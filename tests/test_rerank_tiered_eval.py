"""Pinned coverage for evaluate_retrieval_tiered (task 4478fe53): the
retrieval-only eval variant that routes through the PRODUCTION tiered dispatch
(rerank.maybe_rerank) so the RRF-margin skip is exercised exactly as the live
`trovex()` tool exercises it, and reports the skip fraction alongside hit@1/MRR
— not just the plain evaluate_retrieval(rerank=True), which calls the local
cross-encoder unconditionally and never sees a skip.

Hermetic: a fake searcher returns fixed, score-controlled candidate lists (full
control over the RRF margin without depending on real embeddings/BM25), and the
local cross-encoder is forced to passthrough (no ONNX load) so the no-skip path
is deterministic regardless of whether this machine has a cached model."""

from __future__ import annotations

import pytest

from trovex import rerank_local
from trovex.retrieval_eval import LabeledQuery, evaluate_retrieval_tiered
from trovex.search import SearchResult


def _sr(path: str, score: float) -> SearchResult:
    return SearchResult(
        path=path,
        title=path,
        distance=0.5,
        score=score,
        age_days=0.0,
        status="canonical",
        size_bytes=100,
        tokens_est=50,
        absolute_path="",
        source_id="code",
    )


class _FakeSearcher:
    """Returns a fixed, score-controlled candidate list per query — total
    control over the RRF margin without depending on real embeddings/BM25."""

    def __init__(self, by_query: dict[str, list[SearchResult]]):
        self._by_query = by_query

    def search(self, query, limit=5, source_ids=None, kind=None, tags=None):  # noqa: ARG002
        return self._by_query[query]


@pytest.fixture(autouse=True)
def _force_local_rerank_passthrough(monkeypatch):
    """No-key tests fall through to the local cross-encoder tier; force it to
    passthrough (no real ONNX load, no machine-dependent behaviour)."""
    monkeypatch.setattr(rerank_local, "_get_encoder", lambda: None)
    rerank_local._encoder = None
    rerank_local._tried = False
    yield
    rerank_local._encoder = None
    rerank_local._tried = False


def test_tiered_eval_reports_skip_fraction_and_hits():
    """q1 has a clear margin (skipped — order untouched, already correct);
    q2 has a tight margin (not skipped, falls to local tier → passthrough,
    order untouched, top-1 stays wrong). skip_fraction must reflect exactly
    the one clear-margin query."""
    clear = [_sr("right.md", 1.0), _sr("wrong.md", 0.4)]  # margin 0.6 > 0.2 → skip
    tight = [_sr("wrong2.md", 1.0), _sr("right2.md", 0.95)]  # margin 0.05 → no skip
    searcher = _FakeSearcher({"q1": clear, "q2": tight})
    labeled = [
        LabeledQuery(query="q1", relevant=["right.md"]),
        LabeledQuery(query="q2", relevant=["right2.md"]),
    ]

    stats, skip_fraction = evaluate_retrieval_tiered(searcher, labeled, k=1)

    assert skip_fraction == 0.5  # exactly 1 of 2 queries skipped
    assert stats.n == 2
    assert stats.hit_at_1 == 0.5  # only q1 hits (skip preserved its correct top-1)


def test_tiered_eval_zero_skip_fraction_when_every_margin_is_tight():
    tight_a = [_sr("a.md", 1.0), _sr("a2.md", 0.99)]
    tight_b = [_sr("b.md", 1.0), _sr("b2.md", 0.98)]
    searcher = _FakeSearcher({"qa": tight_a, "qb": tight_b})
    labeled = [
        LabeledQuery(query="qa", relevant=["a.md"]),
        LabeledQuery(query="qb", relevant=["b.md"]),
    ]

    _, skip_fraction = evaluate_retrieval_tiered(searcher, labeled, k=1)
    assert skip_fraction == 0.0


def test_tiered_eval_full_skip_fraction_when_every_margin_is_clear():
    a = [_sr("a.md", 1.0), _sr("a2.md", 0.1)]
    b = [_sr("b.md", 1.0), _sr("b2.md", 0.1)]
    searcher = _FakeSearcher({"qa": a, "qb": b})
    labeled = [
        LabeledQuery(query="qa", relevant=["a.md"]),
        LabeledQuery(query="qb", relevant=["b.md"]),
    ]

    stats, skip_fraction = evaluate_retrieval_tiered(searcher, labeled, k=1)
    assert skip_fraction == 1.0
    assert stats.hit_at_1 == 1.0  # skip never touches order, both were already right


def test_tiered_eval_empty_labeled_is_zero_not_a_crash():
    stats, skip_fraction = evaluate_retrieval_tiered(_FakeSearcher({}), [], k=5)
    assert stats.n == 0
    assert skip_fraction == 0.0
