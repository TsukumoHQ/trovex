"""sqlite-vec query-latency benchmark — correctness of the measurement + a generous
regression ceiling. Hermetic: bag-of-words embedder, synthetic corpus, no network.

The ceiling is deliberately loose (catches a catastrophic/quadratic regression on a
small corpus, not a few-ms CI jitter). The point is a number that exists and is sane,
not a microbenchmark contract.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex.config import Settings
from trovex.query_latency import LatencyStats, format_latency_stats, measure_query_latency
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
def searcher(settings):
    store = SqliteStore(settings, embedder=BagEmbedder())
    topics = ["jwt token signature", "kubernetes pod rollout", "stripe invoice webhook",
              "embedding vector index", "rate limit backoff retry"]
    for i in range(150):
        topic = topics[i % len(topics)]
        store.put(f"# doc {i}\n\n{topic} detail number {i} body content", kind="reference")
    return Searcher(settings, embedder=BagEmbedder())


def test_measure_query_latency_aggregates(searcher):
    queries = ["jwt token signature", "kubernetes pod rollout", "stripe invoice webhook"]
    stats = measure_query_latency(searcher, queries, source_ids=["trovex"], repeats=4)

    assert isinstance(stats, LatencyStats)
    assert stats.n == len(queries) * 4
    # Percentiles are monotonic and bounded by the max.
    assert 0.0 < stats.p50_ms <= stats.p95_ms <= stats.max_ms
    assert stats.p50_ms <= stats.mean_ms * 5  # mean not wildly detached from the median
    # Generous regression ceiling: a 150-doc sqlite-vec knn must be well under this.
    assert stats.p95_ms < 250.0, format_latency_stats(stats)


def test_measure_query_latency_empty_is_zeroed(searcher):
    assert measure_query_latency(searcher, []).n == 0
    assert measure_query_latency(searcher, ["x"], repeats=0).n == 0
    stats = measure_query_latency(searcher, [])
    assert stats.p50_ms == stats.p95_ms == stats.max_ms == 0.0


def test_latency_stats_as_dict_and_format():
    s = LatencyStats(n=3, mean_ms=1.5, p50_ms=1.0, p95_ms=2.0, max_ms=2.5)
    assert s.as_dict() == {"n": 3, "mean_ms": 1.5, "p50_ms": 1.0, "p95_ms": 2.0, "max_ms": 2.5}
    assert "p95=2.00ms" in format_latency_stats(s)
