"""FastAPI app combining MCP HTTP endpoint + SSR HTML UI + JSON API."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .mcp_app import mcp
from .state import get_state

TEMPLATES_DIR = Path(__file__).parent / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up state on startup so the first request isn't slow.
    get_state()
    async with mcp.session_manager.run():
        yield


def build_app() -> FastAPI:
    app = FastAPI(title="ctx", lifespan=lifespan)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Mount MCP HTTP at /mcp
    mcp_app = mcp.streamable_http_app()
    app.mount("/mcp", mcp_app)

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
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
        last_run = db.execute(
            "SELECT * FROM index_runs ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        recent = db.execute(
            "SELECT path, title, mtime, status, tokens_est FROM docs "
            "ORDER BY mtime DESC LIMIT 20"
        ).fetchall()
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "total": total,
                "total_tokens": total_tokens,
                "by_status": by_status,
                "last_run": dict(last_run) if last_run else None,
                "recent": [dict(r) for r in recent],
            },
        )

    @app.get("/search", response_class=HTMLResponse)
    async def search_html(request: Request, q: str = "", summary: bool = False) -> HTMLResponse:
        state = get_state()
        results = state.searcher.search(q, limit=10) if q else []
        summaries: dict[str, str] = {}
        if summary and results:
            for r in results:
                summaries[r.path] = state.searcher._extract_summary(r.absolute_path)
        return templates.TemplateResponse(
            request,
            "search.html",
            {"q": q, "summary": summary, "results": results, "summaries": summaries},
        )

    @app.get("/api/search")
    async def api_search(
        q: str = Query(..., min_length=1),
        limit: int = Query(5, ge=1, le=20),
        summary: bool = False,
    ) -> JSONResponse:
        state = get_state()
        results = state.searcher.search(q, limit=limit)
        return JSONResponse(
            [
                {
                    "path": r.path, "title": r.title, "score": round(r.score, 4),
                    "distance": round(r.distance, 4), "age_days": round(r.age_days, 1),
                    "status": r.status, "marker": r.marker,
                    "tokens_est": r.tokens_est, "size_bytes": r.size_bytes,
                }
                for r in results
            ]
        )

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
