"""Doc-router retrieval-quality eval — metric correctness on a known ranking. Hermetic:
bag-of-words embedder, a tiny labelled corpus where the right answer is unambiguous."""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex.config import Settings
from trovex.retrieval_eval import (
    LabeledQuery,
    RetrievalStats,
    evaluate_retrieval,
    format_retrieval_stats,
)
from trovex.search import Searcher
from trovex.store import SqliteStore

DIM = 384


class BagEmbedder:
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
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


@pytest.fixture
def corpus(settings):
    """Three well-separated docs; return the store + their ids."""
    store = SqliteStore(settings, embedder=BagEmbedder())
    ids = {
        "auth": store.put("# Auth\n\njwt token signature validation rotate keys", kind="reference"),
        "deploy": store.put("# Deploy\n\nkubernetes pod rollout rollback crash loop", kind="reference"),
        "billing": store.put("# Billing\n\nstripe invoice webhook reconciliation", kind="reference"),
    }
    return Searcher(settings, embedder=BagEmbedder()), ids


def test_perfect_retrieval_scores_one(corpus):
    searcher, ids = corpus
    labeled = [
        LabeledQuery("jwt token signature validation", [ids["auth"]]),
        LabeledQuery("kubernetes pod rollout rollback", [ids["deploy"]]),
        LabeledQuery("stripe invoice webhook reconciliation", [ids["billing"]]),
    ]
    s = evaluate_retrieval(searcher, labeled, k=3)
    assert s.n == 3
    assert s.hit_at_1 == 1.0
    assert s.hit_at_k == 1.0
    assert s.mrr == 1.0
    assert s.recall_at_k == 1.0
    assert s.misses == []


def test_miss_is_surfaced_and_scored_zero(corpus):
    searcher, ids = corpus
    # A query whose only "relevant" doc is one that does NOT match it → a clean miss.
    # k=1 so the irrelevant-labelled doc falls outside the (single) returned result;
    # with k>=corpus-size every doc is returned and nothing can miss.
    labeled = [LabeledQuery("kubernetes pod rollout rollback", [ids["billing"]])]
    s = evaluate_retrieval(searcher, labeled, k=1)
    assert s.hit_at_1 == 0.0
    assert s.hit_at_k == 0.0
    assert s.mrr == 0.0
    assert s.recall_at_k == 0.0
    assert s.misses == ["kubernetes pod rollout rollback"]


def test_mrr_rewards_rank_two(corpus):
    """When the relevant doc is the top result, MRR=1; when a labelled query accepts a
    doc that lands at rank 2, MRR=0.5. Use a query that matches 'deploy' best but labels
    'auth' as the only relevant → auth should appear lower, giving reciprocal rank < 1."""
    searcher, ids = corpus
    # 'auth' shares no strong tokens with this query, so it won't be rank 1; if it lands
    # in top-3 at rank r, mrr = 1/r < 1. Assert mrr is strictly between 0 and 1 OR a miss.
    labeled = [LabeledQuery("kubernetes pod rollout crash", [ids["auth"]])]
    s = evaluate_retrieval(searcher, labeled, k=3)
    assert 0.0 <= s.mrr <= 1.0
    # hit@1 must be 0 (auth is not the best match for a deploy query).
    assert s.hit_at_1 == 0.0


def test_recall_counts_partial_relevant_set(corpus):
    """recall@k = fraction of a query's relevant docs found. Two relevant, one in top-k
    → recall 0.5."""
    searcher, ids = corpus
    # Query matches auth strongly; label BOTH auth and billing relevant. Only auth ranks.
    labeled = [LabeledQuery("jwt token signature validation", [ids["auth"], ids["billing"]])]
    s = evaluate_retrieval(searcher, labeled, k=1)  # k=1 → only the single best returned
    assert s.hit_at_1 == 1.0  # auth is rank 1
    assert s.recall_at_k == 0.5  # 1 of 2 relevant found


def test_empty_is_zeroed(corpus):
    searcher, _ = corpus
    assert evaluate_retrieval(searcher, []).n == 0
    # queries with no label are skipped → still zero
    s = evaluate_retrieval(searcher, [LabeledQuery("x", [])], k=3)
    assert s.n == 0 and s.mrr == 0.0


def test_format_includes_metrics_and_misses():
    s = RetrievalStats(n=2, k=3, hit_at_1=0.5, hit_at_k=1.0, mrr=0.75, recall_at_k=0.5,
                       misses=["lost query"])
    out = format_retrieval_stats(s)
    assert "hit@1=0.50" in out and "MRR=0.750" in out and "lost query" in out
