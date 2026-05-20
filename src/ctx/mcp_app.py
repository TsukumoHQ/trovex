"""MCP server exposing the `ctx` tool.

Single tool, minimal output by design — see project README for rationale.
"""

import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .state import get_state

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

    from .usage import log_query

    state = get_state()
    t0 = _time.perf_counter()
    results = state.searcher.search(q, limit=5)
    out = (state.searcher.format_with_summary(results) if summary
           else state.searcher.format_minimal(results))
    elapsed_ms = int((_time.perf_counter() - t0) * 1000)
    try:
        # Savings model: without ctx, agent typically reads top-3 .md files
        # matching their grep/glob. With ctx, they read 1 (the canonical top-1).
        # "would_have_read_tokens" = sum of top-3 results (incl. the one they
        # still read with ctx). Real savings later subtract top-1 + response.
        would_have_read = sum(r.tokens_est for r in results[:3])
        top_tokens = results[0].tokens_est if results else 0
        log_query(
            state.searcher.db, q, len(results), summary,
            response_tokens_est=len(out) // 4, elapsed_ms=elapsed_ms,
            would_have_read_tokens=would_have_read,
            top_result_tokens=top_tokens,
        )
    except Exception:
        pass  # never let logging break the tool
    return out
