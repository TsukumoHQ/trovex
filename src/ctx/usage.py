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
current_openai_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_openai_key", default=None
)
current_rerank_model: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_rerank_model", default=None
)
current_write_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_write_token", default=None
)


class UserHeaderMiddleware(BaseHTTPMiddleware):
    """Reads X-CTX-User + optional X-CTX-OpenAI-Key from incoming request."""

    async def dispatch(self, request: Request, call_next):
        user = request.headers.get("x-ctx-user") or "unknown"
        clean = "".join(c for c in user if c.isalnum() or c in "._-")[:32] or "unknown"
        u_token = current_user.set(clean)

        # BYOK: optional OpenAI key for reranking. Never persist, never log.
        raw_key = request.headers.get("x-ctx-openai-key")
        if raw_key and raw_key.startswith("sk-") and len(raw_key) > 20:
            k_token = current_openai_key.set(raw_key)
        else:
            k_token = current_openai_key.set(None)

        # Per-request model override (allowed = gpt-5.* family).
        m = (request.headers.get("x-ctx-rerank-model") or "").strip()
        m_token = current_rerank_model.set(m if m.startswith("gpt-") else None)

        w_token = current_write_token.set(request.headers.get("x-ctx-write-token"))

        try:
            response = await call_next(request)
        finally:
            current_user.reset(u_token)
            current_openai_key.reset(k_token)
            current_rerank_model.reset(m_token)
            current_write_token.reset(w_token)
        return response


def log_query(db, query: str, n_results: int, summary: bool,
              response_tokens_est: int, elapsed_ms: int,
              would_have_read_tokens: int = 0,
              top_result_tokens: int = 0,
              results: list | None = None,
              rerank_info: dict | None = None,
              pre_rerank_paths: list[str] | None = None) -> None:
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
           (ts, user, query, n_results, summary, response_tokens_est, elapsed_ms,
            would_have_read_tokens, top_result_tokens,
            reranked, llm_model, llm_tokens_in, llm_tokens_out, llm_elapsed_ms,
            pre_top1_path, top1_changed, top1_lift, top5_overlap)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (time.time(), current_user.get(), query[:500],
         n_results, int(summary), response_tokens_est, elapsed_ms,
         would_have_read_tokens, top_result_tokens,
         1 if rerank_info else 0,
         (rerank_info or {}).get("model"),
         (rerank_info or {}).get("tokens_in", 0),
         (rerank_info or {}).get("tokens_out", 0),
         (rerank_info or {}).get("elapsed_ms", 0),
         pre_top1, top1_changed, top1_lift, top5_overlap),
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
