"""FastAPI app combining MCP HTTP endpoint + SSR HTML UI + JSON API."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from .mcp_app import mcp
from .state import get_state

TEMPLATES_DIR = Path(__file__).parent / "templates"

EXAMPLE_QUERIES = [
    "auth JWT", "qdrant vector", "RAG architecture",
    "deployment cron", "supabase RLS", "memory layer",
]


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


def build_app() -> FastAPI:
    app = FastAPI(title="ctx", lifespan=lifespan)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

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

        return templates.TemplateResponse(
            request, "home.html",
            {
                "total": total, "total_tokens": total_tokens, "avg_tokens": avg_tokens,
                "by_status": by_status, "last_run": last_run,
                "last_run_relative": last_run_relative,
                "recent": recent, "attention": attention, "heaviest": heaviest,
                "corpus_path": str(state.settings.project_root),
            },
        )

    @app.get("/search", response_class=HTMLResponse)
    async def search_html(request: Request, q: str = "", summary: bool = False) -> HTMLResponse:
        return _render_search(request, templates, q, summary, partial=False)

    @app.get("/search/partial", response_class=HTMLResponse)
    async def search_partial(request: Request, q: str = "", summary: bool = False) -> HTMLResponse:
        return _render_search(request, templates, q, summary, partial=True)

    @app.get("/docs", response_class=HTMLResponse)
    async def docs_page(
        request: Request,
        qpath: str = "",
        status: str = "",
        sort: str = "recent",
        limit: int = 100,
    ) -> HTMLResponse:
        ctx_data = _docs_query(qpath, status, sort, limit)
        ctx_data["total"] = get_state().searcher.db.execute(
            "SELECT COUNT(*) AS c FROM docs"
        ).fetchone()["c"]
        ctx_data.update(qpath=qpath, status=status, sort=sort, limit=limit)
        return templates.TemplateResponse(request, "docs.html", ctx_data)

    @app.get("/docs/partial", response_class=HTMLResponse)
    async def docs_partial(
        request: Request,
        qpath: str = "",
        status: str = "",
        sort: str = "recent",
        limit: int = 100,
    ) -> HTMLResponse:
        ctx_data = _docs_query(qpath, status, sort, limit)
        return templates.TemplateResponse(request, "_docs_table.html", ctx_data)

    # ── JSON API ─────────────────────────────────────────────────────

    @app.get("/api/search")
    async def api_search(
        q: str = Query(..., min_length=1),
        limit: int = Query(5, ge=1, le=20),
        summary: bool = False,
    ) -> JSONResponse:
        state = get_state()
        results = state.searcher.search(q, limit=limit)
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
    async def api_reindex() -> JSONResponse:
        state = get_state()
        stats = state.indexer.reindex(state.settings.project_root)
        return JSONResponse(stats)

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> str:
        return "ok"

    return app


def _render_search(request: Request, templates: Jinja2Templates, q: str, summary: bool, partial: bool) -> HTMLResponse:
    state = get_state()
    db = state.searcher.db
    total = db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]

    elapsed_ms = 0
    results = []
    summaries: dict[str, str] = {}
    if q.strip():
        t0 = time.perf_counter()
        results = state.searcher.search(q, limit=10)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if summary:
            for r in results:
                summaries[r.path] = state.searcher._extract_summary(r.absolute_path)

    ctx_data = {
        "q": q, "summary": summary, "total": total,
        "results": results, "summaries": summaries,
        "elapsed_ms": elapsed_ms,
        "example_queries": EXAMPLE_QUERIES,
    }
    template_name = "_results.html" if partial else "search.html"
    return templates.TemplateResponse(request, template_name, ctx_data)


def _docs_query(qpath: str, status: str, sort: str, limit: int) -> dict[str, Any]:
    state = get_state()
    db = state.searcher.db

    where = ["workspace_id = 'default'"]
    params: list[Any] = []
    if qpath:
        where.append("path LIKE ?")
        params.append(f"%{qpath}%")
    if status:
        where.append("status = ?")
        params.append(status)

    order = {
        "recent":  "mtime DESC",
        "oldest":  "mtime ASC",
        "largest": "tokens_est DESC",
        "path":    "path ASC",
    }.get(sort, "mtime DESC")

    limit = max(10, min(1000, int(limit)))

    rows = db.execute(
        f"""SELECT path, title, mtime, status, tokens_est, size_bytes
            FROM docs WHERE {' AND '.join(where)}
            ORDER BY {order} LIMIT ?""",
        (*params, limit),
    ).fetchall()
    rows = _rows_with_age(rows)
    filtered_count = db.execute(
        f"SELECT COUNT(*) AS c FROM docs WHERE {' AND '.join(where)}", params
    ).fetchone()["c"]

    return {"rows": rows, "filtered": filtered_count}
