"""FastAPI app combining MCP HTTP endpoint + SSR HTML UI + JSON API."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from . import insights as insights_mod
from . import savings as savings_mod
from .markdown import render_markdown
from .mcp_app import mcp
from .state import get_state
from .usage import UserHeaderMiddleware

TEMPLATES_DIR = Path(__file__).parent / "templates"

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


def build_app() -> FastAPI:
    # docs_url=None frees the /docs path for our own browse page.
    app = FastAPI(title="ctx", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(UserHeaderMiddleware)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.filters["avatar_color"] = _avatar_color

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
                "recent": recent, "attention": attention, "heaviest": heaviest,
                "corpus_path": str(state.settings.project_root),
                "by_user": by_user_rows,
                "recent_queries": recent_queries,
                "total_queries_7d": total_queries_7d,
                "has_any_queries": total_queries_7d > 0 or len(by_user_rows) > 0,
                "savings_totals": savings_totals,
                "sources": sources,
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
        source: str = "",
        sort: str = "recent",
        limit: int = 100,
    ) -> HTMLResponse:
        ctx_data = _docs_query(qpath, status, sort, limit, source)
        ctx_data["total"] = get_state().searcher.db.execute(
            "SELECT COUNT(*) AS c FROM docs"
        ).fetchone()["c"]
        ctx_data.update(qpath=qpath, status=status, sort=sort, limit=limit, source=source)
        return templates.TemplateResponse(request, "docs.html", ctx_data)

    @app.get("/docs/partial", response_class=HTMLResponse)
    async def docs_partial(
        request: Request,
        qpath: str = "",
        status: str = "",
        source: str = "",
        sort: str = "recent",
        limit: int = 100,
    ) -> HTMLResponse:
        ctx_data = _docs_query(qpath, status, sort, limit, source)
        return templates.TemplateResponse(request, "_docs_table.html", ctx_data)

    @app.get("/doc/{ext_id}", response_class=HTMLResponse)
    async def doc_view(request: Request, ext_id: str) -> HTMLResponse:
        """Render a ctx-owned doc's content — how humans read what agents store
        (no local file; the frontend is the human surface)."""
        doc = get_state().store.get(ext_id)
        if doc is None:
            return HTMLResponse("(not found)", status_code=404)
        body_html, toc = render_markdown(doc.content)
        return templates.TemplateResponse(
            request, "doc.html", {"doc": doc, "body_html": body_html, "toc": toc}
        )

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

    # ── Install page + hook downloads ────────────────────────────────

    @app.get("/install", response_class=HTMLResponse)
    async def install_page(request: Request) -> HTMLResponse:
        state = get_state()
        total = state.searcher.db.execute(
            "SELECT COUNT(*) AS c FROM docs"
        ).fetchone()["c"]
        return templates.TemplateResponse(request, "install.html", {"total": total})

    @app.get("/hooks/{name}", response_class=PlainTextResponse)
    async def hook_download(name: str) -> str:
        if name not in {"ctx-baseline.sh", "ctx-ambient.sh", "ctx-md-guard.sh"}:
            return ""
        repo_hooks = Path(__file__).resolve().parent.parent.parent / "deploy" / "hooks"
        for base in (Path("/home/synxadmin/.claude/hooks"), repo_hooks):
            path = base / name
            if path.exists():
                return path.read_text()
        return ""

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
    async def api_suggest(q: str = "") -> JSONResponse:
        state = get_state()
        db = state.searcher.db
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

    # Tokens from query (alphanumeric runs >= 2 chars) for inline highlighting.
    import re as _re
    highlight_terms = sorted(
        {t for t in _re.findall(r"[a-zA-Z0-9]{2,}", q.lower()) if len(t) >= 2},
        key=len, reverse=True,
    )

    ctx_data = {
        "q": q, "summary": summary, "total": total,
        "results": results, "summaries": summaries,
        "elapsed_ms": elapsed_ms,
        "example_queries": EXAMPLE_QUERIES,
        "highlight_terms": highlight_terms,
    }
    template_name = "_results.html" if partial else "search.html"
    return templates.TemplateResponse(request, template_name, ctx_data)


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
        where.append("path LIKE ?")
        params.append(f"%{qpath}%")
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
