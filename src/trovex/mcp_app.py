"""MCP server exposing the `trovex` tool.

Single tool, minimal output by design — see project README for rationale.
"""

import json
import logging
import os
import secrets
import time
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .state import get_state
from .store import TROVEX_SOURCE_ID, extract_section, replace_section
from .tokens import count_tokens as _count_tokens

log = logging.getLogger("trovex.mcp")

# The inline cumulative savings counter appended to tool output ("~1.2k tok
# saved this call · ~48k this session"). On by default; TROVEX_INLINE_SAVINGS=0
# turns it off for a caller that wants the byte-minimal raw output.
_INLINE_SAVINGS_ON = os.environ.get("TROVEX_INLINE_SAVINGS", "1") != "0"


def _with_inline(db, out: str, this_call_saved: int) -> str:
    """Append the one-line cumulative savings counter to a tool's output.

    Off via env, and skipped entirely when there's nothing to show (no savings
    this call and none banked this session) so trivial calls stay quiet. Never
    raises — the counter is a nicety, never a reason a tool fails."""
    if not _INLINE_SAVINGS_ON:
        return out
    try:
        from . import savings as _savings
        from .usage import current_session

        session = current_session.get()
        session_total = _savings.session_saved(db, session)
        if this_call_saved <= 0 and session_total <= 0:
            return out
        precision, _ = _savings.latest_precision(db)
        return out + "\n\n" + _savings.inline_counter(this_call_saved, session_total, precision)
    except Exception:  # noqa: BLE001 — the counter must never break the tool
        log.debug("inline savings counter failed", exc_info=True)
        return out


def _version_string() -> str:
    try:
        return _pkg_version("trovex")
    except PackageNotFoundError:  # source tree without an installed dist
        return "0.0.0"


# CCAR 2.2 — actionable, typed tool errors. A tool that hits a real error returns
# this compact JSON object (still a str, so the wire contract is unchanged) an
# agent can branch on, instead of a bare human sentence or a raw pydantic dump.
# `category` is one of: "validation" (the caller must fix the call — never retry
# as-is), "permission" (missing/!wrong auth), "transient" (safe to retry).
def _err(code: str, category: str, hint: str, *, retryable: bool = False) -> str:
    return json.dumps(
        {"error": {"code": code, "category": category, "isRetryable": retryable, "hint": hint}},
        ensure_ascii=False,
    )


# Allow override via env so the same code runs locally and behind Traefik.
EXTRA_HOSTS = [h for h in os.environ.get("TROVEX_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
EXTRA_ORIGINS = [
    o for o in os.environ.get("TROVEX_MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()
]

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
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
            # Docker host alias — a containerized agent / dokan job reaches the MCP (the
            # only write path) at host.docker.internal:8765. Resolves to the host only
            # inside Docker, not internet-reachable, so the rebind risk is minimal.
            "host.docker.internal",
            "host.docker.internal:*",
            # Extra hosts (e.g. a real deploy domain) come from TROVEX_MCP_ALLOWED_HOSTS —
            # never hardcode a deploy host in the public repo.
            *EXTRA_HOSTS,
        ],
        allowed_origins=[
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
            "http://host.docker.internal:*",
            *EXTRA_ORIGINS,
        ],
    ),
)
# FastMCP (mcp==1.27.1) has no `version` kwarg — it forwards name/instructions to the
# low-level Server but leaves `version` unset, which falls back to the `mcp` package's
# own version for serverInfo.version. Set it directly so clients see trovex's version.
mcp._mcp_server.version = _version_string()


ALL_SOURCES = "*"


def _pinned_source() -> str:
    """The `?source=` a project pinned on the MCP server URL in its .mcp.json.

    One trovex daemon serves every project, and it cannot see a client's cwd —
    so the scope has to travel with the connection. The client re-POSTs to the
    same URL for every call, so the param is present on each request, not just
    on initialize.
    """
    try:
        request = mcp.get_context().request_context.request
    except (LookupError, ValueError, AttributeError):
        return ""  # stdio transport, or called outside a request
    try:
        return (request.query_params.get("source") or "").strip()
    except AttributeError:
        return ""


