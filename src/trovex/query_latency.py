"""sqlite-vec query-latency benchmark.

Measures end-to-end retrieval latency (embed the query + the sqlite-vec knn join +
scoring) over a corpus, so a regression in the hot read path is caught as numbers,
not vibes. Pure measurement: the Searcher (hence the store, embedder, and corpus) is
injected by the caller — hermetic in tests, real in a CLI run.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from .search import Searcher


@dataclass
class LatencyStats:
    n: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float

    def as_dict(self) -> dict:
        return asdict(self)


def _percentile(sorted_ms: list[float], q: float) -> float:
    """Nearest-rank percentile of an ascending list. q in [0, 1]."""
    if not sorted_ms:
        return 0.0
    idx = min(len(sorted_ms) - 1, max(0, round(q * (len(sorted_ms) - 1))))
    return sorted_ms[idx]


def measure_query_latency(
    searcher: Searcher,
    queries: list[str],
    *,
    source_ids: list[str] | None = None,
    limit: int = 5,
    kind: str | None = None,
    tags: list[str] | None = None,
    repeats: int = 1,
) -> LatencyStats:
    """Time `searcher.search` over every query, `repeats` times, and aggregate.

    Each timed call is the full read path (query embed + knn + scoring). Returns
    zeroed stats when there is nothing to time (no queries / repeats <= 0).
    """
    samples: list[float] = []
    for _ in range(max(0, repeats)):
        for q in queries:
            t0 = time.perf_counter()
            searcher.search(q, limit=limit, source_ids=source_ids, kind=kind, tags=tags)
            samples.append((time.perf_counter() - t0) * 1000.0)

    if not samples:
        return LatencyStats(n=0, mean_ms=0.0, p50_ms=0.0, p95_ms=0.0, max_ms=0.0)

    samples.sort()
    return LatencyStats(
        n=len(samples),
        mean_ms=sum(samples) / len(samples),
        p50_ms=_percentile(samples, 0.5),
        p95_ms=_percentile(samples, 0.95),
        max_ms=samples[-1],
    )


def format_latency_stats(stats: LatencyStats) -> str:
    return (
        f"query latency over n={stats.n}: "
        f"p50={stats.p50_ms:.2f}ms  p95={stats.p95_ms:.2f}ms  "
        f"mean={stats.mean_ms:.2f}ms  max={stats.max_ms:.2f}ms"
    )
