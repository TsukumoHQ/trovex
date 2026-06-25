"""Reproducible token-savings benchmark — backs the ~60% claim, honestly.

Runs a query set through the SHIPPED savings model (`Searcher.savings_estimate`:
without trovex an agent reads the top-3 candidate docs to triage; with trovex it
reads the 1 canonical doc → `saved = top3_tokens - top1_tokens - pointer`). It
reports the DISTRIBUTION across the query set — median + p25/p75 spread and the
aggregate ratio — never a cherry-picked maximum.

The number is only as honest as the query set: pass a REPRESENTATIVE set of real
doc-lookup questions (coordinate analytics-lead), not hand-picked winners. This
module is the reproducible harness; the published figure is whatever the vetted
query set yields, stated with its spread.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median, quantiles

from .search import Searcher


@dataclass
class BenchResult:
    n_queries: int
    n_scored: int  # queries that produced a top-1-vs-top-3 comparison
    median_ratio: float
    p25_ratio: float
    p75_ratio: float
    total_saved: int
    total_would_have_read: int
    per_query: list[dict] = field(default_factory=list)

    @property
    def aggregate_ratio(self) -> float:
        """Pooled saving = Σ saved / Σ would-have-read (weights by doc size)."""
        return self.total_saved / self.total_would_have_read if self.total_would_have_read else 0.0


def run_benchmark(
    searcher: Searcher,
    queries: list[str],
    *,
    limit: int = 5,
    source_ids: list[str] | None = None,
) -> BenchResult:
    """Score each query against an already-indexed `searcher`. Pure + deterministic
    for a given index + embedder, so the result is reproducible."""
    rows: list[dict] = []
    for q in queries:
        results = searcher.search(q, limit=limit, source_ids=source_ids)
        s = searcher.savings_estimate(results)
        scored = bool(s and s["would_have_read"])
        rows.append(
            {
                "query": q,
                "scored": scored,
                "ratio": round(s["ratio"], 4) if scored else 0.0,
                "saved": s["saved"] if scored else 0,
                "would_have_read": s["would_have_read"] if s else 0,
            }
        )

    scored_rows = [r for r in rows if r["scored"]]
    ratios = sorted(r["ratio"] for r in scored_rows)
    med = median(ratios) if ratios else 0.0
    if len(ratios) >= 2:
        q1, _q2, q3 = quantiles(ratios, n=4)  # p25, p50, p75
        p25, p75 = q1, q3
    else:
        p25 = p75 = med

    return BenchResult(
        n_queries=len(queries),
        n_scored=len(scored_rows),
        median_ratio=med,
        p25_ratio=p25,
        p75_ratio=p75,
        total_saved=sum(r["saved"] for r in scored_rows),
        total_would_have_read=sum(r["would_have_read"] for r in scored_rows),
        per_query=rows,
    )


def format_report(r: BenchResult, *, repo: str = "", query_source: str = "") -> str:
    """Honest plain-text report: method, distribution, spread — not a single hero number."""
    lines = [
        "# trovex token-savings benchmark (modelled per doc-lookup)",
        "",
        "Method: per query, would-have-read = Σ top-3 result tokens; with trovex = top-1",
        "canonical doc + a small pointer. saved = would_have_read − top1 − pointer; "
        "ratio = saved / would_have_read. This is a MODEL, not a live A/B.",
        "",
        f"Repo(s): {repo or '(unspecified)'}",
        f"Query set: {query_source or '(unspecified — must be representative, not cherry-picked)'}",
        f"Queries: {r.n_queries} ({r.n_scored} scored)",
        "",
        f"Median saving per lookup: {r.median_ratio * 100:.0f}%  "
        f"(p25 {r.p25_ratio * 100:.0f}% – p75 {r.p75_ratio * 100:.0f}%)",
        f"Aggregate (pooled by tokens): {r.aggregate_ratio * 100:.0f}%",
        "",
        "Honest framing: report the median + spread above, not the max.",
    ]
    return "\n".join(lines)
