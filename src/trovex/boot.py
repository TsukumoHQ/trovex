"""Active-memory boot recall (RFC 330e7d43, step 2).

Serves an agent its OWN recent records as a token-light pointer pack, scoped
server-side: owner/<agent> + kind=record. Scope first, score second — global
vector + an absolute threshold cross-injects; owner-scope yields precision≈1
by construction. The pack is ~80 tokens (titles + ids, not bodies); the agent
pulls a full record on demand via trovex_read(doc_id).
"""

from __future__ import annotations

from .search import Searcher

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


def boot_pointers(
    searcher: Searcher,
    agent: str,
    *,
    k: int = 5,
    floor: float = 0.62,
    q: str | None = None,
) -> dict:
    """The agent's own records as a pointer pack. Empty (zero cost) when nothing
    clears scope + floor — a session for an unknown agent injects nothing."""
    results = searcher.search(
        (q or BOOT_QUERY)[:BOOT_Q_MAX],
        limit=k,
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
    results = [r for r in results if r.score >= floor]
    if not results:
        return {"agent": agent, "pointers": [], "render": "", "tokens_est": 0}

    pointers = [{"id": r.path, "title": r.title, "score": round(r.score, 3)} for r in results]
    lines = [f"## Resume — {agent} (trovex active memory)"]
    lines += [f"- {p['title']}  (trovex:{p['id']})" for p in pointers]
    lines.append("Pull any with trovex_read(doc_id) for the full record.")
    render = "\n".join(lines)
    return {
        "agent": agent,
        "pointers": pointers,
        "render": render,
        "tokens_est": max(1, len(render) // 4),
    }
