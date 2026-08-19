"""$-pricing for the savings receipt — the honesty rails on the dollar figure.

Covers task cfa5c328's bar: tokens saved price at a stated input rate; the $ is
a conservative floor gated on measured precision (never inflated when routing is
unverified); env overrides resolve/degrade safely; and the committed benchmark
result loads. Hermetic: a bare schema DB, no model download, no network.
"""

from __future__ import annotations

import time

import pytest

import trovex.db as dbmod
from trovex import pricing, savings

DIM = 384


@pytest.fixture
def db(tmp_path):
    return dbmod.open_db(tmp_path / "trovex.db", DIM)


def _log(db, *, whr, topr, resp, user="alpha", session="sess-1", ts=None):
    db.execute(
        """INSERT INTO mcp_queries
           (ts, user, session_id, query, n_results, summary, response_tokens_est,
            elapsed_ms, would_have_read_tokens, top_result_tokens)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ts if ts is not None else time.time(), user, session, "q", 3, 0, resp, 1, whr, topr),
    )
    db.commit()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Every test starts from the default reference model, no env override."""
    monkeypatch.delenv("TROVEX_PRICE_MODEL", raising=False)
    monkeypatch.delenv("TROVEX_PRICE_PER_MTOK", raising=False)


# --- the conversion ---------------------------------------------------------


def test_usd_prices_at_default_input_rate():
    # 1M tokens at the gpt-5.4 input rate ($2.50) = $2.50 exactly.
    assert pricing.usd(1_000_000) == pytest.approx(2.50)
    assert pricing.price_model() == "gpt-5.4"
    assert pricing.input_per_mtok() == pytest.approx(2.50)


def test_usd_never_negative_or_none():
    assert pricing.usd(0) == 0.0
    assert pricing.usd(None) == 0.0
    assert pricing.usd(-500) == 0.0


def test_usd_or_none_preserves_none():
    """saved_at_precision is None when precision is unmeasured — the $ mirror must
    stay None too, never fabricate a dollar figure on an unmeasured base."""
    assert pricing.usd_or_none(None) is None
    assert pricing.usd_or_none(1_000_000) == pytest.approx(2.50)


def test_pricing_block_is_never_context_free():
    blk = pricing.pricing_block()
    assert set(blk) == {"model", "input_per_mtok", "source"}
    assert blk["model"] == "gpt-5.4"
    assert blk["input_per_mtok"] == pytest.approx(2.5)
    assert "2026" in blk["source"]


# --- env overrides degrade safely -------------------------------------------


def test_model_override_picks_table_rate(monkeypatch):
    monkeypatch.setenv("TROVEX_PRICE_MODEL", "claude-opus")
    assert pricing.input_per_mtok() == pytest.approx(15.00)
    assert pricing.price_model() == "claude-opus"


def test_unknown_model_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("TROVEX_PRICE_MODEL", "does-not-exist")
    assert pricing.price_model() == "gpt-5.4"
    assert pricing.input_per_mtok() == pytest.approx(2.50)


def test_raw_rate_override_wins(monkeypatch):
    monkeypatch.setenv("TROVEX_PRICE_PER_MTOK", "10")
    assert pricing.input_per_mtok() == pytest.approx(10.0)
    assert pricing.usd(1_000_000) == pytest.approx(10.0)


def test_bad_raw_rate_degrades_not_raises(monkeypatch):
    monkeypatch.setenv("TROVEX_PRICE_PER_MTOK", "not-a-number")
    # falls back to the default table rate rather than crashing the receipt
    assert pricing.input_per_mtok() == pytest.approx(2.50)


def test_negative_raw_rate_ignored(monkeypatch):
    monkeypatch.setenv("TROVEX_PRICE_PER_MTOK", "-5")
    assert pricing.input_per_mtok() == pytest.approx(2.50)


def test_fmt_usd_subcent_keeps_precision():
    # a small-but-real number must not round to $0.00 (which reads as "no savings")
    assert pricing.fmt_usd(0.0079) == "$0.0079"
    assert pricing.fmt_usd(12.5) == "$12.50"


# --- $ woven into the savings receipt ---------------------------------------


def test_totals_carry_dollar_fields_and_pricing_block(db):
    _log(db, whr=1000, topr=100, resp=50)  # saved = 850
    rec = savings.totals(db, 0.0)
    assert rec["saved"] == 850
    assert rec["saved_usd"] == pytest.approx(pricing.usd(850))
    assert rec["pricing"]["model"] == "gpt-5.4"


def test_dollar_at_precision_is_none_when_unmeasured(db):
    """No eval on record → no precision → the $-at-precision figure is None, not
    an inflated raw dollar amount."""
    _log(db, whr=1000, topr=100, resp=50)
    rec = savings.totals(db, 0.0)
    assert rec["precision"] is None
    assert rec["saved_usd_at_precision"] is None
    assert rec["saved_usd"] > 0  # the raw floor is still shown


def test_dollar_at_precision_scales_by_hit_at_1(db):
    _log(db, whr=1000, topr=100, resp=50)  # saved = 850
    db.execute(
        """INSERT INTO retrieval_eval_runs (ts, n, k, hit_at_1, hit_at_k, mrr, recall_at_k)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (time.time(), 10, 5, 0.5, 1.0, 0.7, 1.0),
    )
    db.commit()
    rec = savings.totals(db, 0.0)
    assert rec["precision"] == pytest.approx(0.5)
    assert rec["saved_at_precision"] == round(850 * 0.5)
    assert rec["saved_usd_at_precision"] == pytest.approx(pricing.usd(round(850 * 0.5)))
    # never inflated above the raw floor
    assert rec["saved_usd_at_precision"] <= rec["saved_usd"]


def test_per_agent_and_session_carry_dollars(db):
    _log(db, whr=1000, topr=100, resp=50, user="alpha", session="s1")
    agents = savings.per_agent(db, 0.0)
    sessions = savings.per_session(db, 0.0)
    assert agents and "saved_usd" in agents[0] and "saved_usd_at_precision" in agents[0]
    assert sessions and "saved_usd" in sessions[0] and "saved_usd_at_precision" in sessions[0]


# --- committed benchmark result ---------------------------------------------


def test_benchmark_result_loads_and_is_honest():
    """The committed proof the /api/savings/benchmark route serves. Must parse and
    carry a sane, deterministic, non-inflated savings figure."""
    res = savings.benchmark_result()
    assert res is not None, "run `python benchmarks/token-savings/run.py --fixed` to generate it"
    assert res["deterministic"] is True
    assert 0 < res["savings_pct"] < 100
    assert res["baseline_tokens"] > res["trovex_tokens"] > 0
    assert res["saved_usd"] >= 0
    assert res["pricing"]["model"]