def _resolve_source(explicit: str = "") -> str | None:
    """Which source_id to scope a query to, or None for the whole store.

    Precedence: an explicit tool argument beats the URL pin, so an agent can
    reach across projects on purpose; `*` at either level means all sources.
    Nothing set anywhere keeps the original behaviour — search everything.

    Raises ValueError on an unknown id. A typo'd .mcp.json would otherwise
    filter every result away and read as "trovex found nothing".
    """
    value = (explicit or "").strip() or _pinned_source()
    if not value or value == ALL_SOURCES:
        return None
    known = {s.id for s in get_state().settings.load_sources()} | {TROVEX_SOURCE_ID}
    if value not in known:
        raise ValueError(
            f"unknown source {value!r} — configured: {', '.join(sorted(known))} "
            f"(or {ALL_SOURCES!r} for all)"
        )
    return value


@mcp.tool()
def trovex(q: str = "", summary: bool = False, source: str = "", query: str = "") -> str:
    """Find canonical docs for a query.

    Returns one result per line: path + marker (★ canonical, ◯ plan,
    ✗ stale, ⚠ duplicate) + freshness. Set summary=True only when
    minimal output is ambiguous (adds ~150 tokens).

    Args:
        q: Natural-language query (e.g. "auth JWT", "deployment cron"). The
            alias `query` is also accepted (trovex_search/trovex_read use
            `query`) — pass either.
        summary: Include a 50-word extract per result. Default False.
        source: Restrict to one source id (project). Defaults to whatever this
            connection is pinned to; pass "*" to search every source.
        query: Alias for `q` (accepted so a caller that learned `query` from the
            other tools doesn't misfire).
    """
    import time as _time

    from .rerank import maybe_rerank
    from .usage import log_query

    from . import cache as _qcache

    q = (q or query).strip()
    if not q:
        return _err(
            "missing_query",
            "validation",
            'Pass the search text as `q` (alias `query`), e.g. trovex(q="auth jwt").',
        )

    state = get_state()
    db = state.searcher.db
    t0 = _time.perf_counter()

    try:
        scope = _resolve_source(source)
    except ValueError as e:
        return _err("unknown_source", "validation", str(e))

    # Exact-match query cache: a repeat against an unchanged corpus skips the
    # candidate search + the LLM reranker (the cost driver). corpus_version is
    # derived from the docs table, so any trovex_write/delete auto-invalidates.
    # Token metrics are replayed so usage/savings dashboards stay accurate.
    # The scope is part of the key: without it the first project to run a query
    # would serve its results to every other project asking the same thing.
    ver = _qcache.corpus_version(db)
    cache_key = q if scope is None else f"{q}\x00source={scope}"
    cached = _qcache.get(db, cache_key, summary, ver)
    if cached is not None:
        try:
            log_query(
                db,
                q,
                cached["n_results"],
                summary,
                response_tokens_est=cached["resp_tokens"],
                elapsed_ms=0,
                would_have_read_tokens=cached["whr"],
                top_result_tokens=cached["top_tokens"],
            )
        except Exception:  # noqa: BLE001 — logging must never break the tool
            log.debug("log_query (cache-hit path) failed", exc_info=True)
        cached_saved = max(0, cached["whr"] - cached["top_tokens"] - cached["resp_tokens"])
        return _with_inline(db, cached["output"], cached_saved)

    # Fetch a wider candidate pool when reranking is possible.
    candidates = state.searcher.search(q, limit=20, source_ids=[scope] if scope else None)
    pre_rerank_paths = [c.path for c in candidates]
    results, rerank_info = maybe_rerank(q, candidates, limit=5)

    out = (
        state.searcher.format_with_summary(results)
        if summary
        else state.searcher.format_minimal(results)
    )
    elapsed_ms = int((_time.perf_counter() - t0) * 1000)
    would_have_read = sum(r.tokens_est for r in results[:3])
    top_tokens = results[0].tokens_est if results else 0
    resp_tokens = _count_tokens(out)
    try:
        log_query(
            db,
            q,
            len(results),
            summary,
            response_tokens_est=resp_tokens,
            elapsed_ms=elapsed_ms,
            would_have_read_tokens=would_have_read,
            top_result_tokens=top_tokens,
            results=results,
            rerank_info=(
                {
                    "model": rerank_info.model,
                    "tokens_in": rerank_info.tokens_in,
                    "tokens_out": rerank_info.tokens_out,
                    "elapsed_ms": rerank_info.elapsed_ms,
                }
                if rerank_info
                else None
            ),
            # Only pass pre-rerank when actually reranking — otherwise it's
            # the same list and metrics would be meaningless.
            pre_rerank_paths=pre_rerank_paths if rerank_info else None,
        )
    except Exception:  # noqa: BLE001 — logging must never break the tool
        log.debug("log_query failed", exc_info=True)
    try:
        _qcache.put(
            db,
            cache_key,
            summary,
            ver,
            out,
            len(results),
            would_have_read,
            top_tokens,
            resp_tokens,
        )
    except Exception:  # noqa: BLE001 — cache is best-effort, never block the tool
        log.debug("query-cache put failed", exc_info=True)
    return _with_inline(db, out, max(0, would_have_read - top_tokens - resp_tokens))


