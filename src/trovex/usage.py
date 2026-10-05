"""Per-user attribution for MCP calls.

We capture the X-TROVEX-User header on each HTTP request via a Starlette
middleware and stash it in a contextvar. The MCP tool reads it back
and logs the query for the dashboard.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import queue
import re
import sqlite3
import threading
import time
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

log = logging.getLogger("trovex.usage")

# Conservative secret/PII patterns redacted from query text before it's stored
# (finding 5). Each is anchored to a recognisable shape so ordinary queries
# aren't mangled — we'd rather miss an exotic secret than redact real words.
_SECRET_PATTERNS = [
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),  # email
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),  # OpenAI-style key
    re.compile(r"\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{16,}\b"),  # GitHub token
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),  # Slack token
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
    # key=value secrets, e.g. api_key=..., token: ..., password=...
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|authorization|bearer)"
        r"\b\s*[:=]\s*\S+"
    ),
]


def redact_secrets(text: str) -> str:
    """Replace obvious secrets / emails in free text with `[redacted]` so they
    aren't persisted in the query log. Best-effort, pattern-based."""
    if not text:
        return text
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[redacted]", text)
    return text


def purge_old_queries(db, retention_days: int) -> int:
    """Delete mcp_queries rows older than retention_days; returns rows removed.
    retention_days <= 0 disables purging. Cascades to mcp_query_results via FK."""
    if retention_days is None or retention_days <= 0:
        return 0
    cutoff = time.time() - retention_days * 86400
    cur = db.execute("DELETE FROM mcp_queries WHERE ts < ?", (cutoff,))
    db.commit()
    return cur.rowcount or 0


def mark_result_used(db, path: str, session_id: str, window_seconds: float) -> int:
    """Label a served result relevant (task b47301eb): a served-but-unread doc is
    unlabelled, not "irrelevant" — but when THIS session reads `path` back
    (trovex_read(doc_id=...)) within `window_seconds` of it being served, that's
    the fleet's own free relevance signal, so mark it. Marks every still-unused
    served row for `path` in that session's window, not just the newest, since a
    single doc_id read can plausibly answer more than one recent query.

    Best-effort: a labeling miss must never break the read that triggered it, so
    this swallows its own errors.
    """
    if not path or not session_id or session_id == "unknown":
        return 0
    cutoff = time.time() - window_seconds
    try:
        cur = db.execute(
            """UPDATE mcp_query_results SET used = 1
               WHERE used = 0 AND path = ? AND query_id IN (
                   SELECT id FROM mcp_queries WHERE session_id = ? AND ts >= ?
               )""",
            (path, session_id, cutoff),
        )
        db.commit()
        return cur.rowcount or 0
    except Exception:  # noqa: BLE001 — labeling must never break a read
        log.debug("mark_result_used failed", exc_info=True)
        return 0


current_user: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trovex_current_user", default="unknown"
)
current_session: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trovex_current_session", default="unknown"
)
current_openai_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trovex_openai_key", default=None
)
current_rerank_model: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trovex_rerank_model", default=None
)
current_write_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trovex_write_token", default=None
)


class UserHeaderMiddleware(BaseHTTPMiddleware):
    """Reads X-TROVEX-User + optional X-TROVEX-OpenAI-Key from incoming request."""

    async def dispatch(self, request: Request, call_next):
        user = request.headers.get("x-trovex-user") or "unknown"
        clean = "".join(c for c in user if c.isalnum() or c in "._-")[:32] or "unknown"
        u_token = current_user.set(clean)

        # Per-session attribution for the savings receipt. Prefer an explicit
        # X-TROVEX-Session; otherwise fall back to the MCP transport's own
        # Mcp-Session-Id (present on every streamable-HTTP call after initialize)
        # — a real per-connection id with zero client config. Sanitised like the
        # user, "unknown" when neither is present (e.g. stdio / a bare request).
        raw_session = (
            request.headers.get("x-trovex-session")
            or request.headers.get("mcp-session-id")
            or "unknown"
        )
        clean_session = (
            "".join(c for c in raw_session if c.isalnum() or c in "._-")[:64] or "unknown"
        )
        s_token = current_session.set(clean_session)

        # BYOK: optional OpenAI key for reranking. Never persist, never log.
        raw_key = request.headers.get("x-trovex-openai-key")
        if raw_key and raw_key.startswith("sk-") and len(raw_key) > 20:
            k_token = current_openai_key.set(raw_key)
        else:
            k_token = current_openai_key.set(None)

        # Per-request model override (allowed = gpt-5.* family).
        m = (request.headers.get("x-trovex-rerank-model") or "").strip()
        m_token = current_rerank_model.set(m if m.startswith("gpt-") else None)

        w_token = current_write_token.set(request.headers.get("x-trovex-write-token"))

        try:
            response = await call_next(request)
        finally:
            current_user.reset(u_token)
            current_session.reset(s_token)
            current_openai_key.reset(k_token)
            current_rerank_model.reset(m_token)
            current_write_token.reset(w_token)
        return response


