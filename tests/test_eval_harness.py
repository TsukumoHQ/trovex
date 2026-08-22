"""eval_harness: cases.jsonl loading, the combined retrieval+rubric run, resumability,
the $ budget cap (never silently drops a pending case), and both release gates. Hermetic —
bag-of-words embedder + fake answer/judge callables, no LLM, no network."""

from __future__ import annotations

import hashlib
import json
import re

import numpy as np
import pytest

from trovex.config import Settings
from trovex.eval_bench import EvalQuery
from trovex.eval_harness import (
    EvalCase,
    HarnessReport,
    format_harness_report,
    gate,
    gate_retrieval_only,
    load_cases,
    run_harness,
)
from trovex.eval_rubric import RubricScore
from trovex.retrieval_eval import RetrievalStats
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
def corpus(tmp_path):
    """Two well-separated docs; return the searcher + their ids."""
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "none.yaml",
    )
    store = SqliteStore(settings, embedder=_Bag())
    ids = {
        "auth": store.put("# Auth\n\njwt token signature validation rotate keys", kind="reference"),
        "deploy": store.put("# Deploy\n\nkubernetes pod rollout rollback crash loop", kind="reference"),
    }
    return Searcher(settings, embedder=_Bag()), ids


def _fixed_judge(score: RubricScore | None = None, calls: list | None = None):
    score = score or RubricScore(correctness=80, autonomy=80, actionability=80, safety=80, concision=80)
    calls = calls if calls is not None else []

    def judge_fn(eq: EvalQuery, answer: str) -> RubricScore:
        calls.append(eq.query)
        return score

    return judge_fn


def _answer_fn(query: str, context: str) -> tuple[str, int]:
    return "ans", 5


def _content_fn(result) -> str:
    return "doc text " * 20


# ── load_cases ────────────────────────────────────────────────────────────


def test_load_cases_parses_fields(tmp_path):
    p = tmp_path / "cases.jsonl"
    p.write_text(
        "# a comment line, skipped\n"
        "\n"
        '{"query": "how do I auth", "category": "C1", "expected_docs": ["auth.md"]}\n'
        '{"query": "is X supported", "category": "C6", "in_corpus": false}\n',
        encoding="utf-8",
    )
    cases = load_cases(p)
    assert len(cases) == 2
    assert cases[0].query == "how do I auth"
    assert cases[0].in_corpus is True  # default
    assert cases[0].expected_docs == ["auth.md"]
    assert cases[1].in_corpus is False
    assert cases[1].expected_docs == []  # default


def test_case_conversions():
    c = EvalCase(query="q", category="C1", expected_docs=["a.md", "b.md"])
    lq = c.as_labeled_query()
    assert lq.query == "q" and lq.relevant == ["a.md", "b.md"]
    eq = c.as_eval_query()
    assert eq.query == "q" and eq.category == "C1" and eq.in_corpus is True


# ── run_harness: retrieval_only ─────────────────────────────────────────


def test_retrieval_only_skips_llm_entirely(corpus):
    searcher, ids = corpus
    cases = [
        EvalCase("jwt token signature validation", "C1", expected_docs=[ids["auth"]]),
        EvalCase("kubernetes pod rollout rollback", "C1", expected_docs=[ids["deploy"]]),
    ]
    report = run_harness(cases, searcher, k=3, retrieval_only=True)
    assert report.n_scored == 0
    assert report.n_pending == 0
    assert report.mean_weighted is None
    assert report.per_category == []
    assert isinstance(report.retrieval, RetrievalStats)
    assert report.retrieval.hit_at_1 == 1.0


def test_retrieval_only_requires_no_callables(corpus):
    searcher, ids = corpus
    cases = [EvalCase("jwt token", "C1", expected_docs=[ids["auth"]])]
    # None of answer_fn/judge_fn/content_fn are passed — must not raise.
    run_harness(cases, searcher, retrieval_only=True)


def test_full_run_requires_callables(corpus):
    searcher, _ids = corpus
    cases = [EvalCase("q", "C1")]
    with pytest.raises(AssertionError):
        run_harness(cases, searcher)


# ── run_harness: full rubric pass ───────────────────────────────────────


def test_full_run_scores_every_case(corpus):
    searcher, ids = corpus
    cases = [
        EvalCase("jwt token signature validation", "C1", expected_docs=[ids["auth"]]),
        EvalCase("kubernetes pod rollout rollback", "C2", expected_docs=[ids["deploy"]]),
    ]
    calls = []
    report = run_harness(
        cases,
        searcher,
        answer_fn=_answer_fn,
        judge_fn=_fixed_judge(calls=calls),
        content_fn=_content_fn,
    )
    assert report.n_scored == 2
    assert report.n_pending == 0
    assert calls == ["jwt token signature validation", "kubernetes pod rollout rollback"]
    assert report.mean_weighted == pytest.approx(80.0)
    cats = {c.category: c for c in report.per_category}
    assert cats["C1"].n == 1 and cats["C2"].n == 1


