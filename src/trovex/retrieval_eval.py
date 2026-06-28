"""Doc-router retrieval-quality eval.

Answers a different question from benchmark.py (token savings) and eval_bench.py
(answer correctness): *does the router return the RIGHT doc?* Given a labelled set of
(query → the doc id(s) that should answer it), it scores the ranking with the standard
IR metrics — hit@1, hit@k, MRR, recall@k — and SURFACES the misses (a quality eval that
hides what it failed on is worthless). Pure scoring: the Searcher is injected, so it's
hermetic in tests and real against a live index in a CLI run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .search import Searcher


@dataclass
class LabeledQuery:
    query: str
    relevant: list[str]  # the doc id(s) (SearchResult.path) that correctly answer it


@dataclass
class RetrievalStats:
    n: int
    k: int
    hit_at_1: float
    hit_at_k: float
    mrr: float
    recall_at_k: float
    misses: list[str] = field(default_factory=list)  # queries with NO relevant doc in top-k


def evaluate_retrieval(
    searcher: Searcher,
    labeled: list[LabeledQuery],
    *,
    k: int = 5,
    source_ids: list[str] | None = None,
    kind: str | None = None,
    tags: list[str] | None = None,
) -> RetrievalStats:
    """Score the router's ranking over a labelled query set.

    - hit@1: top result is relevant.
    - hit@k: any of the top-k is relevant.
    - MRR: mean reciprocal rank of the FIRST relevant hit (0 if none in top-k).
    - recall@k: mean fraction of a query's relevant docs found in top-k.
    Empty/zeroed when there are no queries.
    """
    valid = [lq for lq in labeled if lq.query.strip() and lq.relevant]
    if not valid:
        return RetrievalStats(n=0, k=k, hit_at_1=0.0, hit_at_k=0.0, mrr=0.0, recall_at_k=0.0)

    hit1 = hitk = mrr_sum = recall_sum = 0.0
    misses: list[str] = []
    for lq in valid:
        results = searcher.search(
            lq.query, limit=k, source_ids=source_ids, kind=kind, tags=tags
        )
        ranked = [r.path for r in results]
        relevant = set(lq.relevant)

        if ranked and ranked[0] in relevant:
            hit1 += 1.0

        first_rank = next((i for i, p in enumerate(ranked, start=1) if p in relevant), 0)
        if first_rank:
            hitk += 1.0
            mrr_sum += 1.0 / first_rank
        else:
            misses.append(lq.query)

        found = sum(1 for p in relevant if p in ranked[:k])
        recall_sum += found / len(relevant)

    n = len(valid)
    return RetrievalStats(
        n=n,
        k=k,
        hit_at_1=hit1 / n,
        hit_at_k=hitk / n,
        mrr=mrr_sum / n,
        recall_at_k=recall_sum / n,
        misses=misses,
    )


def format_retrieval_stats(stats: RetrievalStats) -> str:
    lines = [
        f"retrieval quality over n={stats.n} (k={stats.k}): "
        f"hit@1={stats.hit_at_1:.2f}  hit@{stats.k}={stats.hit_at_k:.2f}  "
        f"MRR={stats.mrr:.3f}  recall@{stats.k}={stats.recall_at_k:.2f}",
    ]
    if stats.misses:
        lines.append(f"misses ({len(stats.misses)}): " + " · ".join(stats.misses[:10]))
    return "\n".join(lines)