def _authorized() -> bool:
    """Writes require the shared token via the X-TROVEX-Write-Token header.

    By default the token is auto-generated and persisted to
    ``<data_dir>/.write_token`` (see config.resolve_write_token), so a write is
    closed unless the caller presents it. An empty token only happens when
    TROVEX_ALLOW_UNAUTH_WRITES is set (opt-in open writes).
    Gates trovex_write / trovex_tag / trovex_delete."""
    from .usage import current_write_token

    tok = get_state().settings.write_token
    if not tok:
        return True
    return secrets.compare_digest(current_write_token.get() or "", tok)


_DENY = _err(
    "unauthorized",
    "permission",
    "Send the X-TROVEX-Write-Token header. The token is at <data_dir>/.write_token, "
    "or set TROVEX_WRITE_TOKEN to a shared value.",
)


def _as_taglist(v) -> list[str]:
    """Accept a list (the natural agent form) or a comma string (forgiving)."""
    if not v:
        return []
    if isinstance(v, str):
        v = v.split(",")
    return [str(t).strip() for t in v if str(t).strip()]


@mcp.tool()
def trovex_write(
    content: str,
    kind: str = "",
    doc_id: str = "",
    tags: list[str] | str | None = None,
    ticket: str = "",
    force: bool = False,
    section: str = "",
) -> str:
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
        doc_id: Omit to create; pass an existing id (full OR a unique short prefix)
            to overwrite that doc. Without `section`, the WHOLE doc is replaced.
        section: With doc_id, PATCH only this heading's section in place (read it back
            first with trovex_read(doc_id, section=…); edit; write it back here). If the
            heading isn't found this hard-errors and writes NOTHING — it never falls
            through to a whole-doc overwrite.
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
    # Resolve a full OR short/prefix doc_id to the real id when the doc EXISTS; a
    # non-resolving doc_id is kept as a client-chosen stable id for a fresh create.
    resolved = state.store.resolve_ext_id(doc_id) if doc_id else None
    if section:
        # PATCH-in-place — never fall through to a whole-doc overwrite (the data-loss bug).
        if not doc_id:
            return _err(
                "missing_doc_id",
                "validation",
                "A section write needs doc_id — pass the doc to patch. Nothing written.",
            )
        doc = state.store.get(resolved) if resolved else None
        if doc is None:
            return _err(
                "doc_not_found",
                "validation",
                f"doc '{doc_id}' not found — cannot patch section '{section}'. Nothing written.",
            )
        patched = replace_section(doc.content, section, content)
        if patched is None:
            return _err(
                "section_not_found",
                "validation",
                f"section '{section}' not found in doc {resolved} — NOTHING written (refused to "
                f'overwrite the whole doc). Read its headings first: trovex_read(doc_id="{resolved}").',
            )
        content = patched
        doc_id = resolved
        # A patch must not silently drop the doc's kind/tags → reuse them when unspecified.
        if not kind:
            kind = doc.kind or ""
        if not tags:
            tags = [t for t in doc.tags if not t.startswith("kind/")]
    elif resolved:
        doc_id = resolved  # whole-doc update via a short id → resolve to the full id
    # Write-time dedup guard: on a CREATE (no doc_id) without force, block-and-point
    # if this near-duplicates an existing canonical — stops the 'one topic, N near-copies'
    # bloat at the source (the store was 43% dupes). Updates + force bypass it.
    if not doc_id and not force:
        dup = state.store.check_duplicate(content)
        if dup:
            pct = round(dup["similarity"] * 100)
            return (
                f"⚠ Not stored — this looks like a duplicate of doc {dup['ext_id']} "
                f'("{dup["title"]}", ~{pct}% similar). One canonical doc per topic: '
                f"UPDATE that doc instead — call trovex_write again with "
                f'doc_id="{dup["ext_id"]}". For a genuinely new doc, pass force=true.'
            )
    taglist = _as_taglist(tags)
    if ticket.strip():
        taglist.append(f"ticket/{ticket.strip()}")
    return state.store.put(
        content,
        kind=kind or None,
        ext_id=doc_id or None,
        tags=taglist or None,
    )


