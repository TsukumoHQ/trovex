"""Active-memory boot recall (RFC 330e7d43, step 2).

Serves an agent its OWN recent records as a token-light pointer pack, scoped
server-side: owner/<agent> + kind=record. Scope first, score second — global
vector + an absolute threshold cross-injects; owner-scope yields precision≈1
by construction. The pack is ~80 tokens (titles + ids, not bodies); the agent
pulls a full record on demand via trovex_read(doc_id).
"""

from __future__ import annotations

import logging
import re
import sqlite3

from .search import Searcher
from .budget import BudgetCandidate, fit_budget
from .query_cache import embed_query_blob
from .tokens import count_tokens as _count_tokens

log = logging.getLogger("trovex.boot")

BOOT_QUERY = "current state resume open work in flight next steps gotchas"

# The prompt hook passes the WHOLE user prompt as q=. Agent preambles and task
# notifications run to tens of thousands of chars, and rejecting those was a
# silently-lost recall: the hook swallows the error, so the agent just got no
# pointers. Truncate instead. Head, not tail: in these prompts the task identity
# (name, branch, id) leads and the boilerplate trails.
#
# perf A (task 62c53f35): 2000 chars ≈ 512 tokens is the model's MAX sequence
# length, so every long prompt paid the full quadratic forward pass (746 ms on a
# loaded host vs 246 ms at 500 chars — measured in the cto perf audit). The
# retrieval signal for owner-scoped recall lives in the first few hundred chars;
# cap at 500 (~128 tokens) so boot embeds stay cheap on the request path.
BOOT_Q_MAX = 500

