"""Active-memory boot recall (RFC 330e7d43, step 2).

Serves an agent its OWN recent records as a token-light pointer pack, scoped
server-side: owner/<agent> + kind=record. Scope first, score second — global
vector + an absolute threshold cross-injects; owner-scope yields precision≈1
by construction. The pack is ~80 tokens (titles + ids, not bodies); the agent
pulls a full record on demand via trovex_read(doc_id).
"""

from __future__ import annotations

import sqlite3

from .search import Searcher
from .budget import BudgetCandidate, fit_budget
from .tokens import count_tokens as _count_tokens

BOOT_QUERY = "current state resume open work in flight next steps gotchas"

# The prompt hook passes the WHOLE user prompt as q=. Agent preambles and task
# notifications run to tens of thousands of chars, and rejecting those was a
# silently-lost recall: the hook swallows the error, so the agent just got no
# pointers. Truncate instead. 2000 chars ≈ the 512-token window of the default
# encoder (bge-small-en-v1.5), so anything past it never reached the vector
# anyway — the cap observes that limit rather than adding one. Head, not tail:
# in these prompts the task identity (name, branch, id) leads and the
# boilerplate trails.
BOOT_Q_MAX = 2000


def _empty_pack(agent: str, budget: int | None = None) -> dict:
    pack = {"agent": agent, "pointers": [], "render": "", "tokens_est": 0}
    if budget is not None:
        pack.update(budget_requested=budget, budget_used=0, trimmed=[])
    return pack


def boot_pointers(
    searcher: Searcher,
    agent: str,
    *,
    k: int = 5,
    floor: float = 0.62,
    q: str | None = None,
    budget: int | None = None,
) -> dict:
    """The agent's own records as a pointer pack. Empty (zero cost) when nothing
    clears scope + floor — a session for an unknown agent injects nothing.

    Best-effort: boot must NEVER 500. Any retrieval OperationalError (e.g. the
    sqlite-vec KNN ceiling on a large store, a locked/backup db) degrades to an
    empty pack instead of taking the whole fleet's Active-Memory boot down."""
    try:
        results = searcher.search(
            (q or BOOT_QUERY)[:BOOT_Q_MAX],
            limit=50 if budget is not None else k,
            source_ids=["trovex"],
            kind="record",
            # owner tags are stored lower-cased; normalise the query so a mixed-case
            # agent (e.g. "COO") recalls its own records instead of nothing.
            tags=[f"owner/{agent.lower()}"],
            # Dense-only: `floor` is an absolute cosine-similarity threshold (~0.62).
            # The flagship search now fuses BM25+dense via RRF, whose scores are ~an
            # order of magnitude smaller — using it here would floor every record out
            # and return empty recall. Scope (owner+record) is what yields precision
            # here; the dense score is the semantic-relevance gate on top.
            hybrid=False,
        )
    except sqlite3.OperationalError:
        return _empty_pack(agent, budget)
    results = [r for r in results if r.score >= floor]
    if not results:
        return _empty_pack(agent, budget)

    if budget is not None:
        candidates = []
        for result in results:
            row = searcher.db.execute(
                "SELECT content FROM docs WHERE ext_id = ?", (result.path,)
            ).fetchone()
            content = row["content"] if row else ""
            stub = f"- {result.title}  (trovex:{result.path})"
            words = content.split()
            extract = " ".join(words[:50]) + ("…" if len(words) > 50 else "")
            candidates.append(
                BudgetCandidate(
                    result.path,
                    {
                        "stub": stub,
                        "card": f"{stub}\n  {extract}",
                        "passage": f"{stub}\n\n{content}",
                    },
                )
            )
        fitted = fit_budget(candidates, budget)
        pointers = [
            {
                "id": item["doc_id"],
                "title": results[i].title,
                "score": round(results[i].score, 3),
                "tier": item["tier"],
                "text": item["text"],
                "tokens_est": item["tokens_est"],
            }
            for i, item in enumerate(fitted["results"])
        ]
        render = "\n".join(item["text"] for item in fitted["results"])
        return {
            "agent": agent,
            "pointers": pointers,
            "render": render,
            "tokens_est": fitted["budget_used"],
            "budget_requested": budget,
            "budget_used": fitted["budget_used"],
            "trimmed": fitted["trimmed"],
        }

    pointers = [{"id": r.path, "title": r.title, "score": round(r.score, 3)} for r in results]
    lines = [f"## Resume — {agent} (trovex active memory)"]
    lines += [f"- {p['title']}  (trovex:{p['id']})" for p in pointers]
    lines.append("Pull any with trovex_read(doc_id) for the full record.")
    render = "\n".join(lines)
    return {
        "agent": agent,
        "pointers": pointers,
        "render": render,
        "tokens_est": _count_tokens(render),
    }
