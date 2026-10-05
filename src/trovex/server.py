"""FastAPI app combining MCP HTTP endpoint + SSR HTML UI + JSON API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import sqlite3
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

from . import capacity
from . import graphview
from . import insights as insights_mod
from . import offload
from . import savings as savings_mod
from . import usearch_index
from .boot import BOOT_QUERY, boot_pointers, clean_query
from .capture import capture_state
from .db import WAL_CHECKPOINT_POLL_SEC, like_escape, run_wal_checkpoint_timer
from .markdown import PYGMENTS_CSS, render_markdown
from .mcp_app import mcp
from .state import get_state
from .usage import UserHeaderMiddleware

log = logging.getLogger("trovex.server")

# /api/boot recall deadline (audit Q5): the fleet's hot path uses a short,
# boot-specific timeout instead of the 30s default, so a slow retrieval sheds
# to boot's empty pack rather than holding an offload worker for 30s and
# feeding the orphaned-worker pile-up that ends in a watchdog restart. The
# prompt hook itself abandons at ~2s.
_BOOT_OFFLOAD_TIMEOUT_SEC = float(os.environ.get("TROVEX_BOOT_TIMEOUT_SEC", "2.5"))

TEMPLATES_DIR = Path(__file__).parent / "templates"
# The React savings-receipt bundle — a SEPARATE build from the marketing site.
# trovex-frontend builds it to web/dist-receipt (base '/receipt/', via
# `npm run build:receipt`); web/dist is the public marketing build and must NOT
# be served here (it would expose the dashboard under a wrong base). Mounted at
# /receipt only when present — see create_app.
WEB_DIST = Path(__file__).parent.parent.parent / "web" / "dist-receipt"
# The React knowledge-graph SPA ("the codebase's brain") — another SEPARATE
# build (base '/graph/', via `npm run build:graph` -> web/dist-graph). Mounted
# at /graph only when present, exactly like /receipt, so a build-less tree
# still boots.
GRAPH_DIST = Path(__file__).parent.parent.parent / "web" / "dist-graph"

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
HOOK_ALLOWLIST = frozenset(
    {
        "trovex-md-guard.sh",
        "trovex-md-read-guard.sh",
        "trovex-boot.sh",
        "trovex-prompt.sh",
        "trovex-postcompact.sh",
        "trovex-sessionend.sh",
        "install-active-memory.sh",
    }
)


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


async def _offloaded(fn, *args, pool: str = "recall", **kwargs) -> tuple[Any, JSONResponse | None]:
    """Run a store/indexer call via the offload pool, returning (result, None)
    or (None, 504-response) on timeout — the uniform wedge-class-2 error shape
    for every route below, instead of letting a bounded-but-still-an-error
    TimeoutError surface as a bare unhandled 500. `pool="heavy"` routes writes /
    re-embeds to the heavy pool so they never occupy a recall worker (task
    b02389c2 AC3); reads default to the recall pool."""
    runner = offload.off_loop_heavy if pool == "heavy" else offload.off_loop
    try:
        return await runner(fn, *args, **kwargs), None
    except TimeoutError:
        return None, JSONResponse(
            {"error": f"{getattr(fn, '__name__', 'call')} timed out"}, status_code=504
        )


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 for over-limit clients (finding 4). Plain JSON, with a Retry hint."""
    return JSONResponse(
        {"error": "rate limit exceeded", "detail": str(exc.limit.limit)},
        status_code=429,
        headers={"Retry-After": "60"},
    )


EXAMPLE_QUERIES = [
    "auth JWT",
    "qdrant vector",
    "RAG architecture",
    "deployment cron",
    "supabase RLS",
    "memory layer",
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

    # Only the head of the doc matters for a 160-char preview; capping the input
    # keeps the regex passes O(cap), not O(doc size) (finding 3).
    content = (content or "")[:SNIPPET_SCAN_CAP]
    text = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)  # frontmatter
    text = re.sub(r"```[\s\S]*?```", " ", text)  # code blocks
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)  # heading marks
    text = re.sub(r"[`*_>]", "", text)  # inline marks
    text = re.sub(r"\s+", " ", text).strip()
    return text[:n] + ("…" if len(text) > n else "")


def _write_authorized(request: Request) -> bool:
    """Mirror the MCP write gate for the HTTP /api write endpoints. The token is
    auto-generated + persisted by default (fail-closed); empty only under the
    TROVEX_ALLOW_UNAUTH_WRITES opt-in. See config.resolve_write_token."""
    tok = get_state().settings.write_token
    if not tok:
        return True
    return secrets.compare_digest(request.headers.get("x-trovex-write-token") or "", tok)


_UNAUTH_MSG = (
    "unauthorized — send the X-TROVEX-Write-Token header (token at "
    "<data_dir>/.write_token, or set TROVEX_WRITE_TOKEN)"
)


def _unauthorized() -> JSONResponse:
    return JSONResponse({"error": _UNAUTH_MSG}, status_code=403)


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}

_NON_LOOPBACK_BIND_MSG = (
    "write-token bootstrap is disabled while trovex serve is bound to a non-loopback "
    "interface — read the token from <data_dir>/.write_token instead (or set "
    "TROVEX_WRITE_TOKEN)"
)


def _is_loopback(request: Request) -> bool:
    """True when the TRANSPORT PEER address is the same machine. Never consults
    X-Forwarded-For or any other header — a header is attacker-controlled input,
    the peer address is not. Used to bootstrap the local browser UI with the
    auto-generated write token without exposing it to remote clients."""
    client = request.client
    return bool(client and client.host in _LOOPBACK_HOSTS)


def _server_bound_loopback() -> bool:
    """True when TROVEX_HOST (the interface trovex serve was launched on — see
    cli._run_server) is itself a loopback address.

    Defense in depth (strix vuln-0001): a non-loopback bind (TROVEX_HOST=0.0.0.0,
    the fleet-host / dokan-container case) can have traffic that genuinely
    originated off-machine but still arrives with request.client.host == 127.0.0.1
    — macOS Docker Desktop's vpnkit terminates a container's connection to
    host.docker.internal locally and re-establishes it, so the host-side peer
    address is legitimately loopback even though the true origin was a container.
    _is_loopback's peer check can't tell those apart, so when the server itself
    isn't loopback-bound the write-token bootstrap route must not answer AT ALL,
    regardless of peer — same-machine tooling reads <data_dir>/.write_token instead."""
    return get_state().settings.host in _LOOPBACK_HOSTS