def log_query(
    db,
    query: str,
    n_results: int,
    summary: bool,
    response_tokens_est: int,
    elapsed_ms: int,
    would_have_read_tokens: int = 0,
    top_result_tokens: int = 0,
    results: list | None = None,
    rerank_info: dict | None = None,
    pre_rerank_paths: list[str] | None = None,
    budget_requested: int | None = None,
    budget_used: int = 0,
) -> None:
    # Divergence metrics: if pre-rerank paths supplied, compare with post-rerank.
    pre_top1: str | None = None
    top1_changed = 0
    top1_lift = 0
    top5_overlap = 5
    if pre_rerank_paths and results:
        pre_top1 = pre_rerank_paths[0] if pre_rerank_paths else None
        post_top1 = results[0].path if results else None
        if pre_top1 and post_top1:
            top1_changed = 1 if pre_top1 != post_top1 else 0
            try:
                # Where was the post-rerank top-1 in the original vector order?
                top1_lift = pre_rerank_paths.index(post_top1)
            except ValueError:
                top1_lift = 0
        # Top-5 set overlap: how many of post-rerank top-5 were in pre top-5?
        post5 = {r.path for r in results[:5]}
        pre5 = set(pre_rerank_paths[:5])
        top5_overlap = len(post5 & pre5)

    cur = db.execute(
        """INSERT INTO mcp_queries
           (ts, user, session_id, query, n_results, summary, response_tokens_est, elapsed_ms,
            would_have_read_tokens, top_result_tokens,
            reranked, llm_model, llm_tokens_in, llm_tokens_out, llm_elapsed_ms,
            pre_top1_path, top1_changed, top1_lift, top5_overlap,
            budget_requested, budget_used)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            time.time(),
            current_user.get(),
            current_session.get(),
            redact_secrets(query)[:500],
            n_results,
            int(summary),
            response_tokens_est,
            elapsed_ms,
            would_have_read_tokens,
            top_result_tokens,
            # "reranked" means reordering actually happened — a margin-skip
            # (task 4478fe53) carries a non-None rerank_info (so callers can
            # count the skip) but never touched the candidate order.
            1 if (rerank_info and not rerank_info.get("rerank_skipped")) else 0,
            (rerank_info or {}).get("model"),
            (rerank_info or {}).get("tokens_in", 0),
            (rerank_info or {}).get("tokens_out", 0),
            (rerank_info or {}).get("elapsed_ms", 0),
            pre_top1,
            top1_changed,
            top1_lift,
            top5_overlap,
            budget_requested,
            budget_used,
        ),
    )
    query_id = cur.lastrowid
    if results and query_id is not None:
        db.executemany(
            """INSERT INTO mcp_query_results (query_id, rank, path, status, tokens_est, score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(query_id, i, r.path, r.status, r.tokens_est, r.score) for i, r in enumerate(results)],
        )
    db.commit()


def _insert_pointer_query(
    db,
    *,
    source: str,
    agent: str,
    query: str,
    pointers: list[dict],
    tokens_est: int,
    elapsed_ms: int,
    budget_requested: int | None = None,
    budget_used: int = 0,
) -> None:
    """The mcp_queries + mcp_query_results INSERTs for one boot/prompt row, WITHOUT
    committing — shared by log_pointer_query (commit-per-call) and the background
    QueryLogWriter (batched commit)."""
    cur = db.execute(
        """INSERT INTO mcp_queries
           (ts, user, session_id, query, n_results, source,
            response_tokens_est, top_result_tokens, elapsed_ms,
            budget_requested, budget_used)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            time.time(),
            agent,
            agent,
            redact_secrets(query)[:500],
            len(pointers),
            source,
            tokens_est,
            tokens_est,
            elapsed_ms,
            budget_requested,
            budget_used,
        ),
    )
    query_id = cur.lastrowid
    if pointers and query_id is not None:
        db.executemany(
            """INSERT INTO mcp_query_results (query_id, rank, path, status, tokens_est, score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (query_id, i, p["id"], "canonical", 0, p.get("score", 0.0))
                for i, p in enumerate(pointers)
            ],
        )


