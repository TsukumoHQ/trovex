"""MCP server exposing the `trovex` tool.

Single tool, minimal output by design — see project README for rationale.
"""

import logging
import os
import time

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .state import get_state
from .store import TROVEX_SOURCE_ID, extract_section

log = logging.getLogger("trovex.mcp")

# Allow override via env so the same code runs locally and behind Traefik.
EXTRA_HOSTS = [h for h in os.environ.get("TROVEX_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
EXTRA_ORIGINS = [o for o in os.environ.get("TROVEX_MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()]

mcp = FastMCP(
    "trovex",
    instructions=(
        "Token-efficient routing for .md docs. Use `trovex(q)` before reading "
        "any .md file to find the right one. Set summary=True only if the "
        "minimal output is ambiguous (costs ~150 extra tokens)."
    ),
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "127.0.0.1:*", "localhost:*", "[::1]:*",
            # Docker host alias — a containerized agent / dokan job reaches the MCP (the
            # only write path) at host.docker.internal:8765. Resolves to the host only
            # inside Docker, not internet-reachable, so the rebind risk is minimal.
            "host.docker.internal", "host.docker.internal:*",
            # Extra hosts (e.g. a real deploy domain) come from TROVEX_MCP_ALLOWED_HOSTS —
            # never hardcode a deploy host in the public repo.
            *EXTRA_HOSTS,
        ],
        allowed_origins=[
            "http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*",
            "http://host.docker.internal:*",
            *EXTRA_ORIGINS,
        ],
    ),
)


@mcp.tool()
def trovex(q: str, summary: bool = False) -> str:
    """Find canonical docs for a query.

    Returns one result per line: path + marker (★ canonical, ◯ plan,
    ✗ stale, ⚠ duplicate) + freshness. Set summary=True only when
    minimal output is ambiguous (adds ~150 tokens).

    Args:
        q: Natural-language query (e.g. "auth JWT", "deployment cron").
        summary: Include a 50-word extract per result. Default False.
    """
    import time as _time

    from .rerank import maybe_rerank
    from .usage import log_query

    from . import cache as _qcache

    state = get_state()
    db = state.searcher.db
    t0 = _time.perf_counter()

    # Exact-match query cache: a repeat against an unchanged corpus skips the
    # candidate search + the LLM reranker (the cost driver). corpus_version is
    # derived from the docs table, so any trovex_write/delete auto-invalidates.
    # Token metrics are replayed so usage/savings dashboards stay accurate.
    ver = _qcache.corpus_version(db)
    cached = _qcache.get(db, q, summary, ver)
    if cached is not None:
        try:
            log_query(
                db, q, cached["n_results"], summary,
                response_tokens_est=cached["resp_tokens"], elapsed_ms=0,
                would_have_read_tokens=cached["whr"],
                top_result_tokens=cached["top_tokens"],
            )
        except Exception:  # noqa: BLE001 — logging must never break the tool
            log.debug("log_query (cache-hit path) failed", exc_info=True)
        return cached["output"]

    # Fetch a wider candidate pool when reranking is possible.
    candidates = state.searcher.search(q, limit=20)
    pre_rerank_paths = [c.path for c in candidates]
    results, rerank_info = maybe_rerank(q, candidates, limit=5)

    out = (state.searcher.format_with_summary(results) if summary
           else state.searcher.format_minimal(results))
    elapsed_ms = int((_time.perf_counter() - t0) * 1000)
    would_have_read = sum(r.tokens_est for r in results[:3])
    top_tokens = results[0].tokens_est if results else 0
    resp_tokens = len(out) // 4
    try:
        log_query(
            db, q, len(results), summary,
            response_tokens_est=resp_tokens, elapsed_ms=elapsed_ms,
            would_have_read_tokens=would_have_read,
            top_result_tokens=top_tokens,
            results=results,
            rerank_info=(
                {
                    "model": rerank_info.model,
                    "tokens_in": rerank_info.tokens_in,
                    "tokens_out": rerank_info.tokens_out,
                    "elapsed_ms": rerank_info.elapsed_ms,
                } if rerank_info else None
            ),
            # Only pass pre-rerank when actually reranking — otherwise it's
            # the same list and metrics would be meaningless.
            pre_rerank_paths=pre_rerank_paths if rerank_info else None,
        )
    except Exception:  # noqa: BLE001 — logging must never break the tool
        log.debug("log_query failed", exc_info=True)
    try:
        _qcache.put(db, q, summary, ver, out, len(results),
                    would_have_read, top_tokens, resp_tokens)
    except Exception:  # noqa: BLE001 — cache is best-effort, never block the tool
        log.debug("query-cache put failed", exc_info=True)
    return out


def _authorized() -> bool:
    """Writes require the shared token via the X-TROVEX-Write-Token header.

    By default the token is auto-generated and persisted to
    ``<data_dir>/.write_token`` (see config.resolve_write_token), so a write is
    closed unless the caller presents it. An empty token only happens when
    TROVEX_ALLOW_UNAUTH_WRITES is set (opt-in open writes).
    Gates trovex_write / trovex_tag / trovex_delete."""
    from .usage import current_write_token
    tok = get_state().settings.write_token
    return (not tok) or (current_write_token.get() == tok)


_DENY = (
    "(unauthorized — send the X-TROVEX-Write-Token header. The token is at "
    "<data_dir>/.write_token, or set TROVEX_WRITE_TOKEN to a shared value.)"
)


def _as_taglist(v) -> list[str]:
    """Accept a list (the natural agent form) or a comma string (forgiving)."""
    if not v:
        return []
    if isinstance(v, str):
        v = v.split(",")
    return [str(t).strip() for t in v if str(t).strip()]


@mcp.tool()
def trovex_write(content: str, kind: str = "", doc_id: str = "",
              tags: list[str] | None = None, ticket: str = "", force: bool = False) -> str:
    """Store a doc INSIDE trovex so every agent of every dev can read it.

    For records / memory / coordination notes (incidents, decisions, plans) —
    not code-docs that belong in a repo. The doc lives in trovex's shared store,
    so a second agent (or a second dev) reads it via `trovex_read` instead of
    re-deriving it. Returns an opaque id; pass it back to `trovex_write` (as
    doc_id) to update the same doc.

    ONE CANONICAL DOC PER TOPIC (that's trovex's whole pitch). On a CREATE, if the
    content near-duplicates an existing canonical doc, this BLOCKS and points you at
    it — UPDATE that doc (pass its id as doc_id) instead of creating a near-copy.
    Pass force=true only for a genuinely new doc. (Updates — doc_id set — never block.)

    Args:
        content: The markdown body to store.
        kind: Lifecycle hint. "record" = event-anchored, never goes stale by
            age. Default "" = a normal living doc.
        doc_id: Omit to create; pass an existing id to overwrite that doc.
        force: On create, override the near-duplicate block to store a new doc anyway.
        tags: List of tags (free or hierarchical "a/b/c"), e.g.
            ["type/report", "owner/cto", "domain/accounting"]. `kind/<kind>`
            is auto-added. A comma string is also accepted.
        ticket: Optional work-item id (Linear "SYN-1389", GitHub "#123", …).
            Stored as a `ticket/<id>` tag so the doc links back to its tracker
            item — tracker-agnostic, no schema change. Find everything tied to
            it via `trovex_search(tags=["ticket/<id>"])`.
    """
    if not _authorized():
        return _DENY
    state = get_state()
    # Write-time dedup guard: on a CREATE (no doc_id) without force, block-and-point
    # if this near-duplicates an existing canonical — stops the 'one topic, N near-copies'
    # bloat at the source (the store was 43% dupes). Updates + force bypass it.
    if not doc_id and not force:
        dup = state.store.check_duplicate(content)
        if dup:
            pct = round(dup["similarity"] * 100)
            return (
                f"⚠ Not stored — this looks like a duplicate of doc {dup['ext_id']} "
                f"(\"{dup['title']}\", ~{pct}% similar). One canonical doc per topic: "
                f"UPDATE that doc instead — call trovex_write again with "
                f"doc_id=\"{dup['ext_id']}\". For a genuinely new doc, pass force=true."
            )
    taglist = _as_taglist(tags)
    if ticket.strip():
        taglist.append(f"ticket/{ticket.strip()}")
    return state.store.put(
        content, kind=kind or None, ext_id=doc_id or None,
        tags=taglist or None,
    )


@mcp.tool()
def trovex_tag(doc_id: str, add: list[str] | None = None,
            remove: list[str] | None = None) -> str:
    """Add/remove tags on a trovex-owned doc — returns the doc's new tag set.

    Args:
        doc_id: The doc to tag.
        add: List of tags to add (free or hierarchical "a/b/c").
        remove: List of tags to remove.
    """
    if not _authorized():
        return _DENY
    state = get_state()
    tags = state.store.set_tags(
        doc_id, add=_as_taglist(add), remove=_as_taglist(remove),
    )
    return ", ".join(tags) if tags else "(no tags)"


@mcp.tool()
def trovex_read(query: str = "", doc_id: str = "", section: str = "", full: bool = False) -> str:
    """Read a trovex-owned doc — by default returns the most relevant *passage*.

    Token-minimal by design: a query returns the single best chunk (with its
    heading breadcrumb), not the whole doc. Set full=true for the whole doc.

    Args:
        query: Natural-language query → the best-matching passage.
        doc_id: Opaque id → that exact doc (whole, or just `section`).
        section: With doc_id, return only that heading's section.
        full: With query, return the whole best-matching doc instead of a passage.
    """
    state = get_state()
    if doc_id:
        doc = state.store.get(doc_id)
        if doc is None:
            return "(not found)"
        if section:
            sec = extract_section(doc.content, section)
            return sec if sec is not None else f"(section '{section}' not found)"
        return doc.content
    if not query.strip():
        return "(provide query or doc_id)"
    if full:
        results = state.searcher.search(query, limit=1, source_ids=[TROVEX_SOURCE_ID])
        doc = state.store.get(results[0].path) if results else None
        return doc.content if doc else "(no results)"
    t0 = time.perf_counter()
    hits = state.store.search_chunks(query, limit=1)
    if hits:
        h = hits[0]
        # small-to-big: match the chunk, return its full parent section.
        section = state.store.section_text(h["doc_id"], h["heading_path"]) or h["content"]
        out = _fmt_passage({**h, "content": section})
    else:
        out = "(no results)"
    _log_retrieval(state, query, hits, out, t0)
    return out


@mcp.tool()
def trovex_search(query: str, k: int = 5, kind: str = "",
               tags: list[str] | None = None) -> str:
    """Search the store — returns the top K relevant *passages* (not whole docs).

    The RAG entry point: chunk-level retrieval with metadata filters. Each result
    is a passage with its heading breadcrumb + source doc id.

    Args:
        query: Natural-language query.
        k: How many passages (default 5).
        kind: Filter by kind (e.g. "record").
        tags: List of tags to filter by (any-match). A comma string also works.
    """
    state = get_state()
    t0 = time.perf_counter()
    hits = state.store.search_chunks(
        query, limit=k, kind=kind or None,
        tags=_as_taglist(tags) or None,
    )
    out = "\n\n———\n\n".join(_fmt_passage(h) for h in hits) if hits else "(no results)"
    _log_retrieval(state, query, hits, out, t0)
    return out


def _fmt_passage(h: dict) -> str:
    bc = f"{h['title']} > {h['heading_path']}" if h.get("heading_path") else h["title"]
    return f"{bc}\n\n{h['content']}\n\n— trovex:{h['ext_id']}"


def _log_retrieval(state, query: str, hits: list, response: str, t0: float) -> None:
    """Log a chunk-retrieval call for usage/savings/insights. Savings story:
    baseline = reading the whole parent doc(s); served = the passages."""
    try:
        from .usage import log_query
        would_have_read = sum({h["ext_id"]: h.get("doc_tokens", 0) for h in hits}.values())
        log_query(
            state.searcher.db, query, len(hits), False,
            response_tokens_est=len(response) // 4,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
            would_have_read_tokens=would_have_read, top_result_tokens=0,
        )
    except Exception:  # noqa: BLE001 — logging must never break a tool
        log.debug("log_query (chunk path) failed", exc_info=True)


@mcp.tool()
def trovex_delete(doc_id: str) -> str:
    """Delete a trovex-owned doc by id.

    Updates do NOT go here — to change a doc, call `trovex_write` with its
    existing doc_id (that overwrites in place). Use delete only to remove.

    Args:
        doc_id: Opaque id of the doc to remove.
    """
    if not _authorized():
        return _DENY
    state = get_state()
    return "deleted" if state.store.delete(doc_id) else "(not found)"