@mcp.tool()
def trovex_tag(
    doc_id: str,
    add: list[str] | str | None = None,
    remove: list[str] | str | None = None,
) -> str:
    """Add/remove tags on a trovex-owned doc — returns the doc's new tag set.

    Args:
        doc_id: The doc to tag.
        add: Tags to add — a list (e.g. ["owner/cto", "type/report"]) or a
            comma string ("owner/cto,type/report"). Free or hierarchical "a/b/c".
        remove: Tags to remove — same list-or-comma-string form.
    """
    if not _authorized():
        return _DENY
    state = get_state()
    tags = state.store.set_tags(
        doc_id,
        add=_as_taglist(add),
        remove=_as_taglist(remove),
    )
    return ", ".join(tags) if tags else "(no tags)"


@mcp.tool()
def trovex_read(
    query: str = "", doc_id: str = "", section: str = "", full: bool = False, q: str = ""
) -> str:
    """Read a trovex-owned doc — by default returns the most relevant *passage*.

    Token-minimal by design: a query returns the single best chunk (with its
    heading breadcrumb), not the whole doc. Set full=true for the whole doc.

    Args:
        query: Natural-language query → the best-matching passage. The alias `q`
            is also accepted (the `trovex` tool uses `q`) — pass either.
        doc_id: Opaque id → that exact doc (whole, or just `section`).
        section: With doc_id, return only that heading's section.
        full: With query, return the whole best-matching doc instead of a passage.
        q: Alias for `query`.
    """
    state = get_state()
    query = (query or q).strip()
    if doc_id:
        # Accept a full OR short/prefix id (a bare short id used to return (not found)).
        resolved = state.store.resolve_ext_id(doc_id)
        doc = state.store.get(resolved) if resolved else None
        if doc is None:
            return "(not found)"
        if section:
            sec = extract_section(doc.content, section)
            return sec if sec is not None else f"(section '{section}' not found)"
        return doc.content
    if not query:
        return _err(
            "missing_input",
            "validation",
            "Provide a `query` (alias `q`) for the best passage, or a `doc_id` for an exact doc.",
        )
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
    saved = _log_retrieval(state, query, hits, out, t0)
    return _with_inline(state.searcher.db, out, saved)


@mcp.tool()
def trovex_search(
    query: str = "",
    k: int = 5,
    kind: str = "",
    tags: list[str] | str | None = None,
    source: str = "",
    q: str = "",
) -> str:
    """Search the store — returns the top K relevant *passages* (not whole docs).

    The RAG entry point: chunk-level retrieval with metadata filters. Each result
    is a passage with its heading breadcrumb + source doc id.

    Args:
        query: Natural-language query. The alias `q` is also accepted (the
            `trovex` tool uses `q`) — pass either.
        k: How many passages (default 5).
        kind: Filter by kind (e.g. "record").
        tags: Tags to filter by, any-match — a list (e.g. ["owner/cto", "kind/record"])
            or a comma string ("owner/cto,kind/record").
        source: Restrict to one source id (project). Defaults to whatever this
            connection is pinned to; pass "*" to search every source.
        q: Alias for `query`.
    """
    state = get_state()
    t0 = time.perf_counter()
    query = (query or q).strip()
    if not query:
        return _err(
            "missing_query",
            "validation",
            'Pass the search text as `query` (alias `q`), e.g. trovex_search(query="deploy cron").',
        )
    try:
        scope = _resolve_source(source)
    except ValueError as e:
        return _err("unknown_source", "validation", str(e))
    hits = state.store.search_chunks(
        query,
        limit=k,
        kind=kind or None,
        source=scope,
        tags=_as_taglist(tags) or None,
    )
    out = "\n\n———\n\n".join(_fmt_passage(h) for h in hits) if hits else "(no results)"
    saved = _log_retrieval(state, query, hits, out, t0)
    return _with_inline(state.searcher.db, out, saved)