def log_pointer_query(
    db,
    *,
    source: str,
    agent: str,
    query: str,
    pointers: list[dict],
    tokens_est: int,
    elapsed_ms: int,
    budget_requested: int | None = None,
    budget_used: int = 0,
) -> None:
    """Log an /api/boot call — the SessionStart hook ('boot') or the
    UserPromptSubmit hook ('prompt') — into mcp_queries/mcp_query_results
    (task 2b7974cf), the same shape `log_query` writes for an explicit
    trovex_search/trovex_read call, so the replay eval and the used-label see
    the fleet's real (hook-driven) traffic volume instead of only the rare
    explicit tool call.

    session_id = the agent's own name: a hook call has no MCP transport
    session, and the agent name IS the natural session key here — it's also
    what an agent's own MCP calls carry via X-TROVEX-Session, so a later
    trovex_read(doc_id=...) from that same agent labels a boot-served pointer
    `used` exactly like an MCP-served one.

    Best-effort: never raises — a logging miss must not break a boot call
    (boot_pointers' own "never 500" contract).
    """
    try:
        _insert_pointer_query(
            db,
            source=source,
            agent=agent,
            query=query,
            pointers=pointers,
            tokens_est=tokens_est,
            elapsed_ms=elapsed_ms,
            budget_requested=budget_requested,
            budget_used=budget_used,
        )
        db.commit()
    except Exception:  # noqa: BLE001 — a boot call must never 500 on a log failure
        # CRITICAL (incident 35c0631e): the mcp_queries INSERT above opens an
        # implicit write transaction (Python's default isolation_level). If the
        # executemany then raises, swallowing without a rollback leaves this
        # long-lived served connection stuck in an open write txn — which freezes
        # every later SELECT to that snapshot (/api/stats served 0 and /api/boot
        # recall went empty on a 4.7k-doc store) AND holds the WAL write lock, so
        # the WAL can never checkpoint (it grew to 140MB) and the separate reindex
        # writer hits "database is locked". Always release it.
        with contextlib.suppress(Exception):
            db.rollback()
        log.debug("log_pointer_query failed", exc_info=True)


# ── Background query-log writer (task b02389c2 AC2 / audit Q6) ────────────────
#
# The per-request boot/prompt log INSERT used to run on the shared offload pool
# through the SERVED connection; when it waited on the write lock (held by the
# reindex/store/checkpoint) it busy-waited up to 30s while holding that
# connection's mutex, stalling every boot read behind it. Move it off the
# request path entirely: /api/boot enqueues a row (non-blocking, dropped if the
# queue is full) and ONE background thread with its OWN short-busy_timeout
# connection drains the queue in batches and commits. The boot path does zero
# DB work for logging.

_QUERYLOG_QUEUE_MAX = 2000
_QUERYLOG_BATCH_MAX = 64
_QUERYLOG_BUSY_TIMEOUT_MS = 100  # drop-on-busy: never hold the write lock for logging


class QueryLogWriter:
    def __init__(self, db_path: Path, maxsize: int = _QUERYLOG_QUEUE_MAX):
        self._db_path = db_path
        self._q: queue.Queue = queue.Queue(maxsize=maxsize)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="trovex-querylog-writer", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def enqueue(self, fields: dict) -> None:
        """Non-blocking; drop the row if the queue is full — a logging miss must
        never slow or fail a boot call."""
        try:
            self._q.put_nowait(fields)
        except queue.Full:
            log.debug("query-log queue full — dropping a row")

    def _run(self) -> None:
        # timeout= sets sqlite busy_timeout without a formatted PRAGMA string
        conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            timeout=_QUERYLOG_BUSY_TIMEOUT_MS / 1000,
        )
        conn.row_factory = sqlite3.Row
        try:
            while True:
                try:
                    first = self._q.get(timeout=0.5)
                except queue.Empty:
                    if self._stop.is_set():
                        break
                    continue
                batch = [first]
                while len(batch) < _QUERYLOG_BATCH_MAX:
                    try:
                        batch.append(self._q.get_nowait())
                    except queue.Empty:
                        break
                self._write_batch(conn, batch)
        finally:
            with contextlib.suppress(Exception):
                conn.close()

    def _write_batch(self, conn: sqlite3.Connection, batch: list[dict]) -> None:
        try:
            for fields in batch:
                _insert_pointer_query(conn, **fields)
            conn.commit()
        except sqlite3.Error as e:
            # Drop the whole batch on a busy/locked DB rather than hold the lock
            # or crash the writer — logging is best-effort (audit Q6).
            with contextlib.suppress(Exception):
                conn.rollback()
            log.debug("query-log batch dropped (%d rows): %s", len(batch), e)


_WRITER: QueryLogWriter | None = None


def start_query_log_writer(data_dir: Path) -> QueryLogWriter:
    global _WRITER
    if _WRITER is None or not _WRITER.running:
        _WRITER = QueryLogWriter(Path(data_dir) / "trovex.db")
        _WRITER.start()
    return _WRITER


def stop_query_log_writer() -> None:
    global _WRITER
    if _WRITER is not None:
        _WRITER.stop()
        _WRITER = None


def enqueue_pointer_query(db, **fields) -> None:
    """Route a boot/prompt log row to the background writer (zero DB work on the
    caller's path). If no writer is running — tests, CLI, any non-served context
    — fall back to a direct synchronous write on `db` so logging still happens;
    the server's lifespan always starts the writer, so the hot path never takes
    that branch."""
    writer = _WRITER
    if writer is not None and writer.running:
        writer.enqueue(fields)
        return
    log_pointer_query(db, **fields)