def test_resume_never_re_judges_a_done_case(corpus, tmp_path):
    searcher, ids = corpus
    resume_path = tmp_path / "resume.jsonl"
    resume_path.write_text(
        json.dumps(
            {
                "query": "jwt token signature validation",
                "category": "C1",
                "rubric": {
                    "correctness": 100,
                    "autonomy": 100,
                    "actionability": 100,
                    "safety": 100,
                    "concision": 100,
                    "raw": "cached",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cases = [
        EvalCase("jwt token signature validation", "C1", expected_docs=[ids["auth"]]),
        EvalCase("kubernetes pod rollout rollback", "C1", expected_docs=[ids["deploy"]]),
    ]
    calls = []
    report = run_harness(
        cases,
        searcher,
        answer_fn=_answer_fn,
        judge_fn=_fixed_judge(RubricScore(50, 50, 50, 50, 50), calls),
        content_fn=_content_fn,
        resume_path=resume_path,
    )
    # only the NEW case was judged — the resumed one is reused, not re-spent.
    assert calls == ["kubernetes pod rollout rollback"]
    assert report.n_scored == 2
    resumed = next(r for r in report.results if r.query == "jwt token signature validation")
    assert resumed.rubric.correctness == 100  # came from resume, not the fake judge (50s)
    # the new case's result got appended to the resume log for a future resume.
    lines = resume_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_budget_stops_early_without_dropping_pending(corpus):
    searcher, ids = corpus
    cases = [
        EvalCase(f"jwt token signature validation {i}", "C1", expected_docs=[ids["auth"]]) for i in range(3)
    ]
    report = run_harness(
        cases,
        searcher,
        answer_fn=_answer_fn,
        judge_fn=_fixed_judge(),
        content_fn=_content_fn,
        budget_usd=0.002,
        cost_per_case_usd=0.002,
    )
    assert report.n_scored == 1
    assert report.n_pending == 2
    assert report.n_scored + report.n_pending == report.n_cases  # nothing silently dropped


# ── gate / gate_retrieval_only ──────────────────────────────────────────


def _report(n_scored=1, n_pending=0, mean_weighted=80.0, hit_at_1=1.0):
    return HarnessReport(
        n_cases=n_scored + n_pending,
        n_scored=n_scored,
        n_pending=n_pending,
        mean_weighted=mean_weighted,
        per_category=[],
        retrieval=RetrievalStats(n=1, k=5, hit_at_1=hit_at_1, hit_at_k=1.0, mrr=1.0, recall_at_k=1.0),
        results=[],
    )


def test_gate_passes_when_above_baseline():
    ok, reason = gate(_report(), {"min_weighted": 60, "min_hit_at_1": 0.5})
    assert ok and reason == "ok"


def test_gate_fails_on_zero_scored():
    ok, reason = gate(_report(n_scored=0, mean_weighted=None), {"min_weighted": 60})
    assert not ok and "no cases scored" in reason


def test_gate_fails_when_pending_left():
    ok, reason = gate(_report(n_pending=1), {"min_weighted": 60})
    assert not ok and "pending" in reason


def test_gate_fails_below_weighted_baseline():
    ok, reason = gate(_report(mean_weighted=40.0), {"min_weighted": 60})
    assert not ok and "weighted score" in reason


def test_gate_fails_below_hit_at_1_baseline():
    ok, reason = gate(_report(hit_at_1=0.2), {"min_hit_at_1": 0.5})
    assert not ok and "hit@1" in reason


def test_gate_retrieval_only_ignores_n_scored():
    # a retrieval_only report always has n_scored=0 — the dedicated gate must not
    # treat that as a failure the way the full `gate` does.
    report = _report(n_scored=0, mean_weighted=None, hit_at_1=0.8)
    ok, reason = gate_retrieval_only(report, {"min_hit_at_1": 0.5})
    assert ok and reason == "ok"


def test_gate_retrieval_only_fails_below_threshold():
    report = _report(n_scored=0, mean_weighted=None, hit_at_1=0.2)
    ok, reason = gate_retrieval_only(report, {"min_hit_at_1": 0.5})
    assert not ok and "hit@1" in reason


# ── format_harness_report ───────────────────────────────────────────────


def test_format_report_shows_pending_and_rubric():
    report = _report(n_pending=2)
    out = format_harness_report(report)
    assert "pending" in out
    assert "rubric weighted score" in out


def test_format_report_omits_rubric_line_when_none_scored():
    report = _report(n_scored=0, mean_weighted=None)
    out = format_harness_report(report)
    assert "rubric weighted score" not in out