def _fmt_passage(h: dict) -> str:
    bc = f"{h['title']} > {h['heading_path']}" if h.get("heading_path") else h["title"]
    return f"{bc}\n\n{h['content']}\n\n— trovex:{h['ext_id']}"


def _log_retrieval(state, query: str, hits: list, response: str, t0: float) -> int:
    """Log a chunk-retrieval call for usage/savings/insights and return the raw
    tokens saved for this call. Savings story: baseline = reading the whole
    parent doc(s); served = the passages (the response)."""
    try:
        from .usage import log_query

        would_have_read = sum({h["ext_id"]: h.get("doc_tokens", 0) for h in hits}.values())
        resp_tokens = _count_tokens(response)
        log_query(
            state.searcher.db,
            query,
            len(hits),
            False,
            response_tokens_est=resp_tokens,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
            would_have_read_tokens=would_have_read,
            top_result_tokens=0,
        )
        return max(0, would_have_read - resp_tokens)
    except Exception:  # noqa: BLE001 — logging must never break a tool
        log.debug("log_query (chunk path) failed", exc_info=True)
        return 0


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


# ---------------------------------------------------------------------------
# MCP resources — the doc/topic catalog, exposed at connection time.
#
# trovex IS a documentation catalog (a doc-router), but it exposed only tools:
# an agent had to call `trovex_search` even to see WHAT exists. CCAR 2.4 =
# expose the content catalog as read-only MCP RESOURCES, so an MCP client gets
# the index at connect time without an exploratory tool call — the token-
# efficiency story trovex already sells, made stronger. Strictly additive: the
# tools above are unchanged, and resources are read-only.
# ---------------------------------------------------------------------------

_CATALOG_CAP = 1000  # hard ceiling on a per-source listing (token safety)
_CATALOG_PREVIEW = 40  # docs per source shown inline in the global catalog


def _source_labels() -> dict[str, str]:
    """source id → display label, including the trovex-owned virtual source."""
    labels = {TROVEX_SOURCE_ID: "trovex (owned records)"}
    try:
        for s in get_state().settings.load_sources():
            labels[s.id] = s.label
    except Exception:  # noqa: BLE001 — a bad sources.yaml must not break the resource
        log.debug("load_sources failed while labelling catalog", exc_info=True)
    return labels


def _known_source_ids(db) -> set[str]:
    return {
        r["source_id"]
        for r in db.execute(
            "SELECT DISTINCT source_id FROM docs WHERE workspace_id = 'default'"
        ).fetchall()
    }


def _fresh_label(mtime: float, now: float) -> str:
    days = max(0.0, (now - (mtime or 0.0)) / 86400)
    return f"{int(days * 24)}h" if days < 1 else f"{int(days)}d"


def _catalog_rows(db, source: str | None, limit: int) -> list:
    """Canonical docs (never stale/duplicate), newest first, grouped by source."""
    where = ["workspace_id = 'default'", "status NOT IN ('stale', 'duplicate')"]
    params: list = []
    if source:
        where.append("source_id = ?")
        params.append(source)
    return db.execute(
        f"""SELECT ext_id, path, title, status, tokens_est, source_id, mtime
            FROM docs WHERE {" AND ".join(where)}
            ORDER BY source_id, mtime DESC LIMIT ?""",
        (*params, limit),
    ).fetchall()


def _doc_handle(row) -> str:
    """How an agent addresses this doc: an owned record by its trovex id, a
    filesystem doc by its source-relative path."""
    if row["source_id"] == TROVEX_SOURCE_ID and row["ext_id"]:
        return f"trovex:{row['ext_id']}"
    return row["path"] or (f"trovex:{row['ext_id']}" if row["ext_id"] else "?")


