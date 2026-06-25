"""Reproducible savings benchmark harness (src/trovex/benchmark.py).

Hermetic: deterministic BagEmbedder, a tmp store/index, no model download. Verifies
the harness scores a query set, reports a distribution (median + p25/p75 + pooled
aggregate) bounded in [0,1], handles the empty set, and that the report states the
method + spread (not a bare hero number).
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex.benchmark import format_report, run_benchmark
from trovex.config import Settings
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
            yield v / (float(np.linalg.norm(v)) or 1.0)


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
    # A handful of overlapping docs so a query returns several candidates (top-3 vs top-1).
    for i in range(6):
        store.put(
            f"# Auth doc {i}\n\njwt token signature session refresh expiry rotation handler variant {i}",
            tags=[f"doc/{i}"],
        )
    return Searcher(settings, embedder=BagEmbedder())


def test_run_benchmark_reports_bounded_distribution(searcher):
    r = run_benchmark(
        searcher,
        ["jwt token signature", "session refresh expiry"],
        source_ids=["trovex"],
    )
    assert r.n_queries == 2
    assert r.n_scored >= 1
    for x in (r.median_ratio, r.p25_ratio, r.p75_ratio, r.aggregate_ratio):
        assert 0.0 <= x <= 1.0
    assert r.p25_ratio <= r.median_ratio <= r.p75_ratio  # spread ordering
    assert len(r.per_query) == 2
    assert r.total_would_have_read > 0


def test_run_benchmark_empty_query_set(searcher):
    r = run_benchmark(searcher, [])
    assert r.n_queries == 0 and r.n_scored == 0
    assert r.median_ratio == 0.0 and r.aggregate_ratio == 0.0


def test_format_report_states_method_and_spread(searcher):
    r = run_benchmark(searcher, ["jwt token signature"], source_ids=["trovex"])
    out = format_report(r, repo="trovex", query_source="test fixture (NOT representative)")
    assert "Method:" in out
    assert "Median saving" in out and "p25" in out and "p75" in out
    assert "MODEL, not a live A/B" in out  # honesty caveat present