# Harness boilerplate that leads the prompt hook's q= and carries no retrieval
# signal: the <task-notification>/<system-reminder>/<pasted_content> XML blocks,
# the "You are **name**, role" agent preamble, and the relay "check your relay …"
# nudge line. Stripping these BEFORE the length cap keeps the real task text from
# being truncated away behind boilerplate (which would silently drop recall).
_BOILERPLATE_BLOCK_RE = re.compile(
    r"<(task-notification|system-reminder|pasted_content)\b[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
_AGENT_PREAMBLE_RE = re.compile(r"You are \*\*[^*]+\*\*[^.\n]*[.\n]", re.IGNORECASE)
_RELAY_NUDGE_RE = re.compile(r"[^\n]*check your relay[^\n]*", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def clean_query(text: str) -> str:
    """Strip harness boilerplate from a hook-supplied prompt, then cap length.

    Pure + deterministic so the SAME transform runs on the embed path (boot
    recall) and on the logged query text (the replay eval re-embeds what it
    logged — the two must match or replay drifts). Boilerplate-only input
    collapses to "" and the caller falls back to BOOT_QUERY."""
    t = _BOILERPLATE_BLOCK_RE.sub(" ", text)
    t = _AGENT_PREAMBLE_RE.sub(" ", t)
    t = _RELAY_NUDGE_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t).strip()
    return t[:BOOT_Q_MAX]


def _empty_pack(agent: str, budget: int | None = None, degraded: str | None = None) -> dict:
    # `degraded` names WHY the pack is empty: None = a true scope miss ("no
    # records"); a string ("timeout"/"sqlite"/"ceiling") = recall was SHED, not
    # absent. The prompt hook must be able to tell those apart (ticket 7df08701).
    pack = {"agent": agent, "pointers": [], "render": "", "tokens_est": 0, "degraded": degraded}
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
    cleaned = clean_query(q) if q else ""
    try:
        results = searcher.search(
            cleaned or BOOT_QUERY,
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
    except sqlite3.OperationalError as e:
        msg = str(e)
        if "k value in knn query too large" in msg:
            # Genuine sqlite-vec KNN ceiling: the partition outgrew brute-force k.
            # A BOUNDED (not transient) empty — flagged 'ceiling' + logged so the
            # real fix (the usearch escape hatch) is findable. This is the ONLY
            # OperationalError the boot path treats as an empty recall.
            log.warning("boot recall empty: sqlite-vec KNN ceiling (agent=%s): %s", agent, msg)
            return _empty_pack(agent, budget, degraded="ceiling")
        # Any OTHER OperationalError (lock/busy/transient under contention) is NOT
        # "no records": surface it degraded + logged, never a silent empty pack
        # (ticket 7df08701, real trigger = the offload deadline in server.py). The
        # narrow except above is NOT widened to pass a transient off as a ceiling.
        log.warning(
            "boot recall degraded: transient sqlite OperationalError (agent=%s): %s", agent, msg
        )
        return _empty_pack(agent, budget, degraded="sqlite")
    results = [r for r in results if r.score >= floor]
    if not results:
        return _empty_pack(agent, budget)
    return build_boot_pack(searcher.db, agent, results, budget)


class _StaticHit:
    """A minimal result row for the static boot pack (perf D), shaped like the
    Searcher results build_boot_pack expects: `.path` (the doc's ext_id, for the
    budget content lookup), `.title`, `.score`."""

    __slots__ = ("path", "score", "title")

    def __init__(self, path: str, title: str, score: float):
        self.path = path
        self.title = title
        self.score = score


def build_boot_pack(db: sqlite3.Connection, agent: str, results, budget: int | None, degraded: str | None = None) -> dict:
    """Assemble the pointer pack (budgeted or plain) from scored results.

    Shared by the dense path (boot_pointers, degraded=None) and the static shed
    fallback (boot_pointers_static, degraded='static'). `results` items expose
    `.path` (doc ext_id), `.title`, `.score`."""
    if budget is not None:
        candidates = []
        for result in results:
            row = db.execute(
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
            "degraded": degraded,
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
        "degraded": degraded,
    }


def boot_pointers_static(
    db: sqlite3.Connection,
    static_embedder,
    agent: str,
    *,
    k: int = 5,
    floor: float = 0.62,
    q: str | None = None,
    budget: int | None = None,
) -> dict:
    """DEGRADED boot recall over the STATIC (potion) vectors (perf D, task ad2ad98e).

    The shed/over-deadline fallback: an owner+record-scoped DOC-level KNN against
    vec_docs_static (same scope as the dense path, different vector space), so an
    agent under overload still gets a pointer pack in <10 ms instead of nothing. The
    pack is flagged `degraded='static'` so the prompt hook knows recall was degraded,
    not absent. Never raises — any failure (no static index, no embedder, a KNN
    error) returns the empty pack flagged 'static', exactly as the dense shed path
    returned the empty pack before.

    Owner scope uses vec_docs_static.owner (mirrors perf C's dense owner column).
    The static tables only exist when static_embed_enabled; absent → empty pack."""
    empty = _empty_pack(agent, budget, degraded="static")
    if static_embedder is None:
        return empty
    cleaned = clean_query(q) if q else ""
    owner = f"owner/{agent.lower()}"
    try:
        qblob = embed_query_blob(static_embedder, cleaned or BOOT_QUERY)
        rows = db.execute(
            """SELECT d.ext_id AS path, d.title AS title, v.distance AS distance
               FROM vec_docs_static v JOIN docs d ON d.id = v.rowid
               WHERE v.embedding MATCH ? AND k = ? AND v.source_id = 'trovex'
                 AND v.lifecycle != 'archived' AND v.lifecycle != 'pending_delete'
                 AND v.status != 'duplicate'
                 AND v.kind = 'record'
                 AND v.owner = ?
               ORDER BY v.distance""",
            (qblob, max(k if budget is None else 50, 1), owner),
        ).fetchall()
    except sqlite3.OperationalError as e:
        # No static table (feature off / not yet reindexed) or a KNN limit — the
        # shed fallback degrades to the empty pack, never a 500 on the boot path.
        log.warning("static boot recall unavailable (agent=%s): %s", agent, e)
        return empty
    results = [
        _StaticHit(r["path"], r["title"], 1.0 - r["distance"])
        for r in rows
        if (1.0 - r["distance"]) >= floor
    ]
    if not results:
        return empty
    return build_boot_pack(db, agent, results, budget, degraded="static")
