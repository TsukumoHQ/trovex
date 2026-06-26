"""FastAPI app combining MCP HTTP endpoint + SSR HTML UI + JSON API."""

from __future__ import annotations

import json
import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from . import insights as insights_mod
from . import savings as savings_mod
from .boot import boot_pointers
from .capture import capture_state
from .db import like_escape
from .markdown import PYGMENTS_CSS, render_markdown
from .mcp_app import mcp
from .state import get_state
from .usage import UserHeaderMiddleware

log = logging.getLogger("trovex.server")

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Validation patterns for free-text filter params (finding 6). kind is a bare
# slug; tags allow `/` (owner/alpha scope) but nothing else exotic.
KIND_RE = r"^[A-Za-z0-9_-]+$"
TAG_RE = r"^[A-Za-z0-9_/-]+$"
_re_tag = re.compile(TAG_RE)
MAX_TAGS = 10
MAX_TAG_LEN = 50

# qpath is a path *substring* filter (finding 3): cap length and restrict to a
# sane path charset so a pathological/oversized value can't reach the LIKE query.
MAX_QPATH_LEN = 200
QPATH_RE = re.compile(r"^[A-Za-z0-9 ._/\-]+$")

# Upper bound on the content a regex-based helper (_snippet) will scan, so a very
# large doc body can't drive pathological regex cost (finding 3).
SNIPPET_SCAN_CAP = 20_000

# Hook names servable via /hooks/<name> (finding 2) — an exact allowlist.
HOOK_ALLOWLIST = frozenset({
    "trovex-md-guard.sh", "trovex-md-read-guard.sh",
    "trovex-boot.sh", "trovex-prompt.sh", "trovex-postcompact.sh",
    "trovex-sessionend.sh", "install-active-memory.sh",
})


def _safe_hook_name(name: str) -> bool:
    """A hook name is servable only if it's in the allowlist AND is a bare
    filename — no separators, parent refs, or percent-encoding (finding 2)."""
    if name not in HOOK_ALLOWLIST:
        return False
    if any(c in name for c in ("/", "\\", "%")) or ".." in name:
        return False
    return Path(name).name == name


def _redact(s: str | None, n: int = 20) -> str:
    """Truncate a user query/string before it reaches the logs (finding 8) — we
    never need the full text to debug, and it may carry sensitive content."""
    s = s or ""
    return s[:n] + "…" if len(s) > n else s


def _rate_limit(get_value):
    """slowapi limit factory reading the live setting, so a `429` class can be
    tuned (or disabled with an empty string) via TROVEX_RATE_LIMIT_* env."""
    def _value() -> str:
        v = get_value()
        # An empty setting disables the class — return a very high ceiling so the
        # decorator stays valid while effectively never tripping.
        return v or "1000000/minute"
    return _value


