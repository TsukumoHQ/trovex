"""Replay real agent queries as the eval set (task b47301eb, Miner D F8 + gap c).

eval_harness runs a hand-written cases.jsonl; the real traffic is already logged
in mcp_queries/mcp_query_results and never replayed. usage.mark_result_used labels
a served row `used=1` when the SAME session reads it back via
trovex_read(doc_id=...) within the labeling window — a free relevance signal the
fleet produces for itself. This module re-runs sampled queries against the
CURRENT index and scores hit@1/MRR against those used-labelled rows only: a
served-but-never-read doc is unlabelled, not "wrong", so it is excluded rather
than counted as a miss.
"""

from __future__ import annotations

import statistics
import time
from collections import Counter
from dataclasses import dataclass, field

from .search import Searcher


@dataclass
class ReplayedQuery:
    query_id: int
    query: str
    session_id: str
    source: str  # 'mcp' | 'boot' | 'prompt' (task 2b7974cf)
    served_path: str | None  # rank-0 path served at the time
    used_path: str | None  # a served path this session later read back, if any
    tokens_served: int
    new_top1: str | None  # top-1 path under the CURRENT index
    new_rank_of_used: int | None  # 1-based rank of used_path today; None if absent/unlabelled
    rank_drift: int | None  # |new rank of the served top1 - 1|; None if it fell out of the pool


@dataclass
class ReplayReport:
    n: int
    n_used_labeled: int
    hit_at_1_used: float
    hit_at_k_used: float
    mrr_used: float
    tokens_served_median: float
    rank_drift_mean: float | None
    k: int
    per_source: dict[str, int] = field(default_factory=dict)
    queries: list[ReplayedQuery] = field(default_factory=list)


def sample_queries(db, *, since_seconds: float, limit: int, source: str | None = None) -> list[dict]:
    """Most recent `limit` mcp_queries rows within the window, each carrying its
    served results (ordered by rank, with their `used` label). `source` narrows
    to one of 'mcp'/'boot'/'prompt' (task 2b7974cf); None samples all of them."""
    cutoff = time.time() - since_seconds
    where = "ts >= ?"
    params: list = [cutoff]
    if source:
        where += " AND source = ?"
        params.append(source)
    rows = db.execute(
        f"""SELECT id, query, session_id, source, top_result_tokens, response_tokens_est
           FROM mcp_queries WHERE {where} ORDER BY ts DESC LIMIT ?""",
        (*params, limit),
    ).fetchall()
    out: list[dict] = []
    for r in rows:
        results = db.execute(
            """SELECT rank, path, used, tokens_est FROM mcp_query_results
               WHERE query_id = ? ORDER BY rank""",
            (r["id"],),
        ).fetchall()
        out.append(
            {
                "id": r["id"],
                "query": r["query"],
                "session_id": r["session_id"],
                "source": r["source"],
                "tokens_served": r["top_result_tokens"] or r["response_tokens_est"] or 0,
                "results": [dict(x) for x in results],
            }
        )
    return out


def replay_eval(
    db,
    searcher: Searcher,
    *,
    since_seconds: float,
    limit: int = 500,
    k: int = 5,
    source: str | None = None,
) -> ReplayReport:
    """Re-run each sampled query against the CURRENT index and compare to what was
    actually served. Every sampled query contributes to tokens_served_median and
    rank_drift; only used-labelled queries contribute to hit@1/hit@k/MRR.
    `source` narrows the sample to one of 'mcp'/'boot'/'prompt'; the report's
    `per_source` breakdown is always over whatever was actually sampled."""
    sampled = sample_queries(db, since_seconds=since_seconds, limit=limit, source=source)
    queries: list[ReplayedQuery] = []
    tokens: list[float] = []
    drifts: list[int] = []
    hit1 = hitk = mrr_sum = 0.0
    n_labeled = 0

    for row in sampled:
        served = row["results"]
        served_path = served[0]["path"] if served else None
        used_row = next((x for x in served if x["used"]), None)
        used_path = used_row["path"] if used_row else None

        fresh = searcher.search(row["query"], limit=max(k, 20))
        fresh_paths = [x.path for x in fresh]

        new_rank_of_used = None
        if used_path:
            n_labeled += 1
            try:
                new_rank_of_used = fresh_paths.index(used_path) + 1
            except ValueError:
                new_rank_of_used = None
            if new_rank_of_used == 1:
                hit1 += 1.0
            if new_rank_of_used and new_rank_of_used <= k:
                hitk += 1.0
                mrr_sum += 1.0 / new_rank_of_used

        drift = None
        if served_path:
            try:
                drift = abs(fresh_paths.index(served_path) + 1 - 1)
                drifts.append(drift)
            except ValueError:
                pass

        tokens.append(float(row["tokens_served"] or 0))
        queries.append(
            ReplayedQuery(
                query_id=row["id"],
                query=row["query"],
                session_id=row["session_id"],
                source=row["source"],
                served_path=served_path,
                used_path=used_path,
                tokens_served=row["tokens_served"] or 0,
                new_top1=fresh_paths[0] if fresh_paths else None,
                new_rank_of_used=new_rank_of_used,
                rank_drift=drift,
            )
        )

    return ReplayReport(
        n=len(sampled),
        n_used_labeled=n_labeled,
        hit_at_1_used=(hit1 / n_labeled) if n_labeled else 0.0,
        hit_at_k_used=(hitk / n_labeled) if n_labeled else 0.0,
        mrr_used=(mrr_sum / n_labeled) if n_labeled else 0.0,
        tokens_served_median=statistics.median(tokens) if tokens else 0.0,
        rank_drift_mean=(sum(drifts) / len(drifts)) if drifts else None,
        k=k,
        per_source=dict(Counter(row["source"] for row in sampled)),
        queries=queries,
    )


def gate_replay(report: ReplayReport, baseline: dict) -> tuple[bool, str]:
    """Compare a replay report against baseline thresholds: {"min_hit_at_1":
    float, "max_tokens_served_median": float}. Fails closed: no used-labelled
    queries in the window is NOT a pass — a green gate must never mean "we
    didn't actually check"."""
    if report.n_used_labeled == 0:
        return False, "no used-labelled queries in window (nothing to gate on)"
    min_hit_at_1 = float(baseline.get("min_hit_at_1", 0))
    max_tokens = baseline.get("max_tokens_served_median")
    reasons = []
    if report.hit_at_1_used < min_hit_at_1:
        reasons.append(f"hit@1(used) {report.hit_at_1_used:.2f} < baseline {min_hit_at_1}")
    if max_tokens is not None and report.tokens_served_median > float(max_tokens):
        reasons.append(
            f"tokens-served median {report.tokens_served_median:.0f} > baseline {max_tokens}"
        )
    if reasons:
        return False, "; ".join(reasons)
    return True, "ok"


def format_replay_report(report: ReplayReport) -> str:
    lines = [
        f"replay eval: n={report.n} used-labelled={report.n_used_labeled}",
        f"hit@1(used)={report.hit_at_1_used:.2f} hit@{report.k}(used)={report.hit_at_k_used:.2f} "
        f"MRR(used)={report.mrr_used:.3f} tokens-served median={report.tokens_served_median:.0f}",
    ]
    if report.per_source:
        by_source = ", ".join(f"{s}={n}" for s, n in sorted(report.per_source.items()))
        lines.append(f"by source: {by_source}")
    if report.rank_drift_mean is not None:
        lines.append(f"rank drift (served top1 vs fresh top-20): mean={report.rank_drift_mean:.2f}")
    return "\n".join(lines)
