"""Per-user attribution for MCP calls.

We capture the X-CTX-User header on each HTTP request via a Starlette
middleware and stash it in a contextvar. The MCP tool reads it back
and logs the query for the dashboard.
"""

from __future__ import annotations

import contextvars
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

current_user: contextvars.ContextVar[str] = contextvars.ContextVar(
    "ctx_current_user", default="unknown"
)


class UserHeaderMiddleware(BaseHTTPMiddleware):
    """Reads X-CTX-User from the incoming request and stores it for tools."""

    async def dispatch(self, request: Request, call_next):
        user = request.headers.get("x-ctx-user") or "unknown"
        # Sanitize: keep alphanumerics, dot, dash, underscore. 1-32 chars.
        clean = "".join(c for c in user if c.isalnum() or c in "._-")[:32] or "unknown"
        token = current_user.set(clean)
        try:
            response = await call_next(request)
        finally:
            current_user.reset(token)
        return response


def log_query(db, query: str, n_results: int, summary: bool,
              response_tokens_est: int, elapsed_ms: int,
              would_have_read_tokens: int = 0,
              top_result_tokens: int = 0,
              results: list | None = None) -> None:
    cur = db.execute(
        """INSERT INTO mcp_queries
           (ts, user, query, n_results, summary, response_tokens_est, elapsed_ms,
            would_have_read_tokens, top_result_tokens)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (time.time(), current_user.get(), query[:500],
         n_results, int(summary), response_tokens_est, elapsed_ms,
         would_have_read_tokens, top_result_tokens),
    )
    query_id = cur.lastrowid
    if results and query_id is not None:
        db.executemany(
            """INSERT INTO mcp_query_results (query_id, rank, path, status, tokens_est, score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(query_id, i, r.path, r.status, r.tokens_est, r.score)
             for i, r in enumerate(results)],
        )
    db.commit()