async def _read_json(request: Request) -> tuple[dict | None, JSONResponse | None]:
    """Parse a JSON request body, returning (body, None) or (None, 400-response).

    Replaces the unguarded ``await request.json()`` (finding 7): malformed JSON
    now yields a clean 400 instead of an unhandled 500."""
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
        log.info("rejected malformed JSON body: %s", e.__class__.__name__)
        return None, JSONResponse({"error": "invalid JSON body"}, status_code=400)
    if not isinstance(body, dict):
        return None, JSONResponse({"error": "expected a JSON object"}, status_code=400)
    return body, None


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 for over-limit clients (finding 4). Plain JSON, with a Retry hint."""
    return JSONResponse(
        {"error": "rate limit exceeded", "detail": str(exc.limit.limit)},
        status_code=429,
        headers={"Retry-After": "60"},
    )

EXAMPLE_QUERIES = [
    "auth JWT", "qdrant vector", "RAG architecture",
    "deployment cron", "supabase RLS", "memory layer",
]


def _sources_meta(db) -> list[dict]:
    """Resolved sources from the index (id + display label + doc count)."""
    rows = db.execute(
        """SELECT source_id, COUNT(*) AS c
           FROM docs WHERE workspace_id = 'default'
           GROUP BY source_id ORDER BY c DESC"""
    ).fetchall()
    return [{"id": r["source_id"], "count": r["c"]} for r in rows]


def _now() -> float:
    return time.time()


def _relative_time(seconds_ago: float) -> str:
    if seconds_ago < 60:
        return f"{int(seconds_ago)}s ago"
    if seconds_ago < 3600:
        return f"{int(seconds_ago / 60)}m ago"
    if seconds_ago < 86400:
        return f"{int(seconds_ago / 3600)}h ago"
    return f"{int(seconds_ago / 86400)}d ago"


def _snippet(content: str, n: int = 160) -> str:
    """A short plain-text preview of a doc body for the store cards."""
    import re
    text = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)  # frontmatter
    text = re.sub(r"```[\s\S]*?```", " ", text)                       # code blocks
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)            # heading marks
    text = re.sub(r"[`*_>]", "", text)                                # inline marks
    text = re.sub(r"\s+", " ", text).strip()
    return text[:n] + ("…" if len(text) > n else "")


def _write_authorized(request: Request) -> bool:
    """Mirror the MCP write gate for the HTTP /api write endpoints."""
    tok = get_state().settings.write_token
    return (not tok) or (request.headers.get("x-trovex-write-token") == tok)


def _rows_with_age(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = _now()
    out = []
    for r in rows:
        d = dict(r)
        d["age_days"] = max(0.0, (now - d.get("mtime", now)) / 86400)
        out.append(d)
    return out


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_state()  # warm up
    async with mcp.session_manager.run():
        yield


_AVATAR_PALETTE = [
    "#22c55e", "#60a5fa", "#a78bfa", "#f59e0b",
    "#ec4899", "#06b6d4", "#fb7185", "#84cc16",
]


def _avatar_color(name: str | None) -> str:
    if not name:
        return _AVATAR_PALETTE[0]
    # Sum of code points modulo palette length — deterministic + well-distributed
    h = sum(ord(c) for c in name)
    return _AVATAR_PALETTE[h % len(_AVATAR_PALETTE)]


def _highlight(text: str, terms: list[str]):
    """Escape text, then wrap query terms in <mark> (case-insensitive). Returns
    Markup so Jinja won't re-escape. Terms are alphanumeric, so matching the
    already-escaped text never splits an HTML entity."""
    import html as _html
    import re as _re
    from markupsafe import Markup
    esc = _html.escape(text or "")
    terms = [t for t in (terms or []) if t]
    if not terms:
        return Markup(esc)
    pat = _re.compile(
        "(" + "|".join(_re.escape(t) for t in sorted(terms, key=len, reverse=True)) + ")",
        _re.IGNORECASE,
    )
    return Markup(pat.sub(lambda m: '<mark class="hl">' + m.group(0) + "</mark>", esc))


def _sparkline(values: list[int], w: int = 100, h: int = 30, pad: int = 3) -> dict | None:
    """Normalise a series into SVG point strings for a stretched (preserveAspectRatio=none) sparkline.

    Returns {line, area, w, h} or None when there's nothing to draw. The line is a
    polyline of the values; the area is the same closed back to the baseline for a fill.
    """
    if not values or max(values) <= 0:
        return None
    vmax = max(values)
    inner = h - 2 * pad
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = pad + (i * (w - 2 * pad) / (n - 1) if n > 1 else (w - 2 * pad) / 2)
        y = h - pad - (v / vmax) * inner
        pts.append((round(x, 1), round(y, 1)))
    line = " ".join(f"{x},{y}" for x, y in pts)
    area = f"{pad},{h - pad} {line} {round(pts[-1][0], 1)},{h - pad}"
    return {"line": line, "area": area, "w": w, "h": h}


def build_app() -> FastAPI:
    # docs_url=None frees the /docs path for our own browse page.
    app = FastAPI(title="trovex", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(UserHeaderMiddleware)

    # Per-IP rate limiting (finding 4). The limiter + its in-memory window live on
    # this app instance, so each build_app() starts clean (test isolation). Limits
    # are read live from settings, so TROVEX_RATE_LIMIT_* tunes them per class.
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    search_limit = limiter.limit(_rate_limit(lambda: get_state().settings.rate_limit_search))
    write_limit = limiter.limit(_rate_limit(lambda: get_state().settings.rate_limit_write))

    # `limit` ceilings sourced from settings (finding 9), captured at build time.
    cfg = get_state().settings
    search_max = cfg.search_limit_max

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.filters["avatar_color"] = _avatar_color
    templates.env.filters["highlight"] = _highlight

    # Mount MCP HTTP transport at /mcp
    app.mount("/mcp", mcp.streamable_http_app())

    # ── HTML pages ───────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        state = get_state()
        db = state.searcher.db

        total = db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
        total_tokens = db.execute(
            "SELECT COALESCE(SUM(tokens_est), 0) AS t FROM docs"
        ).fetchone()["t"]
        avg_tokens = (total_tokens // total) if total else 0
        by_status = {
            r["status"]: r["c"]
            for r in db.execute(
                "SELECT status, COUNT(*) AS c FROM docs GROUP BY status"
            ).fetchall()
        }
        last_run_row = db.execute(
            "SELECT * FROM index_runs ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        last_run = dict(last_run_row) if last_run_row else None
        last_run_relative = (
            _relative_time(_now() - last_run["ts"]) if last_run else "never"
        )
        # The store indexes on write — the reindex (index_runs) is retired, so
        # surface the latest write instead of stale added/updated counts.
        lw = db.execute(
            "SELECT MAX(mtime) AS m FROM docs WHERE source_id = 'trovex'"
        ).fetchone()
        last_write_relative = _relative_time(_now() - lw["m"]) if lw and lw["m"] else "never"

        recent = _rows_with_age(db.execute(
            """SELECT path, title, mtime, status, tokens_est, size_bytes
               FROM docs ORDER BY mtime DESC LIMIT 12"""
        ).fetchall())

        attention = _rows_with_age(db.execute(
            """SELECT path, title, mtime, status, tokens_est
               FROM docs
               WHERE status IN ('stale', 'duplicate')
               ORDER BY tokens_est DESC LIMIT 6"""
        ).fetchall())

        heaviest = _rows_with_age(db.execute(
            """SELECT path, title, mtime, status, tokens_est, size_bytes
               FROM docs ORDER BY tokens_est DESC LIMIT 8"""
        ).fetchall())

        # MCP usage (last 7 days) — joined with savings
        since_7d = _now() - 7 * 86400
        by_user = db.execute(
            """SELECT user, COUNT(*) AS queries,
                      COALESCE(SUM(response_tokens_est),0) AS resp_tokens,
                      COALESCE(SUM(would_have_read_tokens),0) AS whr,
                      COALESCE(SUM(top_result_tokens),0) AS topr,
                      MAX(ts) AS last_seen
               FROM mcp_queries WHERE ts >= ?
               GROUP BY user ORDER BY queries DESC""",
            (since_7d,),
        ).fetchall()
        by_user_rows = []
        for r in by_user:
            d = dict(r)
            d["saved"] = max(0, d["whr"] - d["topr"] - d["resp_tokens"])
            d["ratio"] = (d["saved"] / d["whr"]) if d["whr"] else 0.0
            d["last_seen_label"] = _relative_time(_now() - d["last_seen"])
            by_user_rows.append(d)
        savings_totals = savings_mod.totals(db, since_7d)

        # 7-day savings trend (sparkline) + honest week-over-week delta.
        # daily_series buckets by UTC midnight, so 14d → ~15 buckets; take the
        # last 7 as "this week" and the 7 before as "last week".
        series14 = savings_mod.daily_series(db, _now() - 14 * 86400, _now())
        savings_series = [d["saved"] for d in series14[-7:]]
        saved_this = sum(savings_series)
        saved_prev = sum(d["saved"] for d in series14[-14:-7]) if len(series14) >= 8 else 0
        saved_delta_pct = ((saved_this - saved_prev) / saved_prev) if saved_prev else None
        savings_spark = _sparkline(
            savings_series, w=state.settings.sparkline_w, h=state.settings.sparkline_h
        )

        # Activity this week — writes touch mtime, so these are "written / updated",
        # not net-new growth. Labelled as such in the UI (no fake +growth delta).
        docs_written_7d = db.execute(
            "SELECT COUNT(*) AS c FROM docs WHERE mtime >= ?", (since_7d,)
        ).fetchone()["c"]

        recent_queries = [
            {**dict(r), "age_label": _relative_time(_now() - r["ts"])}
            for r in db.execute(
                """SELECT ts, user, query, n_results, summary, elapsed_ms
                   FROM mcp_queries ORDER BY ts DESC LIMIT 15"""
            ).fetchall()
        ]
        total_queries_7d = db.execute(
            "SELECT COUNT(*) AS c FROM mcp_queries WHERE ts >= ?", (since_7d,)
        ).fetchone()["c"]

        sources = _sources_meta(db)
        return templates.TemplateResponse(
            request, "home.html",
            {
                "total": total, "total_tokens": total_tokens, "avg_tokens": avg_tokens,
                "by_status": by_status, "last_run": last_run,
                "last_run_relative": last_run_relative,
                "last_write_relative": last_write_relative,
                "recent": recent, "attention": attention, "heaviest": heaviest,
                "corpus_path": str(state.settings.project_root),
                "by_user": by_user_rows,
                "recent_queries": recent_queries,
                "total_queries_7d": total_queries_7d,
                "has_any_queries": total_queries_7d > 0 or len(by_user_rows) > 0,
                "savings_totals": savings_totals,
                "savings_spark": savings_spark,
                "saved_delta_pct": saved_delta_pct,
                "docs_written_7d": docs_written_7d,
                "sources": sources,
            },
        )

    @app.get("/search", response_class=HTMLResponse)
    @search_limit
    async def search_html(request: Request, q: str = "", summary: bool = False,
                          tag: list[str] = Query(default=[]), kind: str = "",
                          sort: str = "relevance", page: int = 1) -> HTMLResponse:
        # Dedicated search page over the trovex store (hybrid vector + BM25), not a
        # redirect to /store — search is trovex's core verb and deserves its own surface.
        return _render_search(request, templates, q, summary, partial=False,
                              tags=tag, kind=kind, sort=sort, page=page)

    @app.get("/search/partial", response_class=HTMLResponse)
    async def search_partial(request: Request, q: str = "", summary: bool = False,
                             tag: list[str] = Query(default=[]), kind: str = "",
                             sort: str = "relevance", page: int = 1) -> HTMLResponse:
        return _render_search(request, templates, q, summary, partial=True,
                              tags=tag, kind=kind, sort=sort, page=page)

    @app.get("/docs")
    async def docs_page() -> RedirectResponse:
        # /docs was the file-router table view; full-trovex made it redundant with
        # /store (same docs, worse presentation). Redirect to the one surface.
        return RedirectResponse("/store", status_code=308)

    @app.get("/docs/partial", response_class=HTMLResponse)
    async def docs_partial(
        request: Request,
        qpath: str = "",
        status: str = "",
        source: str = "",
        sort: str = "recent",
        limit: int = 100,
    ) -> HTMLResponse:
        trovex_data = _docs_query(qpath, status, sort, limit, source)
        return templates.TemplateResponse(request, "_docs_table.html", trovex_data)

    @app.get("/doc/{ext_id}", response_class=HTMLResponse)
    async def doc_view(request: Request, ext_id: str) -> HTMLResponse:
        """Render a trovex-owned doc's content — how humans read what agents store
        (no local file; the frontend is the human surface)."""
        doc = get_state().store.get(ext_id)
        if doc is None:
            from html import escape
            return HTMLResponse(
                "<!doctype html><html lang=en><head><meta charset=utf-8>"
                "<title>doc not found · trovex</title>"
                "<meta name=viewport content='width=device-width, initial-scale=1'>"
                "<style>body{background:#0b0d0e;color:#e6e6e6;font:15px/1.6 ui-monospace,"
                "Menlo,monospace;display:grid;place-items:center;min-height:100vh;margin:0;"
                "text-align:center}a{color:#22c55e}.c{max-width:34rem;padding:2rem}"
                ".m{color:#8a9199}code{color:#e6e6e6}</style></head><body><div class=c>"
                "<h1 style='font-size:1.25rem;margin:0 0 .5rem'>doc not found</h1>"
                f"<p class=m>No trovex doc with id <code>{escape(ext_id)}</code>. "
                "It may have been deleted, or the link is stale.</p>"
                "<p><a href='/search'>search the store</a> · "
                "<a href='/store'>browse all docs</a></p></div></body></html>",
                status_code=404,
            )
        body_html, toc = render_markdown(doc.content)
        return templates.TemplateResponse(
            request, "doc.html",
            {"doc": doc, "body_html": body_html, "toc": toc, "pygments_css": PYGMENTS_CSS},
        )

    @app.delete("/api/doc/{ext_id}")
    @write_limit
    async def api_doc_delete(ext_id: str, request: Request) -> JSONResponse:
        """Delete a trovex-owned doc. Updates go through trovex_write (same id)."""
        if not _write_authorized(request):
            return _unauthorized()
        ok = get_state().store.delete(ext_id)
        return JSONResponse({"deleted": ok}, status_code=200 if ok else 404)

    @app.get("/store", response_class=HTMLResponse)
    async def store_page(request: Request, tag: str = "", kind: str = "",
                         collection: str = "", q: str = "", page: int = 1) -> HTMLResponse:
        """The trovex-owned doc store — browse + quick title/text filter. Semantic
        search lives on /search (this `q` is a lightweight view filter, paginated
        like the rest of the browse)."""
        state = get_state()
        store = state.store
        now = _now()
        f_tag, f_kind = tag, kind
        if collection:
            cf = store.get_collection(collection) or {}
            f_tag = cf.get("tag", f_tag)
            f_kind = cf.get("kind", f_kind)
        page = max(1, page)
        per = state.settings.store_page_size

        def card(d, snippet):
            return {
                "ext_id": d.ext_id, "title": d.title, "kind": d.kind,
                "status": d.status, "tokens_est": d.tokens_est, "tags": d.tags,
                "age_days": max(0.0, (now - d.mtime) / 86400), "snippet": snippet,
            }

        qf = q.strip() or None
        total = store.count_docs(tag=f_tag or None, kind=f_kind or None, q=qf)
        docs = store.list_docs(tag=f_tag or None, kind=f_kind or None, q=qf,
                               limit=per, offset=(page - 1) * per)
        items = [card(d, _snippet(d.content)) for d in docs]
        pages = (total + per - 1) // per

        facets, other_tags = store.tags_by_facet()
        return templates.TemplateResponse(
            request, "store.html",
            {
                "items": items, "total": total,
                "total_tokens": sum(i["tokens_est"] for i in items),
                "facets": facets, "other_tags": other_tags,
                "collections": store.list_collections(),
                "active_tag": tag, "active_kind": kind, "active_collection": collection,
                "q": q, "page": page, "pages": pages,
            },
        )

    @app.get("/api/collections")
    async def api_collections() -> JSONResponse:
        return JSONResponse(get_state().store.list_collections())

    @app.post("/api/collections")
    @write_limit
    async def api_collection_create(request: Request) -> JSONResponse:
        if not _write_authorized(request):
            return _unauthorized()
        body, err = await _read_json(request)
        if err:
            return err
        name = (body.get("name") or "").strip()
        if not name:
            return JSONResponse({"error": "name required"}, status_code=400)
        flt = {k: v for k, v in (("tag", body.get("tag")), ("kind", body.get("kind"))) if v}
        get_state().store.create_collection(name, flt)
        return JSONResponse({"ok": True, "name": name, "filter": flt})

    @app.delete("/api/collections/{name}")
    @write_limit
    async def api_collection_delete(name: str, request: Request) -> JSONResponse:
        if not _write_authorized(request):
            return _unauthorized()
        get_state().store.delete_collection(name)
        return JSONResponse({"deleted": True})

    @app.get("/api/doc/{ext_id}/versions")
    async def api_doc_versions(ext_id: str) -> JSONResponse:
        return JSONResponse(get_state().store.list_versions(ext_id))

    @app.post("/api/doc/{ext_id}/restore")
    @write_limit
    async def api_doc_restore(ext_id: str, request: Request) -> JSONResponse:
        if not _write_authorized(request):
            return JSONResponse({"error": "unauthorized"}, status_code=403)
        body, err = await _read_json(request)
        if err:
            return err
        try:
            version_id = int(body.get("version_id", 0))
        except (TypeError, ValueError):
            return JSONResponse({"error": "version_id must be an integer"}, status_code=400)
        ok = get_state().store.restore_version(ext_id, version_id)
        return JSONResponse({"restored": ok}, status_code=200 if ok else 404)

    @app.post("/api/doc/{ext_id}/tags")
    @write_limit
    async def api_doc_tags(ext_id: str, request: Request) -> JSONResponse:
        if not _write_authorized(request):
            return _unauthorized()
        body, err = await _read_json(request)
        if err:
            return err
        tags = get_state().store.set_tags(
            ext_id,
            add=[t.strip() for t in (body.get("add") or "").split(",") if t.strip()],
            remove=[t.strip() for t in (body.get("remove") or "").split(",") if t.strip()],
        )
        return JSONResponse({"tags": tags})

    # ── JSON API ─────────────────────────────────────────────────────

    @app.get("/api/search")
    @search_limit
    async def api_search(
        request: Request,
        q: str = Query(..., min_length=1, max_length=500),
        limit: int = Query(5, ge=1, le=search_max),
        summary: bool = False,
        kind: str | None = Query(
            None, max_length=MAX_TAG_LEN, pattern=KIND_RE,
            description="filter to one doc kind, e.g. 'record'",
        ),
        tags: str | None = Query(None, description="comma-separated tags; any-match scope"),
    ) -> JSONResponse:
        state = get_state()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        if tag_list:
            # Validate tags (finding 6): bounded count + slug shape, reject malformed.
            if len(tag_list) > MAX_TAGS:
                return JSONResponse(
                    {"error": f"too many tags (max {MAX_TAGS})"}, status_code=422
                )
            for t in tag_list:
                if len(t) > MAX_TAG_LEN or not _re_tag.match(t):
                    return JSONResponse(
                        {"error": f"invalid tag: {_redact(t)!r}"}, status_code=422
                    )
        results = state.searcher.search(q, limit=limit, kind=kind, tags=tag_list)
        return JSONResponse([
            {
                "path": r.path, "title": r.title,
                "score": round(r.score, 4), "distance": round(r.distance, 4),
                "age_days": round(r.age_days, 1),
                "status": r.status, "marker": r.marker,
                "tokens_est": r.tokens_est, "size_bytes": r.size_bytes,
            }
            for r in results
        ])

    @app.get("/api/boot")
    @search_limit
    async def api_boot(
        request: Request,
        agent: str = Query(..., min_length=1, max_length=MAX_TAG_LEN),
        k: int = Query(5, ge=1, le=search_max),
        floor: float = Query(0.62, ge=0.0, le=1.0),
        q: str | None = Query(None, max_length=500, description="override the generic boot query"),
    ) -> JSONResponse:
        """Active-memory recall: the agent's own records as a ~80-token pointer
        pack (RFC 330e7d43, step 2). Read-only; empty when nothing clears
        scope (owner/<agent> + kind=record) + floor."""
        return JSONResponse(
            boot_pointers(get_state().searcher, agent, k=k, floor=floor, q=q)
        )

    @app.post("/api/capture")
    @write_limit
    async def api_capture(request: Request) -> JSONResponse:
        """Active-memory capture (RFC 330e7d43, step 3): upsert an agent's
        current-state record from a free summary (PostCompact's compact_summary,
        no LLM). Distil-from-transcript is step 4. Write-gated."""
        if not _write_authorized(request):
            return _unauthorized()
        body, err = await _read_json(request)
        if err:
            return err
        agent = (body.get("agent") or "").strip()
        if not agent:
            return JSONResponse({"captured": False, "reason": "no agent"}, status_code=400)
        return JSONResponse(
            capture_state(
                get_state().store,
                agent,
                body.get("summary") or "",
                transcript=body.get("transcript") or "",
                reason=(body.get("reason") or "postcompact"),
            )
        )

    @app.get("/api/map")
    async def api_map(canonical_only: bool = True) -> JSONResponse:
        """The 'map' of the store: titles + tags + status, no content. Cheap enough
        to inject at session start so an agent *sees the territory* and knows what
        it can ask trovex for — turning an unknown-unknown into a queryable target."""
        store = get_state().store
        docs = store.list_docs(limit=2000)
        if canonical_only:
            docs = [d for d in docs if d.status not in ("stale", "duplicate")]
        return JSONResponse({
            "count": len(docs),
            "docs": [
                {"id": d.ext_id, "title": d.title, "kind": d.kind,
                 "status": d.status, "tags": d.tags}
                for d in docs
            ],
        })

    @app.get("/api/stats")
    async def api_stats() -> JSONResponse:
        state = get_state()
        db = state.searcher.db
        total = db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
        total_tokens = db.execute(
            "SELECT COALESCE(SUM(tokens_est), 0) AS t FROM docs"
        ).fetchone()["t"]
        by_status = {
            r["status"]: r["c"]
            for r in db.execute(
                "SELECT status, COUNT(*) AS c FROM docs GROUP BY status"
            ).fetchall()
        }
        return JSONResponse(
            {"total": total, "total_tokens": total_tokens, "by_status": by_status}
        )

    @app.post("/api/reindex")
    @write_limit
    async def api_reindex(request: Request) -> JSONResponse:
        # Write-gated like the other mutating endpoints (finding 2): a full
        # reindex is an admin/token-only operation, not anonymous.
        if not _write_authorized(request):
            return _unauthorized()
        state = get_state()
        stats = state.indexer.reindex(state.settings.project_root)
        return JSONResponse(stats)

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> str:
        return "ok"

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request) -> HTMLResponse:
        from . import backup as backup_mod
        state = get_state()
        db = state.searcher.db
        db_path = state.settings.data_dir / "trovex.db"
        return templates.TemplateResponse(request, "settings.html", {
            "db_size": db_path.stat().st_size if db_path.exists() else 0,
            "doc_count": db.execute(
                "SELECT COUNT(*) AS c FROM docs WHERE source_id='trovex'").fetchone()["c"],
            "chunk_count": db.execute("SELECT COUNT(*) AS c FROM chunks").fetchone()["c"],
            "auth_on": bool(state.settings.write_token),
            "backups": backup_mod.list_backups(state.settings.data_dir),
        })

    @app.get("/api/backups")
    async def api_backups() -> JSONResponse:
        from . import backup as backup_mod
        return JSONResponse(backup_mod.list_backups(get_state().settings.data_dir))

    @app.post("/api/backup")
    @write_limit
    async def api_backup(request: Request) -> JSONResponse:
        if not _write_authorized(request):
            return _unauthorized()
        from . import backup as backup_mod
        state = get_state()
        dest = backup_mod.make_backup(state.settings.data_dir / "trovex.db", state.settings.data_dir)
        return JSONResponse({"ok": True, "file": dest.name})

    # ── Install page + hook downloads ────────────────────────────────

    @app.get("/install", response_class=HTMLResponse)
    async def install_page(request: Request) -> HTMLResponse:
        state = get_state()
        total = state.searcher.db.execute(
            "SELECT COUNT(*) AS c FROM docs"
        ).fetchone()["c"]
        return templates.TemplateResponse(request, "install.html", {"total": total})

    @app.get("/api/write-token")
    async def api_write_token(request: Request) -> JSONResponse:
        """Hand the auto-generated write token to a SAME-MACHINE browser so the
        local UI can issue writes without the operator copying it by hand. Refused
        for non-loopback clients, so a network-exposed instance never leaks it.
        Returns no token when writes are open (TROVEX_ALLOW_UNAUTH_WRITES)."""
        if not _is_loopback(request):
            return _unauthorized()
        return JSONResponse({"token": get_state().settings.write_token})

    @app.get("/hooks/{name}", response_class=PlainTextResponse)
    async def hook_download(name: str) -> PlainTextResponse:
        # Allowlist + traversal/encoding check before touching the filesystem.
        if not _safe_hook_name(name):
            return PlainTextResponse("not found", status_code=404)
        # Serve from the configurable hooks dir first (TROVEX_HOOKS_DIR; defaults
        # to ~/.claude/hooks, no hardcoded user), then the bundled repo copy.
        hooks_dir = get_state().settings.hooks_dir.expanduser()
        repo_hooks = Path(__file__).resolve().parent.parent.parent / "deploy" / "hooks"
        for base in (hooks_dir, repo_hooks):
            try:
                base_resolved = base.resolve()
                path = (base_resolved / name).resolve()
            except OSError:
                continue
            # Defence in depth: the resolved file must stay inside its base dir.
            if base_resolved not in path.parents:
                continue
            if path.is_file():
                return PlainTextResponse(path.read_text())
        return PlainTextResponse("not found", status_code=404)

    # ── Usage page ───────────────────────────────────────────────────

    @app.get("/usage", response_class=HTMLResponse)
    async def usage_page(
        request: Request,
        user: str = "",
        days: int = 7,
    ) -> HTMLResponse:
        from datetime import datetime, timezone

        state = get_state()
        db = state.searcher.db
        days = max(1, min(90, int(days)))
        since = _now() - days * 86400

        where = ["ts >= ?"]
        params: list[Any] = [since]
        if user:
            where.append("user = ?")
            params.append(user)

        queries = db.execute(
            f"""SELECT ts, user, query, n_results, summary,
                       response_tokens_est, elapsed_ms
                FROM mcp_queries
                WHERE {' AND '.join(where)}
                ORDER BY ts DESC LIMIT 500""",
            params,
        ).fetchall()

        users = [r["user"] for r in db.execute(
            "SELECT DISTINCT user FROM mcp_queries ORDER BY user"
        ).fetchall()]

        now = _now()
        now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
        today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        yesterday_start = today_start - 86400

        # Group by time bucket
        buckets: dict[str, list[dict]] = {"Today": [], "Yesterday": [], "Earlier": []}
        for r in queries:
            d = dict(r)
            d["age_label"] = _relative_time(now - d["ts"])
            d["time_label"] = datetime.fromtimestamp(d["ts"], tz=timezone.utc).strftime("%H:%M")
            if d["ts"] >= today_start:
                buckets["Today"].append(d)
            elif d["ts"] >= yesterday_start:
                buckets["Yesterday"].append(d)
            else:
                buckets["Earlier"].append(d)

        # Per-user summary across the window
        per_user_summary = db.execute(
            f"""SELECT user, COUNT(*) AS queries,
                      COALESCE(SUM(response_tokens_est),0) AS resp_tokens,
                      COALESCE(AVG(elapsed_ms),0) AS avg_elapsed_ms,
                      MAX(ts) AS last_seen
               FROM mcp_queries WHERE {' AND '.join(where)}
               GROUP BY user ORDER BY queries DESC""",
            params,
        ).fetchall()
        per_user = []
        for r in per_user_summary:
            d = dict(r)
            d["last_seen_label"] = _relative_time(now - d["last_seen"])
            # Sparkline data: 24 buckets over the window
            sb = _sparkline_buckets(db, d["user"], since, now, 24)
            d["sparkline"] = sb
            per_user.append(d)

        # Top-level stats
        total_queries = len(queries)
        total_tokens = sum(r["response_tokens_est"] for r in queries)
        avg_elapsed = (
            sum(r["elapsed_ms"] for r in queries) / total_queries
            if total_queries else 0
        )
        unique_users = len({r["user"] for r in queries})

        return templates.TemplateResponse(
            request, "usage.html",
            {
                "buckets": buckets,
                "per_user": per_user,
                "users": users, "user": user, "days": days,
                "total_queries": total_queries,
                "total_tokens": total_tokens,
                "avg_elapsed": int(avg_elapsed),
                "unique_users": unique_users,
            },
        )

    @app.get("/insights", response_class=HTMLResponse)
    async def insights_page(request: Request, days: int = 7) -> HTMLResponse:
        state = get_state()
        db = state.searcher.db
        days = max(1, min(90, int(days)))
        since = _now() - days * 86400
        now = _now()

        top_q = insights_mod.top_queries(db, since)
        failed = [
            {**r, "age_label": _relative_time(now - r["ts"])}
            for r in insights_mod.failed_queries(db, since)
        ]
        repeated = [
            {**r,
             "last_label": _relative_time(now - r["last_ts"]),
             "span_label": _relative_time(r["last_ts"] - r["first_ts"]) if r["last_ts"] > r["first_ts"] else "instant"}
            for r in insights_mod.repeated_queries(db, since)
        ]
        most_returned = insights_mod.most_returned_paths(db, since)
        dead = [
            {**r, "age_days": max(0.0, (now - r["mtime"]) / 86400)}
            for r in insights_mod.dead_docs(db, since)
        ]
        heatmap = insights_mod.hour_heatmap(db, since)
        rerank = insights_mod.rerank_stats(db, since)
        divergence = insights_mod.rerank_divergence(db, since)
        return templates.TemplateResponse(
            request, "insights.html",
            {
                "days": days,
                "top_q": top_q, "failed": failed, "repeated": repeated,
                "most_returned": most_returned, "dead": dead,
                "heatmap": heatmap, "rerank": rerank,
                "divergence": divergence,
            },
        )

    @app.get("/api/suggest")
    async def api_suggest(q: str = Query("", max_length=200)) -> JSONResponse:
        state = get_state()
        db = state.searcher.db
        # Log the query truncated (finding 8) — never the full user text.
        log.debug("suggest q=%r", _redact(q))
        return JSONResponse(insights_mod.suggest_queries(db, q))

    @app.get("/savings", response_class=HTMLResponse)
    async def savings_page(request: Request, days: int = 7) -> HTMLResponse:
        state = get_state()
        db = state.searcher.db
        days = max(1, min(90, int(days)))
        since = _now() - days * 86400
        totals = savings_mod.totals(db, since)
        per_user = savings_mod.per_user(db, since)
        daily = savings_mod.daily_series(db, since, _now())
        top_q = savings_mod.top_queries(db, since, limit=10)
        return templates.TemplateResponse(
            request, "savings.html",
            {
                "totals": totals, "per_user": per_user,
                "daily": daily, "top_queries": top_q,
                "days": days,
            },
        )

    @app.get("/api/savings")
    async def api_savings(days: int = 7) -> JSONResponse:
        state = get_state()
        db = state.searcher.db
        days = max(1, min(90, int(days)))
        since = _now() - days * 86400
        return JSONResponse(savings_mod.totals(db, since))

    @app.get("/api/usage")
    async def api_usage(days: int = 7) -> JSONResponse:
        state = get_state()
        db = state.searcher.db
        since = _now() - max(1, min(90, int(days))) * 86400
        by_user = db.execute(
            """SELECT user, COUNT(*) AS queries,
                      COALESCE(SUM(response_tokens_est),0) AS resp_tokens,
                      MAX(ts) AS last_seen
               FROM mcp_queries WHERE ts >= ?
               GROUP BY user ORDER BY queries DESC""",
            (since,),
        ).fetchall()
        return JSONResponse([
            {"user": r["user"], "queries": r["queries"],
             "response_tokens_est": r["resp_tokens"],
             "last_seen": r["last_seen"]}
            for r in by_user
        ])

    return app


def _render_search(request: Request, templates: Jinja2Templates, q: str, summary: bool,
                   partial: bool, *, tags: list[str] | None = None, kind: str = "",
                   sort: str = "relevance", page: int = 1) -> HTMLResponse:
    from urllib.parse import urlencode

    state = get_state()
    store = state.store
    total = store.db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
    now = _now()
    tags = [t for t in (tags or []) if t]
    page = max(1, page)
    per = state.settings.search_page_size

    def _u(**over) -> str:
        """Build a /search URL from current state with overrides (q/kind/sort/tags/page)."""
        params: list[tuple[str, str]] = []
        if over.get("q", q):
            params.append(("q", over.get("q", q)))
        if over.get("kind", kind):
            params.append(("kind", over.get("kind", kind)))
        ss = over.get("sort", sort)
        if ss and ss != "relevance":
            params.append(("sort", ss))
        for t in over.get("tags", tags):
            params.append(("tag", t))
        pg = over.get("page", 1)
        if pg and pg > 1:
            params.append(("page", str(pg)))
        return "/search?" + urlencode(params) if params else "/search"

    elapsed_ms = 0
    pool: list[dict[str, Any]] = []
    facet_counts: dict[str, int] = {}
    if q.strip():
        t0 = time.perf_counter()
        # Over-fetch chunks (filtered by kind + any-of tags), collapse to the
        # best-scoring chunk per doc so one doc with many sections doesn't flood.
        hits = store.search_chunks(q, limit=240, kind=kind or None, tags=tags or None)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        max_score = hits[0]["score"] if hits else 1.0  # ranked desc → first is max
        seen: set[str] = set()
        for h in hits:
            ext_id = h["ext_id"]
            if ext_id in seen:
                continue
            d = store.get(ext_id)
            if not d:
                continue
            seen.add(ext_id)
            pool.append({
                "ext_id": ext_id,
                "title": h["title"] or ext_id,
                "kind": h["kind"],
                "status": d.status,
                "tags": d.tags,
                "section": h["heading_path"],
                "snippet": (h["content"] or "").strip()[:280],
                "tokens_est": h["doc_tokens"],
                "age_days": max(0.0, (now - d.mtime) / 86400),
                "score": (h["score"] / max_score) if max_score else 0.0,
            })
            for t in d.tags:
                facet_counts[t] = facet_counts.get(t, 0) + 1
            if len(pool) >= 60:
                break
        if sort == "recent":
            pool.sort(key=lambda r: r["age_days"])
        elif sort == "tokens":
            pool.sort(key=lambda r: r["tokens_est"], reverse=True)
        # relevance = keep the fused-score order

    total_results = len(pool)
    pages = max(1, (total_results + per - 1) // per)
    page = min(page, pages)
    results = pool[(page - 1) * per: page * per]

    # Facets: tags present in the result set (not already selected), by count.
    facets = [
        {"tag": t, "count": c, "url": _u(tags=tags + [t], page=1)}
        for t, c in sorted(facet_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        if t not in tags
    ][:12]
    active_tags = [
        {"tag": t, "url": _u(tags=[x for x in tags if x != t], page=1)} for t in tags
    ]

    # Tokens from query (alphanumeric runs >= 2 chars) for inline highlighting.
    import re as _re
    highlight_terms = sorted(
        {t for t in _re.findall(r"[a-zA-Z0-9]{2,}", q.lower()) if len(t) >= 2},
        key=len, reverse=True,
    )

    trovex_data = {
        "q": q, "summary": summary, "total": total,
        "results": results,
        "elapsed_ms": elapsed_ms,
        "example_queries": EXAMPLE_QUERIES,
        "highlight_terms": highlight_terms,
        "tags": tags, "kind": kind, "sort": sort,
        "facets": facets, "active_tags": active_tags,
        "total_results": total_results, "page": page, "pages": pages,
        "prev_url": _u(page=page - 1) if page > 1 else "",
        "next_url": _u(page=page + 1) if page < pages else "",
        "clear_url": _u(tags=[], kind="", page=1),
        "has_filters": bool(tags or kind),
    }
    template_name = "_results.html" if partial else "search.html"
    return templates.TemplateResponse(request, template_name, trovex_data)


def _sparkline_buckets(db, user: str, since: float, until: float, n: int) -> list[int]:
    """Return counts per bucket. Used to draw inline activity sparklines."""
    width = (until - since) / n
    rows = db.execute(
        """SELECT ts FROM mcp_queries
           WHERE user = ? AND ts >= ? AND ts <= ?""",
        (user, since, until),
    ).fetchall()
    out = [0] * n
    for r in rows:
        idx = min(n - 1, int((r["ts"] - since) / width))
        out[idx] += 1
    return out


def _docs_query(qpath: str, status: str, sort: str, limit: int,
                source: str = "") -> dict[str, Any]:
    state = get_state()
    db = state.searcher.db

    where = ["workspace_id = 'default'"]
    params: list[Any] = []
    if qpath:
        where.append("path LIKE ? ESCAPE '\\'")
        params.append(f"%{like_escape(qpath)}%")
    if status:
        where.append("status = ?")
        params.append(status)
    if source:
        where.append("source_id = ?")
        params.append(source)

    order = {
        "recent":  "mtime DESC",
        "oldest":  "mtime ASC",
        "largest": "tokens_est DESC",
        "path":    "path ASC",
    }.get(sort, "mtime DESC")

    limit = max(10, min(1000, int(limit)))

    rows = db.execute(
        f"""SELECT path, title, mtime, status, tokens_est, size_bytes, source_id
            FROM docs WHERE {' AND '.join(where)}
            ORDER BY {order} LIMIT ?""",
        (*params, limit),
    ).fetchall()
    rows = _rows_with_age(rows)
    filtered_count = db.execute(
        f"SELECT COUNT(*) AS c FROM docs WHERE {' AND '.join(where)}", params
    ).fetchone()["c"]

    return {"rows": rows, "filtered": filtered_count, "sources_meta": _sources_meta(db)}