def _rows_with_age(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = _now()
    out = []
    for r in rows:
        d = dict(r)
        d["age_days"] = max(0.0, (now - d.get("mtime", now)) / 86400)
        out.append(d)
    return out


def _maybe_enqueue_rebuild_vec(state) -> bool:
    """task 6851d755: an embed_model/dim change on a NON-EMPTY store never
    runs _migrate_embed_dim's inline wipe (see db.py) — it enqueues the
    rebuild_vec job instead, which swaps without ever blocking a writer for
    the expensive (re-embedding) part. Called once at startup; the caller is
    responsible for having already started the applier so it can pick the
    job up. A standalone function (not inlined in lifespan) so it's testable
    without the MCP session manager, which can only ever run() once per
    process. Returns True iff a job was enqueued this call."""
    try:
        from . import db as db_mod
        from . import index_jobs

        dim = state.settings.resolved_embed_dim()
        if db_mod.rebuild_vec_needed(state.indexer.db, dim, state.settings.embed_model):
            log.warning(
                "embed_model/dim changed on a non-empty store — enqueueing rebuild_vec "
                "(model=%r dim=%d)",
                state.settings.embed_model,
                dim,
            )
            index_jobs.enqueue(state.indexer.db, state.index_jobs_lock, "rebuild_vec")
            state.applier.notify()
            return True
        return False
    except Exception:  # noqa: BLE001 — must never block startup
        log.exception("rebuild_vec startup check failed")
        return False


def _warmup(state) -> bool:
    """Prime the lazy, first-call-only costs BEFORE the server accepts traffic
    (perf A, task 62c53f35): the ONNX forward pass + model page-in, the sqlite
    query plan + cold DB pages on the boot path, and the one-time tiktoken load.

    The first request after every (watchdog) restart otherwise paid 0.5-2 s for
    these on the hot path. Standalone + returning True-on-success so it's testable
    without the MCP session manager. Best-effort: warm-up must NEVER block or fail
    startup, so any error degrades to an un-warmed (but correct) server."""
    try:
        from .tokens import count_tokens

        # ONNX forward pass + model weights paged in — the query (int8) session on
        # the boot hot path, and the fp32 doc session for the first write.
        query_embedder = state.query_embedder or state.embedder
        next(iter(query_embedder.embed([BOOT_QUERY])))
        if state.embedder is not query_embedder:
            next(iter(state.embedder.embed([BOOT_QUERY])))
        # Full boot recall path warm (query embed cache, sqlite KNN plan, cold
        # pages). Unknown agent → empty pack, zero writes, just exercises the read.
        boot_pointers(state.searcher, "__warmup__")
        # One-time tiktoken encoding load.
        count_tokens(BOOT_QUERY)
        return True
    except Exception:  # noqa: BLE001 — warm-up must never block startup
        log.debug("startup warm-up failed", exc_info=True)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = get_state()  # warm up
    # Prime first-call costs (embed/KNN/tiktoken) before serving so the first
    # request after a restart isn't the one that pays them (perf A).
    _warmup(state)
    # task 4c89b89a: build the HNSW index for every flagged partition BEFORE
    # serving — a request landing before the first reindex would otherwise see
    # an empty index and silently fall back to sqlite-vec (safe, but defeats
    # the point of flagging the partition in the first place).
    if state.settings.usearch_partitions and usearch_index.available():
        dim = state.settings.resolved_embed_dim()
        for src in state.settings.usearch_partitions:
            usearch_index.rebuild_partition(state.indexer.db, "vec_docs", src, dim)
            usearch_index.rebuild_partition(state.indexer.db, "vec_chunks", src, dim)
    # Start the reindex-queue applier (task dab8766b): recovers any job a prior
    # crash left 'processing', then drains index_jobs on its own thread for the
    # life of the process. /api/reindex only ever enqueues from here on.
    state.applier.start()
    _maybe_enqueue_rebuild_vec(state)
    # Retention (finding 5): drop query-log rows older than the configured window
    # so the local DB doesn't grow unbounded and old (potentially sensitive)
    # query text isn't retained forever.
    try:
        from .usage import purge_old_queries

        deleted = purge_old_queries(state.searcher.db, state.settings.query_retention_days)
        if deleted:
            log.info("purged %d query-log rows past retention", deleted)
    except Exception:  # noqa: BLE001 — retention must never block startup
        log.debug("query-log retention purge failed", exc_info=True)
    # Wedge-class-2 self-heal (see offload.py): every off_loop caller now runs
    # on the same bounded pool, so if it's ever fully saturated by orphaned
    # (past-deadline) calls for TROVEX_WATCHDOG_SATURATION_SEC, restart rather
    # than stay wedged indefinitely — automates the manual `launchctl kickstart`
    # mitigation. Cancelled on shutdown along with everything else in `async with`.
    watchdog_task = asyncio.create_task(offload.run_watchdog())
    # task 20afcaf7 r4: the sole owner of file-shrinking WAL checkpoints, off
    # the request path entirely — see db.run_wal_checkpoint_timer's docstring.
    wal_checkpoint_task = asyncio.create_task(
        run_wal_checkpoint_timer(
            state.store.db, state.settings.data_dir / "trovex.db", WAL_CHECKPOINT_POLL_SEC
        )
    )
    # Served-empty-store guard (incident 35c0631e, audit Q9): refresh the
    # staleness flag once now so the first probe is accurate, then keep it fresh
    # in the background — /healthz only ever reads the flag, never the DB.
    try:
        await offload.off_loop_heavy(_refresh_health, state, timeout=5.0)
    except Exception:  # noqa: BLE001 — a startup refresh miss must not block serving
        pass
    health_task = asyncio.create_task(_health_refresh_timer(state, _HEALTH_REFRESH_SEC))
    # Background query-log writer (task b02389c2 AC2): drains /api/boot's enqueued
    # rows on its own connection, off the request path and off the offload pool.
    from .usage import start_query_log_writer, stop_query_log_writer

    start_query_log_writer(state.settings.data_dir)
    try:
        async with mcp.session_manager.run():
            yield
    finally:
        watchdog_task.cancel()
        wal_checkpoint_task.cancel()
        health_task.cancel()
        stop_query_log_writer()
        state.applier.stop()


_AVATAR_PALETTE = [
    "#22c55e",
    "#60a5fa",
    "#a78bfa",
    "#f59e0b",
    "#ec4899",
    "#06b6d4",
    "#fb7185",
    "#84cc16",
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


# How often the background refresher recomputes the served-empty-store
# staleness flag (audit Q9): /healthz itself stays LOOP-ONLY and only reads the
# flag, so a probe never takes an offload worker or queues behind recall — the
# refresh is one short, infrequent worker use, not one per probe.
_HEALTH_REFRESH_SEC = 15.0


def _refresh_health(state: Any) -> None:
    """Recompute AppState.health OFF the request path (the refresher's worker).
    stale=True exactly when the served connection reads 0/None docs while the DB
    file on disk holds rows (incident 35c0631e: a frozen snapshot served empty
    while still answering 200)."""
    served, on_disk = _healthz_store_counts(state)
    if not served and on_disk > 0:
        state.health = {
            "stale": True,
            "detail": f"stale store: served {served!r} but db file has {on_disk}",
        }
    else:
        state.health = {"stale": False, "detail": "ok"}


async def _health_refresh_timer(state: Any, interval_sec: float) -> None:
    """Refresh the health flag periodically on the offload pool (same pattern as
    the WAL checkpoint timer) — never on the /healthz probe path."""
    while True:
        try:
            await offload.off_loop_heavy(_refresh_health, state, timeout=5.0)
        except Exception:  # noqa: BLE001 — a refresh miss must never crash the timer
            pass
        await asyncio.sleep(interval_sec)


def _healthz_store_counts(state: Any) -> tuple[int | None, int]:
    """(served, on_disk) for the /healthz staleness guard, run OFF the event loop.

    served = docs count via the long-lived served connection (None if that read
    raised). on_disk is read ONLY when served is 0/None, through a FRESH
    connection (_docs_on_disk) so a frozen-snapshot server can't vouch for its
    own stale read; it stays 0 otherwise so a healthy server never pays for the
    second open."""
    try:
        served: int | None = state.searcher.db.execute(
            "SELECT COUNT(*) AS c FROM docs"
        ).fetchone()["c"]
    except Exception:  # noqa: BLE001 — a dead/locked served conn is unhealthy, not a 500
        served = None
    on_disk = 0
    if not served:  # 0 or None
        on_disk = _docs_on_disk(state.settings.data_dir / "trovex.db")
    return served, on_disk


def _docs_on_disk(db_path: Path) -> int:
    """Ground-truth docs count, read through a FRESH short-lived connection — never
    the long-lived served connection (incident 35c0631e), so a server frozen on a
    stale snapshot can't hide behind its own stale read. query_only so this never
    writes or checkpoints. Best-effort: -1 when the file can't be read, so a genuine
    read error can't masquerade as a populated disk and bounce a healthy server."""
    try:
        if not db_path.exists():
            return -1
        conn = sqlite3.connect(str(db_path), timeout=2.0)
        try:
            conn.execute("PRAGMA query_only=ON")
            return conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — a probe hiccup must never bounce a healthy server
        return -1


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

    # Serve the React savings-receipt SPA same-origin with /api/savings* so the
    # view needs no CORS and no separate host. Best-effort: registered only when
    # the built bundle exists (web/dist-receipt), so a source/installed tree
    # without a build still boots. html=True gives SPA fallback to index.html.
    if WEB_DIST.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/receipt", StaticFiles(directory=str(WEB_DIST), html=True), name="receipt")

    # Serve the knowledge-graph SPA same-origin with /api/graph, same contract
    # as /receipt: registered only when web/dist-graph exists, html=True for SPA
    # fallback. Private local view (noindex) — reads the running index.
    if GRAPH_DIST.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/graph", StaticFiles(directory=str(GRAPH_DIST), html=True), name="graph")

    # ── HTML pages ───────────────────────────────────────────────────

    def _compute_home_context(db: sqlite3.Connection, state: Any) -> dict:
        total = db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
        total_tokens = db.execute("SELECT COALESCE(SUM(tokens_est), 0) AS t FROM docs").fetchone()[
            "t"
        ]
        avg_tokens = (total_tokens // total) if total else 0
        by_status = {
            r["status"]: r["c"]
            for r in db.execute("SELECT status, COUNT(*) AS c FROM docs GROUP BY status").fetchall()
        }
        last_run_row = db.execute("SELECT * FROM index_runs ORDER BY ts DESC LIMIT 1").fetchone()
        last_run = dict(last_run_row) if last_run_row else None
        last_run_relative = _relative_time(_now() - last_run["ts"]) if last_run else "never"
        # The store indexes on write — the reindex (index_runs) is retired, so
        # surface the latest write instead of stale added/updated counts.
        lw = db.execute("SELECT MAX(mtime) AS m FROM docs WHERE source_id = 'trovex'").fetchone()
        last_write_relative = _relative_time(_now() - lw["m"]) if lw and lw["m"] else "never"

        recent = _rows_with_age(
            db.execute(
                """SELECT path, title, mtime, status, tokens_est, size_bytes
               FROM docs ORDER BY mtime DESC LIMIT 12"""
            ).fetchall()
        )

        attention = _rows_with_age(
            db.execute(
                """SELECT path, title, mtime, status, tokens_est
               FROM docs
               WHERE status IN ('stale', 'duplicate')
               ORDER BY tokens_est DESC LIMIT 6"""
            ).fetchall()
        )

        heaviest = _rows_with_age(
            db.execute(
                """SELECT path, title, mtime, status, tokens_est, size_bytes
               FROM docs ORDER BY tokens_est DESC LIMIT 8"""
            ).fetchall()
        )

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
        return {
            "total": total,
            "total_tokens": total_tokens,
            "avg_tokens": avg_tokens,
            "by_status": by_status,
            "last_run": last_run,
            "last_run_relative": last_run_relative,
            "last_write_relative": last_write_relative,
            "recent": recent,
            "attention": attention,
            "heaviest": heaviest,
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
        }

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        """Wedge-class-2 (task 20afcaf7 r3): this HTML dashboard did ~10 db calls
        inline on the event loop, same bug class as /api/map and /api/stats —
        a slow one (e.g. blocked behind a forced WAL checkpoint) would freeze
        /healthz along with it. off_loop like every route below."""
        state = get_state()
        context, timeout_resp = await _offloaded(_compute_home_context, state.searcher.db, state)
        if timeout_resp is not None:
            return timeout_resp
        return templates.TemplateResponse(request, "home.html", context)

    @app.get("/search", response_class=HTMLResponse)
    @search_limit
    async def search_html(
        request: Request,
        q: str = Query("", max_length=500),
        summary: bool = False,
        tag: list[str] = Query(default=[]),
        kind: str = "",
        sort: str = "relevance",
        page: int = 1,
    ) -> HTMLResponse:
        # Dedicated search page over the trovex store (hybrid vector + BM25), not a
        # redirect to /store — search is trovex's core verb and deserves its own surface.
        return await _render_search(
            request, templates, q, summary, partial=False, tags=tag, kind=kind, sort=sort, page=page
        )

    @app.get("/search/partial", response_class=HTMLResponse)
    @search_limit
    async def search_partial(
        request: Request,
        q: str = Query("", max_length=500),
        summary: bool = False,
        tag: list[str] = Query(default=[]),
        kind: str = "",
        sort: str = "relevance",
        page: int = 1,
    ) -> HTMLResponse:
        # Same embed+fusion cost as /search (a paid embed call per hit) — MUST carry the
        # same rate-limit + q length cap, else an anon client loops it to burn OpenAI spend.
        return await _render_search(
            request, templates, q, summary, partial=True, tags=tag, kind=kind, sort=sort, page=page
        )

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
    ):
        # Validate the path filter (finding 3): bounded length + a path-shaped
        # charset → 422 on anything malformed, before it reaches the LIKE query.
        if qpath and (len(qpath) > MAX_QPATH_LEN or not QPATH_RE.match(qpath)):
            return JSONResponse({"error": f"invalid qpath: {_redact(qpath)!r}"}, status_code=422)
        # Wedge-class-2 (task 20afcaf7 r3): off_loop like every route above.
        trovex_data, timeout_resp = await _offloaded(_docs_query, qpath, status, sort, limit, source)
        if timeout_resp is not None:
            return timeout_resp
        return templates.TemplateResponse(request, "_docs_table.html", trovex_data)

    def _compute_doc_view(store: Any, ext_id: str) -> tuple[Any, str | None, Any]:
        doc = store.get(ext_id)
        if doc is None:
            return None, None, None
        body_html, toc = render_markdown(doc.content)
        return doc, body_html, toc

    @app.get("/doc/{ext_id}", response_class=HTMLResponse)
    async def doc_view(request: Request, ext_id: str) -> HTMLResponse:
        """Render a trovex-owned doc's content — how humans read what agents store
        (no local file; the frontend is the human surface). Wedge-class-2 (task
        20afcaf7 r3): store.get + markdown render off_loop'd like every route above."""
        (doc, body_html, toc), timeout_resp = await _offloaded(
            _compute_doc_view, get_state().store, ext_id
        )
        if timeout_resp is not None:
            return timeout_resp
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
        # Backlinks panel: the typed doc_links into/out of this doc, so a reader
        # sees the decision lineage (what superseded it, what it's a verdict of)
        # right on the page — the Jinja twin of the graph side panel. Off the loop
        # (wedge class 2) like the render above, since node_detail reads the store.
        detail, bl_timeout = await _offloaded(
            graphview.node_detail, get_state().searcher.db, ext_id
        )
        if bl_timeout is not None:
            return bl_timeout
        links_out = detail["out_links"] if detail else []
        links_in = detail["in_links"] if detail else []
        return templates.TemplateResponse(
            request,
            "doc.html",
            {
                "doc": doc,
                "body_html": body_html,
                "toc": toc,
                "pygments_css": PYGMENTS_CSS,
                "links_out": links_out,
                "links_in": links_in,
            },
        )

    @app.delete("/api/doc/{ext_id}")
    @write_limit
    async def api_doc_delete(ext_id: str, request: Request) -> JSONResponse:
        """Delete a trovex-owned doc. Updates go through trovex_write (same id)."""
        if not _write_authorized(request):
            return _unauthorized()
        # Off the loop (wedge class 2): store.delete retries on SQLITE_BUSY with
        # a real time.sleep backoff — inline, that backoff runs on the loop.
        ok, timeout_resp = await _offloaded(get_state().store.delete, ext_id, pool="heavy")
        if timeout_resp:
            return timeout_resp
        return JSONResponse({"deleted": ok}, status_code=200 if ok else 404)

    def _compute_store_context(
        store: Any, tag: str, kind: str, collection: str, q: str, page: int
    ) -> dict:
        now = _now()
        f_tag, f_kind = tag, kind
        if collection:
            cf = store.get_collection(collection) or {}
            f_tag = cf.get("tag", f_tag)
            f_kind = cf.get("kind", f_kind)
        page = max(1, page)
        per = get_state().settings.store_page_size

        def card(d, snippet):
            return {
                "ext_id": d.ext_id,
                "title": d.title,
                "kind": d.kind,
                "status": d.status,
                "tokens_est": d.tokens_est,
                "tags": d.tags,
                "age_days": max(0.0, (now - d.mtime) / 86400),
                "snippet": snippet,
            }

        qf = q.strip() or None
        total = store.count_docs(tag=f_tag or None, kind=f_kind or None, q=qf)
        docs = store.list_docs(
            tag=f_tag or None, kind=f_kind or None, q=qf, limit=per, offset=(page - 1) * per
        )
        items = [card(d, _snippet(d.content)) for d in docs]
        pages = (total + per - 1) // per

        facets, other_tags = store.tags_by_facet()
        return {
            "items": items,
            "total": total,
            "total_tokens": sum(i["tokens_est"] for i in items),
            "facets": facets,
            "other_tags": other_tags,
            "collections": store.list_collections(),
            "active_tag": tag,
            "active_kind": kind,
            "active_collection": collection,
            "q": q,
            "page": page,
            "pages": pages,
        }

    @app.get("/store", response_class=HTMLResponse)
    async def store_page(
        request: Request,
        tag: str = "",
        kind: str = "",
        collection: str = "",
        q: str = Query("", max_length=200),
        page: int = 1,
    ) -> HTMLResponse:
        """The trovex-owned doc store — browse + quick title/text filter. Semantic
        search lives on /search (this `q` is a lightweight view filter, paginated
        like the rest of the browse). Wedge-class-2 (task 20afcaf7 r3): off_loop
        like every route above."""
        context, timeout_resp = await _offloaded(
            _compute_store_context, get_state().store, tag, kind, collection, q, page
        )
        if timeout_resp is not None:
            return timeout_resp
        return templates.TemplateResponse(request, "store.html", context)

    @app.get("/api/collections")
    async def api_collections() -> JSONResponse:
        # Off the loop (wedge class 2, task 20afcaf7): a store read stuck behind
        # disk-contended write traffic must not stall the event loop either.
        result, timeout_resp = await _offloaded(get_state().store.list_collections)
        if timeout_resp:
            return timeout_resp
        return JSONResponse(result)

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
        # Off the loop (wedge class 2): retry-on-locked backoff, see api_doc_delete.
        _, timeout_resp = await _offloaded(get_state().store.create_collection, name, flt, pool="heavy")
        if timeout_resp:
            return timeout_resp
        return JSONResponse({"ok": True, "name": name, "filter": flt})

    @app.delete("/api/collections/{name}")
    @write_limit
    async def api_collection_delete(name: str, request: Request) -> JSONResponse:
        if not _write_authorized(request):
            return _unauthorized()
        _, timeout_resp = await _offloaded(get_state().store.delete_collection, name, pool="heavy")
        if timeout_resp:
            return timeout_resp
        return JSONResponse({"deleted": True})

    @app.get("/api/doc/{ext_id}/versions")
    async def api_doc_versions(ext_id: str) -> JSONResponse:
        # Off the loop (wedge class 2, task 20afcaf7).
        result, timeout_resp = await _offloaded(get_state().store.list_versions, ext_id)
        if timeout_resp:
            return timeout_resp
        return JSONResponse(result)

    @app.post("/api/doc/{ext_id}/restore")
    @write_limit
    async def api_doc_restore(ext_id: str, request: Request) -> JSONResponse:
        if not _write_authorized(request):
            return _unauthorized()
        body, err = await _read_json(request)
        if err:
            return err
        # Numeric-cast safety (finding 4): a non-integer version_id is a 400, not
        # an uncaught 500. bool is an int subclass but never a valid version id.
        raw = body.get("version_id", 0)
        if isinstance(raw, bool) or not isinstance(raw, (int, str)):
            return JSONResponse({"error": "version_id must be an integer"}, status_code=400)
        try:
            version_id = int(raw)
        except (TypeError, ValueError):
            return JSONResponse({"error": "version_id must be an integer"}, status_code=400)
        # Off the loop (wedge class 2): restore_version re-embeds via put() —
        # onnxruntime inference, the exact class of call that wedged the loop.
        ok, timeout_resp = await _offloaded(
            get_state().store.restore_version, ext_id, version_id, pool="heavy"
        )
        if timeout_resp:
            return timeout_resp
        return JSONResponse({"restored": ok}, status_code=200 if ok else 404)

    @app.get("/api/tombstones")
    async def api_tombstones() -> JSONResponse:
        """Deleted owned docs still recoverable from their tombstones (read-only)."""
        # Off the loop (wedge class 2, task 20afcaf7).
        result, timeout_resp = await _offloaded(get_state().store.list_tombstones)
        if timeout_resp:
            return timeout_resp
        return JSONResponse(result)

    @app.post("/api/doc/{ext_id}/undelete")
    @write_limit
    async def api_doc_undelete(ext_id: str, request: Request) -> JSONResponse:
        """Recover a deleted doc from its most recent tombstone (write-gated)."""
        if not _write_authorized(request):
            return _unauthorized()
        # Off the loop (wedge class 2): restore_deleted re-embeds via put() —
        # same class of call that wedged the loop (see offload.py).
        restored, timeout_resp = await _offloaded(
            get_state().store.restore_deleted, ext_id=ext_id, pool="heavy"
        )
        if timeout_resp:
            return timeout_resp
        return JSONResponse(
            {"undeleted": bool(restored), "ext_id": restored},
            status_code=200 if restored else 404,
        )

    @app.post("/api/doc/{ext_id}/tags")
    @write_limit
    async def api_doc_tags(ext_id: str, request: Request) -> JSONResponse:
        if not _write_authorized(request):
            return _unauthorized()
        body, err = await _read_json(request)
        if err:
            return err
        # Off the loop (wedge class 2): retry-on-locked backoff, see api_doc_delete.
        tags, timeout_resp = await _offloaded(
            get_state().store.set_tags,
            ext_id,
            add=[t.strip() for t in (body.get("add") or "").split(",") if t.strip()],
            remove=[t.strip() for t in (body.get("remove") or "").split(",") if t.strip()],
            pool="heavy",
        )
        if timeout_resp:
            return timeout_resp
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
            None,
            max_length=MAX_TAG_LEN,
            pattern=KIND_RE,
            description="filter to one doc kind, e.g. 'record'",
        ),
        tags: str | None = Query(None, description="comma-separated tags; any-match scope"),
        source: str | None = Query(
            None,
            max_length=MAX_TAG_LEN,
            description="restrict to one source id (project); omit to search all",
        ),
    ) -> JSONResponse:
        state = get_state()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        if tag_list:
            # Validate tags (finding 6): bounded count + slug shape, reject malformed.
            if len(tag_list) > MAX_TAGS:
                return JSONResponse({"error": f"too many tags (max {MAX_TAGS})"}, status_code=422)
            for t in tag_list:
                if len(t) > MAX_TAG_LEN or not _re_tag.match(t):
                    return JSONResponse({"error": f"invalid tag: {_redact(t)!r}"}, status_code=422)
        if source:
            known = {s.id for s in state.settings.load_sources()} | {"trovex"}
            if source not in known:
                return JSONResponse(
                    {"error": f"unknown source: {_redact(source)!r}"}, status_code=422
                )
        # Off the event loop: the sync search (ONNX query-embed on a cache miss +
        # the sqlite KNN) runs on the dedicated bounded offload pool (offload.py)
        # so concurrent requests don't serialize head-of-line on the loop (T1).
        # The sqlite conn is opened check_same_thread=False and writes are
        # single-writer-locked, so a cross-thread read is safe.
        results, timeout_resp = await _offloaded(
            state.searcher.search,
            q,
            limit=limit,
            kind=kind,
            tags=tag_list,
            source_ids=[source] if source else None,
        )
        if timeout_resp:
            return timeout_resp
        return JSONResponse(
            [
                {
                    "path": r.path,
                    "title": r.title,
                    "score": round(r.score, 4),
                    "distance": round(r.distance, 4),
                    "age_days": round(r.age_days, 1),
                    "status": r.status,
                    "marker": r.marker,
                    "tokens_est": r.tokens_est,
                    "size_bytes": r.size_bytes,
                    # Which project a hit came from — needed to make sense of an
                    # unscoped result set, and to know what to pass as `source`.
                    "source_id": r.source_id,
                }
                for r in results
            ]
        )

    @app.get("/api/boot")
    @search_limit
    async def api_boot(
        request: Request,
        agent: str = Query(..., min_length=1, max_length=MAX_TAG_LEN),
        k: int = Query(5, ge=1, le=search_max),
        floor: float = Query(0.62, ge=0.0, le=1.0),
        # No max_length: the prompt hook sends whole prompts here, and a 422 is a
        # silently-dropped recall. boot_pointers truncates to BOOT_Q_MAX instead.
        q: str | None = Query(None, description="override the generic boot query"),
        budget: int | None = Query(None, ge=1, description="response budget in tokens"),
    ) -> JSONResponse:
        """Active-memory recall: the agent's own records as a ~80-token pointer
        pack (RFC 330e7d43, step 2). Read-only; empty when nothing clears
        scope (owner/<agent> + kind=record) + floor."""
        # Off the event loop (T1): boot embeds BOOT_QUERY (cached) then runs the
        # sqlite KNN — both belong on the offload pool, not on the loop. Boot
        # must NEVER 500 (boot_pointers' own contract) — a timeout degrades to
        # the same empty pack boot_pointers itself returns on a retrieval error,
        # rather than surfacing as an error to the prompt hook.
        def _empty_pack(degraded: str | None = None) -> dict:
            # degraded names WHY it's empty: None = true scope miss; a string
            # = recall shed ("timeout"/"shed"), so the prompt hook can tell a
            # shed recall from "no records" (ticket 7df08701).
            pack = {"agent": agent, "pointers": [], "render": "", "tokens_est": 0, "degraded": degraded}
            if budget is not None:
                pack.update(budget_requested=budget, budget_used=0, trimmed=[])
            return pack

        # Load-shed (audit Q5): /api/boot is the fleet's hot path — every agent
        # prompt hits it. If the offload pool is already saturated, or the client
        # (the prompt hook, which abandons at ~2s) has already disconnected, do
        # NOT queue a recall that would just orphan a worker and feed the pile-up
        # that ends in a watchdog restart. Return boot's own empty pack (200) at
        # once — identical to "nothing cleared scope". The recall itself is
        # bounded by the short boot deadline, not the 30s default, so a slow
        # retrieval sheds the same way instead of holding a worker.
        t0 = time.perf_counter()
        if offload.pool_saturated() or await request.is_disconnected():
            # Deliberate load-shed, not "no records" — flag it so the hook can
            # tell a shed recall from an empty one (ticket 7df08701).
            log.warning("boot recall shed: offload pool saturated / client gone (agent=%s)", agent)
            return JSONResponse(_empty_pack(degraded="shed"))
        try:
            pack = await offload.off_loop(
                boot_pointers,
                get_state().searcher,
                agent,
                k=k,
                floor=floor,
                q=q,
                budget=budget,
                timeout=_BOOT_OFFLOAD_TIMEOUT_SEC,
            )
        except TimeoutError:
            # The REAL trigger (ticket 7df08701): the offload worker blew the
            # boot wall-deadline under CPU starvation. NOT "no records" — flag
            # degraded='timeout' + log so the prompt hook can tell them apart.
            log.warning(
                "boot recall degraded: offload timeout %.1fs (agent=%s)",
                _BOOT_OFFLOAD_TIMEOUT_SEC, agent,
            )
            pack = _empty_pack(degraded="timeout")
        # task 2b7974cf: log every boot/prompt-hook call — the fleet's real
        # recall traffic, invisible to the replay eval until this landed. `q`
        # present = the UserPromptSubmit hook (trovex-prompt.sh); absent = the
        # generic SessionStart hook (trovex-boot.sh). Best-effort, never blocks
        # or fails the response — boot must never 500.
        # Query logging is off the request path entirely now (task b02389c2 AC2 /
        # audit Q6): enqueue to the single background writer — non-blocking,
        # dropped if the queue is full — instead of taking an offload worker and
        # busy-waiting on the served connection's write lock. Zero DB work here.
        try:
            from .usage import enqueue_pointer_query

            enqueue_pointer_query(
                get_state().searcher.db,
                source="prompt" if q else "boot",
                agent=agent,
                # Log the SAME text boot embedded (cleaned + capped), not the raw
                # prompt: --replay re-embeds the logged query, so a mismatch here
                # would make the replay eval drift from live recall (perf A).
                query=clean_query(q) if q else BOOT_QUERY,
                pointers=pack.get("pointers", []),
                tokens_est=pack.get("tokens_est", 0),
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
                budget_requested=budget,
                budget_used=pack.get("budget_used", 0),
            )
        except Exception:  # noqa: BLE001 — boot must never 500 on a log failure
            pass
        headers = (
            {"X-Trovex-Budget-Used": str(pack["budget_used"])}
            if budget is not None
            else None
        )
        return JSONResponse(pack, headers=headers)

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
        # Wedge-class-2 recurrence (2026-08-31, live `sample` dump — see offload.py):
        # this call chain (capture_state -> store.put -> embedder.embed) ran
        # INLINE here, straight on the event loop — the ONE route 33ca98a's
        # off-loop fix missed. embedder.embed is onnxruntime inference (CPU-bound,
        # spins its own worker threads), and the transcript-distil fallback path
        # additionally makes a blocking OpenAI network call (up to 20s). Off the
        # loop like every other write path now.
        try:
            # Heavy pool (task b02389c2 AC3): capture is embed + a possible 20s
            # OpenAI distil call — it must never occupy a recall worker.
            result = await offload.off_loop_heavy(
                capture_state,
                get_state().store,
                agent,
                body.get("summary") or "",
                transcript=body.get("transcript") or "",
                reason=(body.get("reason") or "postcompact"),
            )
        except TimeoutError:
            return JSONResponse({"captured": False, "reason": "capture timed out"}, status_code=504)
        return JSONResponse(result)

    def _compute_map(canonical_only: bool) -> dict:
        store = get_state().store
        docs = store.list_docs(limit=2000)
        if canonical_only:
            docs = [d for d in docs if d.status not in ("stale", "duplicate")]
        return {
            "count": len(docs),
            "docs": [
                {
                    "id": d.ext_id,
                    "title": d.title,
                    "kind": d.kind,
                    "status": d.status,
                    "tags": d.tags,
                }
                for d in docs
            ],
        }

    @app.get("/api/map")
    async def api_map(canonical_only: bool = True) -> JSONResponse:
        """The 'map' of the store: titles + tags + status, no content. Cheap enough
        to inject at session start so an agent *sees the territory* and knows what
        it can ask trovex for — turning an unknown-unknown into a queryable target.

        Wedge-class-2 (task 20afcaf7): this read hit the store directly inline on
        the event loop, same bug class as the capture/doc-mutation routes fixed by
        33ca98a/f2b4c872 — a slow store call (e.g. one blocked behind a forced WAL
        checkpoint under disk contention) would freeze /healthz along with it.
        off_loop like every other store-touching route now."""
        result, timeout_resp = await _offloaded(_compute_map, canonical_only)
        if timeout_resp is not None:
            return timeout_resp
        return JSONResponse(result)

    @app.get("/api/graph")
    async def api_graph(
        source: str | None = Query(
            None, max_length=100, pattern=r"^[A-Za-z0-9_.:/-]+$",
            description="restrict to one source_id partition",
        ),
        depth: int = Query(2, ge=0, le=6, description="k-hop radius around focus"),
        focus: str | None = Query(
            None, max_length=200, description="centre node id (doc id or ext_id)",
        ),
    ) -> JSONResponse:
        """The knowledge graph of the live index: docs/code/tickets/decisions as
        nodes, typed doc_links as edges, with per-node status / agent-read heat /
        drift so the SPA can paint its engineering lenses. `focus`+`depth` limit
        the result to a k-hop neighbourhood; bad params 422 via Query bounds.

        Off the loop (wedge class 2, task 20afcaf7): build_graph scans docs +
        doc_links + the agent-usage tables, the same store-read exposure the map
        and stats routes offload."""
        db = get_state().searcher.db
        result, timeout_resp = await _offloaded(
            graphview.build_graph, db, source=source, focus=focus, depth=depth
        )
        if timeout_resp is not None:
            return timeout_resp
        return JSONResponse(result)

    @app.get("/api/graph/node/{node_id}")
    async def api_graph_node(node_id: str) -> JSONResponse:
        """Side-panel detail: the doc rendered + its in/out links with context."""
        db = get_state().searcher.db
        detail, timeout_resp = await _offloaded(graphview.node_detail, db, node_id)
        if timeout_resp is not None:
            return timeout_resp
        if detail is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        html, _headings = render_markdown(detail.pop("content") or "")
        detail["html"] = html
        return JSONResponse(detail)

    def _compute_stats(db: sqlite3.Connection, usearch_partitions: set[str]) -> dict:
        total = db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
        total_tokens = db.execute("SELECT COALESCE(SUM(tokens_est), 0) AS t FROM docs").fetchone()[
            "t"
        ]
        by_status = {
            r["status"]: r["c"]
            for r in db.execute("SELECT status, COUNT(*) AS c FROM docs GROUP BY status").fetchall()
        }
        # task 4c89b89a: per-partition vec0 KNN headroom, so the dashboard shows
        # the same number capacity.log_capacity_warnings acts on — a partition
        # already on the usearch escape hatch is marked `usearch: true` instead
        # of a ceiling ratio (that specific risk no longer applies to it).
        capacity_by_partition = [
            {
                "source_id": src,
                "docs": c["docs"],
                "chunks": c["chunks"],
                "ceiling_ratio": round(c["chunks"] / capacity.VEC0_K_CEILING, 3),
                "usearch": src in usearch_partitions,
            }
            for src, c in sorted(capacity.partition_counts(db).items())
        ]
        return {
            "total": total,
            "total_tokens": total_tokens,
            "by_status": by_status,
            "capacity": capacity_by_partition,
        }

    @app.get("/api/stats")
    async def api_stats() -> JSONResponse:
        """Wedge-class-2 (task 20afcaf7): see _compute_map's docstring — same
        direct-inline-on-the-event-loop bug, off_loop'd for the same reason."""
        state = get_state()
        result, timeout_resp = await _offloaded(
            _compute_stats, state.searcher.db, set(state.settings.usearch_partitions)
        )
        if timeout_resp is not None:
            return timeout_resp
        return JSONResponse(result)

    @app.post("/api/reindex")
    @write_limit
    async def api_reindex(request: Request) -> JSONResponse:
        # Write-gated like the other mutating endpoints (finding 2): a full
        # reindex is an admin/token-only operation, not anonymous.
        if not _write_authorized(request):
            return _unauthorized()
        state = get_state()
        # `full=true` forces a full re-embed (bypasses the mtime/content-hash
        # fast paths); default is incremental — only changed docs re-embed.
        full = request.query_params.get("full", "").strip().lower() in ("1", "true", "yes")
        # index_jobs op-log (task dab8766b, replacing 085f1d69/67ebd68c's
        # per-request lock): enqueue and return immediately — the single
        # applier thread (started in `lifespan`) is what actually calls
        # Indexer.reindex(), never this request. Two callers hitting this
        # while a run is already in flight never collide on the DB or get a
        # bare rejection: enqueue() coalesces them onto the same job (queued)
        # or flags the in-flight one to run again the moment it finishes
        # (processing) — see index_jobs.py.
        from . import index_jobs

        # Off the loop (wedge class 2, task 20afcaf7): enqueue does a BEGIN
        # IMMEDIATE write under state.index_jobs_lock — same disk-contention
        # exposure as every other write route here.
        result, timeout_resp = await _offloaded(
            index_jobs.enqueue,
            state.indexer.db,
            state.index_jobs_lock,
            "rebuild" if full else "scan_source",
            full=full,
        )
        if timeout_resp:
            return timeout_resp
        state.applier.notify()
        return JSONResponse(
            {"job_id": result["job_id"], "position": result["position"], "coalesced": result["coalesced"]},
            status_code=202,
        )

    @app.get("/api/reindex/{job_id}")
    async def api_reindex_status(job_id: int) -> JSONResponse:
        from . import index_jobs

        # Off the loop (wedge class 2, task 20afcaf7).
        job, timeout_resp = await _offloaded(index_jobs.get_job, get_state().indexer.db, job_id)
        if timeout_resp:
            return timeout_resp
        if job is None:
            return JSONResponse({"error": "no such job"}, status_code=404)
        return JSONResponse(job)

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> PlainTextResponse:
        """Liveness + served-empty-store guard (incident 35c0631e), LOOP-ONLY
        (audit Q9).

        A frozen/stale served connection (a half-open write txn pinned the
        snapshot) kept answering 200 while serving 0 docs on a 4.7k-doc store,
        so the whole fleet silently booted empty for days. /healthz now reads a
        staleness flag refreshed in the BACKGROUND and returns 503 when it is
        set — never touching the DB or the offload pool on the probe path, so a
        health check can't queue behind recall or orphan a worker during the
        very overload it exists to report. The flag goes stale when the served
        connection reads 0 docs while the DB file on disk holds rows.
        """
        health = get_state().health
        if health.get("stale"):
            return PlainTextResponse(health.get("detail", "stale store"), status_code=503)
        return PlainTextResponse("ok")

    def _compute_settings_context(db: sqlite3.Connection, state: Any) -> dict:
        from . import backup as backup_mod

        db_path = state.settings.data_dir / "trovex.db"
        return {
            "db_size": db_path.stat().st_size if db_path.exists() else 0,
            "doc_count": db.execute(
                "SELECT COUNT(*) AS c FROM docs WHERE source_id='trovex'"
            ).fetchone()["c"],
            "chunk_count": db.execute("SELECT COUNT(*) AS c FROM chunks").fetchone()["c"],
            "auth_on": bool(state.settings.write_token),
            "backups": backup_mod.list_backups(state.settings.data_dir),
        }

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request) -> HTMLResponse:
        """Wedge-class-2 (task 20afcaf7 r3): off_loop like every route above."""
        state = get_state()
        context, timeout_resp = await _offloaded(
            _compute_settings_context, state.searcher.db, state
        )
        if timeout_resp is not None:
            return timeout_resp
        return templates.TemplateResponse(request, "settings.html", context)

    @app.get("/api/backups")
    async def api_backups() -> JSONResponse:
        # Wedge-class-2 (task 20afcaf7 r3): backup_mod.list_backups globs the
        # backups dir and stat()s every file — off_loop like every route above.
        from . import backup as backup_mod

        result, timeout_resp = await _offloaded(
            backup_mod.list_backups, get_state().settings.data_dir
        )
        if timeout_resp is not None:
            return timeout_resp
        return JSONResponse(result)

    @app.post("/api/backup")
    @write_limit
    async def api_backup(request: Request) -> JSONResponse:
        if not _write_authorized(request):
            return _unauthorized()
        # Wedge-class-2 (task 20afcaf7 r3): the exact stall class this whole
        # ticket is about — a PASSIVE checkpoint + Connection.backup() over the
        # full ~340MB store, inline on the event loop until now. off_loop it.
        from . import backup as backup_mod

        state = get_state()
        dest, timeout_resp = await _offloaded(
            backup_mod.make_backup,
            state.settings.data_dir / "trovex.db",
            state.settings.data_dir,
            pool="heavy",
        )
        if timeout_resp is not None:
            return timeout_resp
        return JSONResponse({"ok": True, "file": dest.name})

    # ── Install page + hook downloads ────────────────────────────────

    def _compute_doc_total(db: sqlite3.Connection) -> int:
        return db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]

    @app.get("/install", response_class=HTMLResponse)
    async def install_page(request: Request) -> HTMLResponse:
        """Wedge-class-2 (task 20afcaf7 r3): off_loop like every route above."""
        total, timeout_resp = await _offloaded(_compute_doc_total, get_state().searcher.db)
        if timeout_resp is not None:
            return timeout_resp
        return templates.TemplateResponse(request, "install.html", {"total": total})

    @app.get("/api/write-token")
    async def api_write_token(request: Request) -> JSONResponse:
        """Hand the auto-generated write token to a SAME-MACHINE browser so the
        local UI can issue writes without the operator copying it by hand. Refused
        for non-loopback clients, so a network-exposed instance never leaks it.
        Returns no token when writes are open (TROVEX_ALLOW_UNAUTH_WRITES). Disabled
        outright on a non-loopback bind — see _server_bound_loopback."""
        if not _server_bound_loopback():
            return JSONResponse({"error": _NON_LOOPBACK_BIND_MSG}, status_code=403)
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

    def _compute_usage_context(db: sqlite3.Connection, user: str, days: int) -> dict:
        from datetime import datetime, timezone

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
                WHERE {" AND ".join(where)}
                ORDER BY ts DESC LIMIT 500""",
            params,
        ).fetchall()

        users = [
            r["user"]
            for r in db.execute("SELECT DISTINCT user FROM mcp_queries ORDER BY user").fetchall()
        ]

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
               FROM mcp_queries WHERE {" AND ".join(where)}
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
        avg_elapsed = sum(r["elapsed_ms"] for r in queries) / total_queries if total_queries else 0
        unique_users = len({r["user"] for r in queries})

        return {
            "buckets": buckets,
            "per_user": per_user,
            "users": users,
            "user": user,
            "days": days,
            "total_queries": total_queries,
            "total_tokens": total_tokens,
            "avg_elapsed": int(avg_elapsed),
            "unique_users": unique_users,
        }

    @app.get("/usage", response_class=HTMLResponse)
    async def usage_page(
        request: Request,
        user: str = "",
        days: int = 7,
    ) -> HTMLResponse:
        """Wedge-class-2 (task 20afcaf7 r3): off_loop like every route above."""
        context, timeout_resp = await _offloaded(
            _compute_usage_context, get_state().searcher.db, user, days
        )
        if timeout_resp is not None:
            return timeout_resp
        return templates.TemplateResponse(request, "usage.html", context)

    def _compute_insights_context(db: sqlite3.Connection, days: int) -> dict:
        days = max(1, min(90, int(days)))
        since = _now() - days * 86400
        now = _now()

        top_q = insights_mod.top_queries(db, since)
        failed = [
            {**r, "age_label": _relative_time(now - r["ts"])}
            for r in insights_mod.failed_queries(db, since)
        ]
        repeated = [
            {
                **r,
                "last_label": _relative_time(now - r["last_ts"]),
                "span_label": _relative_time(r["last_ts"] - r["first_ts"])
                if r["last_ts"] > r["first_ts"]
                else "instant",
            }
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
        return {
            "days": days,
            "top_q": top_q,
            "failed": failed,
            "repeated": repeated,
            "most_returned": most_returned,
            "dead": dead,
            "heatmap": heatmap,
            "rerank": rerank,
            "divergence": divergence,
        }

    @app.get("/insights", response_class=HTMLResponse)
    async def insights_page(request: Request, days: int = 7) -> HTMLResponse:
        """Wedge-class-2 (task 20afcaf7 r3): off_loop like every route above."""
        context, timeout_resp = await _offloaded(
            _compute_insights_context, get_state().searcher.db, days
        )
        if timeout_resp is not None:
            return timeout_resp
        return templates.TemplateResponse(request, "insights.html", context)

    @app.get("/api/suggest")
    async def api_suggest(q: str = Query("", max_length=200)) -> JSONResponse:
        state = get_state()
        db = state.searcher.db
        # Log the query truncated (finding 8) — never the full user text.
        log.debug("suggest q=%r", _redact(q))
        # Off the loop (wedge class 2, task 20afcaf7).
        result, timeout_resp = await _offloaded(insights_mod.suggest_queries, db, q)
        if timeout_resp:
            return timeout_resp
        return JSONResponse(result)

    def _compute_savings_page_context(db: sqlite3.Connection, days: int) -> dict:
        days = max(1, min(90, int(days)))
        since = _now() - days * 86400
        return {
            "totals": savings_mod.totals(db, since),
            "per_user": savings_mod.per_user(db, since),
            "daily": savings_mod.daily_series(db, since, _now()),
            "top_queries": savings_mod.top_queries(db, since, limit=10),
            "days": days,
        }

    @app.get("/savings", response_class=HTMLResponse)
    async def savings_page(request: Request, days: int = 7) -> HTMLResponse:
        """Wedge-class-2 (task 20afcaf7 r3): off_loop like every route above."""
        context, timeout_resp = await _offloaded(
            _compute_savings_page_context, get_state().searcher.db, days
        )
        if timeout_resp is not None:
            return timeout_resp
        return templates.TemplateResponse(request, "savings.html", context)

    @app.get("/api/savings")
    async def api_savings(days: int = 7) -> JSONResponse:
        state = get_state()
        db = state.searcher.db
        days = max(1, min(90, int(days)))
        since = _now() - days * 86400
        # Off the loop (wedge class 2, task 20afcaf7).
        result, timeout_resp = await _offloaded(savings_mod.totals, db, since)
        if timeout_resp:
            return timeout_resp
        return JSONResponse(result)

    @app.get("/api/savings/lifetime")
    async def api_savings_lifetime() -> JSONResponse:
        state = get_state()
        result, timeout_resp = await _offloaded(savings_mod.totals, state.searcher.db, 0.0)
        if timeout_resp:
            return timeout_resp
        return JSONResponse(result)

    @app.get("/api/savings/agents")
    async def api_savings_agents(days: int = 7) -> JSONResponse:
        state = get_state()
        since = _now() - max(1, min(90, int(days))) * 86400
        result, timeout_resp = await _offloaded(savings_mod.per_agent, state.searcher.db, since)
        if timeout_resp:
            return timeout_resp
        return JSONResponse(result)

    @app.get("/api/savings/sessions")
    async def api_savings_sessions(days: int = 7) -> JSONResponse:
        state = get_state()
        since = _now() - max(1, min(90, int(days))) * 86400
        result, timeout_resp = await _offloaded(savings_mod.per_session, state.searcher.db, since)
        if timeout_resp:
            return timeout_resp
        return JSONResponse(result)

    @app.get("/api/savings/benchmark")
    async def api_savings_benchmark() -> JSONResponse:
        """The committed, reproducible corpus-benchmark result (or null if the
        benchmark hasn't been run into the package). Static proof behind the
        headline savings %, distinct from the live per-user ledger above."""
        return JSONResponse(savings_mod.benchmark_result())

    def _compute_usage(db: sqlite3.Connection, since: float) -> list[dict]:
        by_user = db.execute(
            """SELECT user, COUNT(*) AS queries,
                      COALESCE(SUM(response_tokens_est),0) AS resp_tokens,
                      MAX(ts) AS last_seen
               FROM mcp_queries WHERE ts >= ?
               GROUP BY user ORDER BY queries DESC""",
            (since,),
        ).fetchall()
        return [
            {
                "user": r["user"],
                "queries": r["queries"],
                "response_tokens_est": r["resp_tokens"],
                "last_seen": r["last_seen"],
            }
            for r in by_user
        ]

    @app.get("/api/usage")
    async def api_usage(days: int = 7) -> JSONResponse:
        state = get_state()
        db = state.searcher.db
        since = _now() - max(1, min(90, int(days))) * 86400
        # Off the loop (wedge class 2, task 20afcaf7).
        result, timeout_resp = await _offloaded(_compute_usage, db, since)
        if timeout_resp:
            return timeout_resp
        return JSONResponse(result)

    return app


def _compute_search_context(
    q: str,
    summary: bool,
    tags: list[str] | None,
    kind: str,
    sort: str,
    page: int,
) -> dict:
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
            pool.append(
                {
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
                }
            )
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
    results = pool[(page - 1) * per : page * per]

    # Facets: tags present in the result set (not already selected), by count.
    facets = [
        {"tag": t, "count": c, "url": _u(tags=tags + [t], page=1)}
        for t, c in sorted(facet_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        if t not in tags
    ][:12]
    active_tags = [{"tag": t, "url": _u(tags=[x for x in tags if x != t], page=1)} for t in tags]

    # Tokens from query (alphanumeric runs >= 2 chars) for inline highlighting.
    # The `[a-zA-Z0-9]{2,}` class is deliberately restrictive: terms are plain
    # alphanumerics, so when they're later `re.escape`d and matched against the
    # HTML-escaped text in _highlight(), a term can never span/split an HTML
    # entity (e.g. `&amp;`) — no ReDoS, no broken markup. Don't widen this class
    # without revisiting _highlight()'s escaping assumption.
    import re as _re

    highlight_terms = sorted(
        {t for t in _re.findall(r"[a-zA-Z0-9]{2,}", q.lower()) if len(t) >= 2},
        key=len,
        reverse=True,
    )

    trovex_data = {
        "q": q,
        "summary": summary,
        "total": total,
        "results": results,
        "elapsed_ms": elapsed_ms,
        "example_queries": EXAMPLE_QUERIES,
        "highlight_terms": highlight_terms,
        "tags": tags,
        "kind": kind,
        "sort": sort,
        "facets": facets,
        "active_tags": active_tags,
        "total_results": total_results,
        "page": page,
        "pages": pages,
        "prev_url": _u(page=page - 1) if page > 1 else "",
        "next_url": _u(page=page + 1) if page < pages else "",
        "clear_url": _u(tags=[], kind="", page=1),
        "has_filters": bool(tags or kind),
    }
    return trovex_data


async def _render_search(
    request: Request,
    templates: Jinja2Templates,
    q: str,
    summary: bool,
    partial: bool,
    *,
    tags: list[str] | None = None,
    kind: str = "",
    sort: str = "relevance",
    page: int = 1,
) -> HTMLResponse:
    """Wedge-class-2 (task 20afcaf7 r3): search_chunks + the per-hit store.get
    loop below ran inline on the event loop. off_loop like every route above."""
    trovex_data, timeout_resp = await _offloaded(
        _compute_search_context, q, summary, tags, kind, sort, page
    )
    if timeout_resp is not None:
        return timeout_resp
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


def _docs_query(qpath: str, status: str, sort: str, limit: int, source: str = "") -> dict[str, Any]:
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
        "recent": "mtime DESC",
        "oldest": "mtime ASC",
        "largest": "tokens_est DESC",
        "path": "path ASC",
    }.get(sort, "mtime DESC")

    limit = max(10, min(1000, int(limit)))

    rows = db.execute(
        f"""SELECT path, title, mtime, status, tokens_est, size_bytes, source_id
            FROM docs WHERE {" AND ".join(where)}
            ORDER BY {order} LIMIT ?""",
        (*params, limit),
    ).fetchall()
    rows = _rows_with_age(rows)
    filtered_count = db.execute(
        f"SELECT COUNT(*) AS c FROM docs WHERE {' AND '.join(where)}", params
    ).fetchone()["c"]

    return {"rows": rows, "filtered": filtered_count, "sources_meta": _sources_meta(db)}
