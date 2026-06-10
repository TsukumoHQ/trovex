"""MCP server exposing the `ctx` tool.

Single tool, minimal output by design — see project README for rationale.
"""

import os
import time

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .state import get_state
from .store import CTX_SOURCE_ID, extract_section

# Allow override via env so the same code runs locally and behind Traefik.
EXTRA_HOSTS = [h for h in os.environ.get("CTX_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
EXTRA_ORIGINS = [o for o in os.environ.get("CTX_MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()]

mcp = FastMCP(
    "ctx",
    instructions=(
        "Token-efficient routing for .md docs. Use `ctx(q)` before reading "
        "any .md file to find the right one. Set summary=True only if the "
        "minimal output is ambiguous (costs ~150 extra tokens)."
    ),
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "127.0.0.1:*", "localhost:*", "[::1]:*",
            "ctx.prod.synergix.ch", "ctx.prod.synergix.ch:*",
            *EXTRA_HOSTS,
        ],
        allowed_origins=[
            "http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*",
            "https://ctx.prod.synergix.ch",
            *EXTRA_ORIGINS,
        ],
    ),
)


@mcp.tool()
def ctx(q: str, summary: bool = False) -> str:
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

    state = get_state()
    t0 = _time.perf_counter()
    # Fetch a wider candidate pool when reranking is possible.
    candidates = state.searcher.search(q, limit=20)
    pre_rerank_paths = [c.path for c in candidates]
    results, rerank_info = maybe_rerank(q, candidates, limit=5)

    out = (state.searcher.format_with_summary(results) if summary
           else state.searcher.format_minimal(results))
    elapsed_ms = int((_time.perf_counter() - t0) * 1000)
    try:
        would_have_read = sum(r.tokens_est for r in results[:3])
        top_tokens = results[0].tokens_est if results else 0
        log_query(
            state.searcher.db, q, len(results), summary,
            response_tokens_est=len(out) // 4, elapsed_ms=elapsed_ms,
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
    except Exception:
        pass  # never let logging break the tool
    return out


def _authorized() -> bool:
    """Writes require the shared token (X-CTX-Write-Token) when one is configured.
    Empty token = open (back-compat). Gates ctx_write / ctx_tag / ctx_delete."""
    from .usage import current_write_token
    tok = get_state().settings.write_token
    return (not tok) or (current_write_token.get() == tok)


_DENY = "(unauthorized — set the X-CTX-Write-Token header to the shared write token)"


@mcp.tool()
def ctx_write(content: str, kind: str = "", doc_id: str = "", tags: str = "") -> str:
    """Store a doc INSIDE ctx so every agent of every dev can read it.

    For records / memory / coordination notes (incidents, decisions, plans) —
    not code-docs that belong in a repo. The doc lives in ctx's shared store,
    so a second agent (or a second dev) reads it via `ctx_read` instead of
    re-deriving it. Returns an opaque id; pass it back to `ctx_write` (as
    doc_id) to update the same doc.

    Args:
        content: The markdown body to store.
        kind: Lifecycle hint. "record" = event-anchored, never goes stale by
            age. Default "" = a normal living doc.
        doc_id: Omit to create; pass an existing id to overwrite that doc.
        tags: Comma-separated tags (free or hierarchical "a/b/c") for organizing
            + filtering. `kind/<kind>` is auto-added.
    """
    if not _authorized():
        return _DENY
    state = get_state()
    taglist = [t.strip() for t in tags.split(",") if t.strip()]
    return state.store.put(
        content, kind=kind or None, ext_id=doc_id or None, tags=taglist or None,
    )


@mcp.tool()
def ctx_tag(doc_id: str, add: str = "", remove: str = "") -> str:
    """Add/remove tags on a ctx-owned doc — returns the doc's new tag set.

    Args:
        doc_id: The doc to tag.
        add: Comma-separated tags to add (free or hierarchical "a/b/c").
        remove: Comma-separated tags to remove.
    """
    if not _authorized():
        return _DENY
    state = get_state()
    tags = state.store.set_tags(
        doc_id,
        add=[t.strip() for t in add.split(",") if t.strip()],
        remove=[t.strip() for t in remove.split(",") if t.strip()],
    )
    return ", ".join(tags) if tags else "(no tags)"


@mcp.tool()
def ctx_read(query: str = "", doc_id: str = "", section: str = "", full: bool = False) -> str:
    """Read a ctx-owned doc — by default returns the most relevant *passage*.

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
        results = state.searcher.search(query, limit=1, source_ids=[CTX_SOURCE_ID])
        doc = state.store.get(results[0].path) if results else None
        return doc.content if doc else "(no results)"
    t0 = time.perf_counter()
    hits = state.store.search_chunks(query, limit=1)
    out = _fmt_passage(hits[0]) if hits else "(no results)"
    _log_retrieval(state, query, hits, out, t0)
    return out


@mcp.tool()
def ctx_search(query: str, k: int = 5, kind: str = "", tags: str = "") -> str:
    """Search the store — returns the top K relevant *passages* (not whole docs).

    The RAG entry point: chunk-level retrieval with metadata filters. Each result
    is a passage with its heading breadcrumb + source doc id.

    Args:
        query: Natural-language query.
        k: How many passages (default 5).
        kind: Filter by kind (e.g. "record").
        tags: Comma-separated tags to filter by (any-match).
    """
    state = get_state()
    t0 = time.perf_counter()
    hits = state.store.search_chunks(
        query, limit=k, kind=kind or None,
        tags=[t.strip() for t in tags.split(",") if t.strip()] or None,
    )
    out = "\n\n———\n\n".join(_fmt_passage(h) for h in hits) if hits else "(no results)"
    _log_retrieval(state, query, hits, out, t0)
    return out


def _fmt_passage(h: dict) -> str:
    bc = f"{h['title']} > {h['heading_path']}" if h.get("heading_path") else h["title"]
    return f"{bc}\n\n{h['content']}\n\n— ctx:{h['ext_id']}"


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
    except Exception:
        pass  # never let logging break a tool


@mcp.tool()
def ctx_delete(doc_id: str) -> str:
    """Delete a ctx-owned doc by id.

    Updates do NOT go here — to change a doc, call `ctx_write` with its
    existing doc_id (that overwrites in place). Use delete only to remove.

    Args:
        doc_id: Opaque id of the doc to remove.
    """
    if not _authorized():
        return _DENY
    state = get_state()
    return "deleted" if state.store.delete(doc_id) else "(not found)"
