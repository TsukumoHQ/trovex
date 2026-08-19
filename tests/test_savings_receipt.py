"""The token-savings RECEIPT — real tokenizer + honest, precision-gated numbers.

Covers task 9aaf0738's bar: chars/4 replaced by a real tokenizer; the
counterfactual is explicit and never negative; savings are gated on measured
retrieval hit@1 (no adjusted number without an eval); per-session / per-agent /
lifetime aggregation over the new session_id column; the trovex://savings
resources; the inline cumulative counter copy; and the REST endpoints.

Hermetic: a bare schema DB (db.open_db) for the model, the deterministic
BagEmbedder + a TestClient for the HTTP surface. No model download, no network.
"""

from __future__ import annotations

import hashlib
import re
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

import trovex.db as dbmod
from trovex import savings, tokens
from trovex import state as state_mod
from trovex import usage
from trovex.config import Settings
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.server import build_app
from trovex.state import AppState
from trovex.store import SqliteStore

DIM = 384


@pytest.fixture
def db(tmp_path):
    return dbmod.open_db(tmp_path / "trovex.db", DIM)


def _log(db, *, whr, topr, resp, user="alpha", session="sess-1", ts=None):
    """Insert one mcp_queries row with explicit token components."""
    db.execute(
        """INSERT INTO mcp_queries
           (ts, user, session_id, query, n_results, summary, response_tokens_est,
            elapsed_ms, would_have_read_tokens, top_result_tokens)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ts if ts is not None else time.time(), user, session, "q", 3, 0, resp, 1, whr, topr),
    )
    db.commit()


# --- real tokenizer ---------------------------------------------------------


def test_count_tokens_is_real_not_chars_over_4():
    if tokens._encoder() is None:
        pytest.skip("real tokenizer unavailable (offline / no BPE cache)")
    text = "The quick brown fox jumps over the lazy dog."
    n = tokens.count_tokens(text)
    # A real BPE count differs from the naive chars/4 estimate for this string.
    assert n > 0
    assert n != len(text) // 4
    assert tokens.tokenizer_name() == "o200k_base"


def test_count_tokens_falls_back_to_estimate(monkeypatch):
    """When the tokenizer can't load, count honestly degrades to chars/4 and
    tokenizer_name() says so — never a silent zero."""
    monkeypatch.setattr(tokens, "_encoder", lambda: None)
    monkeypatch.setattr(tokens, "_name", tokens._ESTIMATE_NAME)
    text = "x" * 40
    assert tokens.count_tokens(text) == 10  # 40 // 4
    assert tokens.count_tokens("") == 0
    assert tokens.count_tokens("a") == 1  # never 0 for non-empty


# --- counterfactual ---------------------------------------------------------


def test_saved_is_conservative_and_never_negative(db):
    _log(db, whr=1000, topr=200, resp=50)
    rec = savings.totals(db, 0.0)
    assert rec["saved"] == 1000 - 200 - 50
    assert rec["would_have_read"] == 1000

    # A pathological row where the response dwarfs the counterfactual clamps to 0.
    _log(db, whr=10, topr=5, resp=9999, session="sess-2")
    rec2 = savings.session_totals(db, "sess-2")
    assert rec2["saved"] == 0


def test_assumption_ships_in_every_payload(db):
    _log(db, whr=500, topr=100, resp=20)
    for rec in (
        savings.totals(db, 0.0),
        savings.session_totals(db, "sess-1"),
    ):
        assert rec["assumption"] == savings.ASSUMPTION
        assert "would_have_read" in rec["assumption"]


# --- precision gate ---------------------------------------------------------


def test_precision_null_shows_caveat_no_adjusted_number(db):
    _log(db, whr=1000, topr=200, resp=50)
    rec = savings.totals(db, 0.0)
    assert rec["precision"] is None
    assert rec["precision_measured_at"] is None
    assert rec["saved_at_precision"] is None  # never fabricate an adjusted figure
    assert rec["caveat"]  # the 'routing unverified' caveat is present
    assert "unmeasured" in rec["caveat"]


def test_precision_gate_scales_saved_after_eval(db):
    from trovex.retrieval_eval import RetrievalStats

    _log(db, whr=1000, topr=200, resp=50)  # saved = 750
    savings.record_eval_run(
        db, RetrievalStats(n=10, k=5, hit_at_1=0.5, hit_at_k=0.9, mrr=0.7, recall_at_k=0.8)
    )
    rec = savings.totals(db, 0.0)
    assert rec["precision"] == 0.5
    assert rec["precision_measured_at"] is not None
    assert rec["saved_at_precision"] == round(750 * 0.5)  # 375
    assert rec["caveat"] is None  # measured → no caveat

    # Latest run wins.
    savings.record_eval_run(
        db, RetrievalStats(n=10, k=5, hit_at_1=0.8, hit_at_k=0.95, mrr=0.85, recall_at_k=0.9)
    )
    assert savings.totals(db, 0.0)["precision"] == 0.8


# --- aggregation: session / agent / lifetime --------------------------------


def test_per_session_and_per_agent_aggregate(db):
    _log(db, whr=1000, topr=100, resp=50, user="alpha", session="s1")
    _log(db, whr=500, topr=50, resp=20, user="alpha", session="s2")
    _log(db, whr=300, topr=30, resp=10, user="beta", session="s3")

    sessions = savings.per_session(db, 0.0)
    by_session = {r["session"]: r for r in sessions}
    assert set(by_session) == {"s1", "s2", "s3"}
    assert by_session["s1"]["saved"] == 1000 - 100 - 50
    assert by_session["s1"]["agent"] == "alpha"

    agents = savings.per_agent(db, 0.0)
    by_agent = {r["agent"]: r for r in agents}
    assert by_agent["alpha"]["sessions"] == 2  # distinct sessions
    assert by_agent["beta"]["sessions"] == 1
    assert by_agent["alpha"]["queries"] == 2


def test_session_saved_is_lifetime_running_total(db):
    _log(db, whr=1000, topr=100, resp=50, session="s1")
    _log(db, whr=200, topr=20, resp=10, session="s1")
    assert savings.session_saved(db, "s1") == (1000 - 100 - 50) + (200 - 20 - 10)


# --- session_id plumbing ----------------------------------------------------


def test_log_query_persists_session_from_contextvar(db):
    tok = usage.current_session.set("ctx-session")
    try:
        usage.log_query(db, "hello", 1, False, response_tokens_est=5, elapsed_ms=1)
    finally:
        usage.current_session.reset(tok)
    row = db.execute("SELECT session_id FROM mcp_queries").fetchone()
    assert row["session_id"] == "ctx-session"


@pytest.mark.asyncio
async def test_middleware_maps_mcp_session_header():
    """Mcp-Session-Id → current_session, with X-TROVEX-Session taking precedence."""
    from starlette.requests import Request

    mw = usage.UserHeaderMiddleware(app=lambda *a, **k: None)
    seen = {}

    async def call_next(_request):
        seen["session"] = usage.current_session.get()

        class _R:
            pass

        return _R()

    scope = {
        "type": "http",
        "headers": [(b"mcp-session-id", b"abc123")],
    }
    await mw.dispatch(Request(scope), call_next)
    assert seen["session"] == "abc123"

    scope2 = {
        "type": "http",
        "headers": [(b"mcp-session-id", b"abc123"), (b"x-trovex-session", b"override")],
    }
    await mw.dispatch(Request(scope2), call_next)
    assert seen["session"] == "override"


# --- MCP resource receipts + inline counter ---------------------------------


def test_receipt_markdown_states_number_tokenizer_and_precision(db):
    _log(db, whr=100_000, topr=2_000, resp=100)
    md = savings.render_receipt_md(db)
    assert "savings receipt" in md
    assert "tokens saved" in md
    assert tokens.tokenizer_name() in md  # tokenizer stated (real name or estimate)
    assert "unmeasured" in md.lower() or "hit@1" in md  # precision honesty


def test_session_receipt_markdown(db):
    _log(db, whr=5000, topr=500, resp=50, session="mysession")
    md = savings.render_session_md(db, "mysession")
    assert "mysession" in md
    assert "tokens saved" in md
    empty = savings.render_session_md(db, "nope")
    assert "no queries" in empty


def test_inline_counter_copy_is_precision_honest():
    unverified = savings.inline_counter(1200, 48000, None)
    assert "saved this call" in unverified
    assert "this session" in unverified
    assert "routing unverified" in unverified

    measured = savings.inline_counter(1200, 48000, 0.86)
    assert "hit@1=0.86" in measured


# --- REST surface -----------------------------------------------------------


class _BagEmbedder:
    name = "bag"
    dim = DIM

    def embed(self, texts):
        for t in texts:
            v = np.zeros(DIM, dtype=np.float32)
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                idx = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                v[idx % DIM] += 1.0
            norm = float(np.linalg.norm(v)) or 1.0
            yield v / norm


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    emb = _BagEmbedder()
    store = SqliteStore(settings, embedder=emb)
    # Seed a few query rows so the endpoints have something to aggregate.
    _log(store.db, whr=1000, topr=100, resp=50, user="alpha", session="s1")
    _log(store.db, whr=400, topr=40, resp=10, user="beta", session="s2")
    state_mod._state = AppState(
        settings=settings,
        embedder=emb,
        searcher=Searcher(settings, embedder=emb),
        indexer=Indexer(settings, embedder=emb),
        store=store,
    )
    try:
        yield TestClient(build_app())
    finally:
        state_mod.reset_state()


def test_api_savings_carries_full_receipt(client):
    body = client.get("/api/savings", params={"days": 7}).json()
    for key in ("saved", "would_have_read", "tokenizer", "precision", "assumption", "caveat"):
        assert key in body
    assert body["assumption"] == savings.ASSUMPTION


def test_api_savings_lifetime_and_breakdowns(client):
    life = client.get("/api/savings/lifetime").json()
    assert "assumption" in life and life["saved"] >= 0

    agents = client.get("/api/savings/agents").json()
    assert {a["agent"] for a in agents} == {"alpha", "beta"}
    assert all("saved_at_precision" in a and "sessions" in a for a in agents)

    sessions = client.get("/api/savings/sessions").json()
    assert {s["session"] for s in sessions} == {"s1", "s2"}
    assert all("agent" in s and "saved" in s for s in sessions)


def test_api_savings_carries_dollar_fields(client):
    """The $ dimension is served alongside the token receipt (additive)."""
    body = client.get("/api/savings/lifetime").json()
    for key in ("saved_usd", "saved_usd_at_precision", "pricing"):
        assert key in body
    assert set(body["pricing"]) == {"model", "input_per_mtok", "source"}
    # no eval seeded → precision unmeasured → $-at-precision is null, not inflated
    assert body["saved_usd_at_precision"] is None
    assert body["saved_usd"] >= 0


def test_api_savings_benchmark_serves_committed_proof(client):
    """GET /api/savings/benchmark wraps the committed benchmark result. When the
    proof is present it must be a sane, non-inflated, deterministic payload; the
    route must 200 regardless (null when the benchmark hasn't been run)."""
    resp = client.get("/api/savings/benchmark")
    assert resp.status_code == 200
    body = resp.json()
    if body is None:
        return  # no committed proof in this tree — the null contract still holds
    assert body["deterministic"] is True
    assert 0 < body["savings_pct"] < 100
    assert body["baseline_tokens"] > body["trovex_tokens"] > 0
    assert body["saved_usd"] >= 0
    assert body["pricing"]["model"]