def _render_doc_line(row, now: float) -> str:
    from .search import STATUS_MARKER

    mark = STATUS_MARKER.get(row["status"], "★")
    title = (row["title"] or "(untitled)").strip()
    return (
        f"- {mark} {title} · ~{row['tokens_est']}tok · "
        f"{_fresh_label(row['mtime'], now)} · {_doc_handle(row)}"
    )


@mcp.resource("trovex://savings", name="savings", mime_type="text/markdown")
def savings_receipt() -> str:
    """The token-savings receipt — lifetime + last-7d tokens saved, the tokenizer
    used, and the measured routing precision the number is gated on. trovex's
    core claim, made auditable: real tokenizer, conservative counterfactual, and
    no precision-adjusted figure until an eval has measured hit@1."""
    from . import savings as _savings

    return _savings.render_receipt_md(get_state().searcher.db)


@mcp.resource("trovex://savings/{session}", name="session-savings", mime_type="text/markdown")
def savings_for_session(session: str) -> str:
    """One session's savings receipt. `session` is an Mcp-Session-Id (or an
    X-TROVEX-Session value) seen in the query log."""
    from . import savings as _savings

    return _savings.render_session_md(get_state().searcher.db, session)


@mcp.resource("trovex://sources", name="sources", mime_type="text/markdown")
def catalog_sources() -> str:
    """The configured sources (projects) and their doc counts — the top of the
    territory. Read `trovex://catalog/{source}` for one source's doc listing."""
    db = get_state().searcher.db
    labels = _source_labels()
    meta = db.execute(
        """SELECT source_id, COUNT(*) AS c FROM docs
           WHERE workspace_id = 'default' GROUP BY source_id ORDER BY c DESC"""
    ).fetchall()
    if not meta:
        return "# trovex sources\n\n(store is empty)"
    lines = ["# trovex sources", ""]
    for m in meta:
        lines.append(
            f"- **{m['source_id']}** — {labels.get(m['source_id'], m['source_id'])} · {m['c']} docs"
        )
    lines += [
        "",
        "Read `trovex://catalog` for the canonical doc index, or "
        "`trovex://catalog/{source}` for one source.",
    ]
    return "\n".join(lines)


@mcp.resource("trovex://catalog", name="catalog", mime_type="text/markdown")
def catalog_index() -> str:
    """The canonical doc/topic index across every source — what trovex can
    answer, available at connect time so an agent needn't call a search tool to
    see what exists. Grouped by source, capped preview per source (read
    `trovex://catalog/{source}` for a source's full list)."""
    db = get_state().searcher.db
    now = time.time()
    rows = _catalog_rows(db, None, _CATALOG_CAP)
    if not rows:
        return "# trovex catalog\n\n(store is empty)"
    labels = _source_labels()
    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(r["source_id"], []).append(r)
    out = [f"# trovex catalog — {len(rows)} canonical docs across {len(groups)} sources", ""]
    for sid, docs in groups.items():
        out.append(f"## {labels.get(sid, sid)} ({sid}) — {len(docs)} docs")
        out += [_render_doc_line(r, now) for r in docs[:_CATALOG_PREVIEW]]
        if len(docs) > _CATALOG_PREVIEW:
            out.append(f"- … +{len(docs) - _CATALOG_PREVIEW} more — read `trovex://catalog/{sid}`")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


@mcp.resource("trovex://catalog/{source}", name="source-catalog", mime_type="text/markdown")
def catalog_for_source(source: str) -> str:
    """One source's full canonical doc listing (capped). `source` is a source id
    from `trovex://sources` (e.g. "trovex" for owned records, "code")."""
    db = get_state().searcher.db
    now = time.time()
    labels = _source_labels()
    if source not in (set(labels) | _known_source_ids(db)):
        # Unknown id → say so, never a silent empty listing that reads as "none".
        return f"# {source}\n\n(unknown source — read `trovex://sources` for valid ids)"
    rows = _catalog_rows(db, source, _CATALOG_CAP)
    if not rows:
        return f"# {labels.get(source, source)} ({source})\n\n(no canonical docs)"
    out = [f"# {labels.get(source, source)} ({source}) — {len(rows)} canonical docs", ""]
    out += [_render_doc_line(r, now) for r in rows]
    if len(rows) >= _CATALOG_CAP:
        out.append(f"\n(capped at {_CATALOG_CAP})")
    return "\n".join(out) + "\n"
