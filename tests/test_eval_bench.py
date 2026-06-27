"""eval_bench accounting (TSU-42 spine). The load-bearing assertion: a token cut that
breaks the answer is NOT a win — saving is counted ONLY at equal task-success, and a
trovex-wrong/baseline-right query is a reported LOSS. Pure, no LLM."""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex.config import Settings
from trovex.eval_bench import (
    ArmResult,
    EvalQuery,
    QueryEval,
    aggregate,
    eval_query,
    format_eval_report,
    run_eval,
)
from trovex.search import Searcher
from trovex.store import SqliteStore

DIM = 384


class _Bag:
    name = "bag"
    dim = DIM

    def embed(self, texts):
        for t in texts:
            v = np.zeros(DIM, dtype=np.float32)
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                idx = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                v[idx % DIM] += 1.0
            yield v / (float(np.linalg.norm(v)) or 1.0)


@pytest.fixture
def searcher(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "none.yaml",
    )
    store = SqliteStore(settings, embedder=_Bag())
    for i in range(5):
        store.put(
            f"# Auth {i}\n\njwt token session refresh expiry rotation handler variant {i}",
            tags=[f"d/{i}"],
        )
    return Searcher(settings, embedder=_Bag())


def _q(cat, t_correct, t_tok, b_correct, b_tok, query="q"):
    return QueryEval(
        query=query,
        category=cat,
        trovex=ArmResult(correct=t_correct, tokens=t_tok),
        baseline=ArmResult(correct=b_correct, tokens=b_tok),
    )


def test_saving_counted_only_at_equal_success():
    e = _q("C1", True, 100, True, 300)  # both correct
    assert e.equal_success
    assert abs(e.saving_ratio - (200 / 300)) < 1e-9  # ~0.67


def test_fewer_tokens_but_wrong_is_not_a_win():
    # trovex reads less (50) but is WRONG; baseline correct. The gate: NOT counted, and a LOSS.
    e = _q("C7", False, 50, True, 300)
    assert e.saving_ratio is None  # not counted toward the number
    assert e.trovex_loss is True
    assert e.equal_success is False


def test_trovex_only_win_not_counted_as_saving():
    # trovex right, baseline wrong → a quality win for trovex, but NOT an equal-success token saving.
    e = _q("C8", True, 100, False, 300)
    assert e.trovex_only_win is True
    assert e.saving_ratio is None
    assert e.trovex_loss is False


def test_miss_case_both_abstain_counts_as_equal_success():
    # C6: answer not in corpus. Both correctly abstain (correct=True). Near-zero saving is fine.
    e = _q("C6", True, 40, True, 60)
    assert e.equal_success
    assert e.saving_ratio is not None and e.saving_ratio >= 0.0


def test_aggregate_gates_and_surfaces_losses():
    evals = [
        _q("C1", True, 100, True, 300),  # counted, ~0.67
        _q("C1", True, 200, True, 400),  # counted, 0.50
        _q("C7", False, 50, True, 300),  # LOSS, not counted
        _q("C8", True, 80, False, 300),  # trovex-only win, not counted
        _q("C6", True, 40, True, 50),  # counted, 0.20
    ]
    r = aggregate(evals)
    assert r.n_queries == 5
    assert r.n_equal_success == 3  # C1x2 + C6
    assert r.n_trovex_loss == 1  # the C7 loss is surfaced
    assert r.median_saving is not None and 0.0 <= r.median_saving <= 1.0
    cats = {c.category: c for c in r.per_category}
    assert cats["C7"].n_trovex_loss == 1
    assert cats["C8"].n_trovex_only_win == 1
    assert cats["C1"].n_equal_success == 2


def test_report_states_number_losses_and_equal_success():
    r = aggregate([_q("C1", True, 100, True, 300), _q("C7", False, 50, True, 300)])
    out = format_eval_report(r, query_source="test set (NOT pre-registered)")
    assert "equal task-success" in out
    assert "Median token saving at equal success" in out
    assert "LOSS" in out and "quality-loss" in out  # losses surfaced, not hidden


# ── driver (LLM-in-loop, mocked) ─────────────────────────────────────


def test_eval_query_wires_both_arms_and_overhead(searcher):
    # constant answer cost; both arms judged correct → equal success, saving counted.
    qe = eval_query(
        EvalQuery("jwt token session", "C1"),
        searcher,
        answer_fn=lambda q, ctx: ("ans", 7),
        judge_fn=lambda eq, ans: True,
        content_fn=lambda r: "X" * 400,  # ~100 tok per doc
        baseline_k=3,
    )
    assert qe.equal_success
    # baseline (up to 3 docs) reads more than trovex (1 doc) → a real saving.
    assert qe.baseline.tokens > qe.trovex.tokens
    assert qe.saving_ratio is not None and qe.saving_ratio > 0
    # trovex's tokens include its routing/index OVERHEAD (>= 1 doc + answer).
    assert qe.trovex.tokens >= 100 + 7


def test_run_eval_aggregates_a_set(searcher):
    qs = [EvalQuery("jwt token", "C1"), EvalQuery("session refresh", "C2")]
    r = run_eval(
        qs,
        searcher,
        answer_fn=lambda q, ctx: ("a", 5),
        judge_fn=lambda eq, ans: True,
        content_fn=lambda r: "yyyy" * 50,
    )
    assert r.n_queries == 2
    assert r.n_equal_success == 2


def test_driver_passes_eq_to_judge_for_miss_case(searcher):
    # the judge must receive the EvalQuery so a C6 miss-case can score abstention.
    seen: list[bool] = []
    eval_query(
        EvalQuery("nonexistent external fact", "C6", in_corpus=False),
        searcher,
        answer_fn=lambda q, ctx: ("a", 1),
        judge_fn=lambda eq, ans: (seen.append(eq.in_corpus), eq.in_corpus)[1],
        content_fn=lambda r: "c",
        baseline_k=3,
    )
    assert False in seen  # judge saw in_corpus=False (it can score 'correctly abstained')
