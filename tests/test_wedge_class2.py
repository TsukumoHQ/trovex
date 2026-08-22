"""Wedge class 2 fix (ticket 5e80f318): a stuck sync MCP tool handler must time
out instead of freezing the whole event loop.

Root cause (2026-08-22 prod outage, 3rd wedge that day, distinct from the WAL
class fixed by eda6f60e): every `@mcp.tool()` handler in mcp_app.py is a plain
`def`, so the mcp SDK calls it directly on the single asyncio event loop
(fn_is_async computed once at registration). The default-on local rerank tier
(rerank_local.py's lazy fastembed TextCrossEncoder fetch) has no timeout
anywhere it could be set — a slow/stuck network call there (or in the
embedder) froze the ENTIRE server, including unrelated /api/boot requests
sharing the same event loop (server.py mounts the MCP app into the same
FastAPI app).

`_off_loop` (mcp_app.py) registers an async twin with FastMCP that runs the
real sync handler in the threadpool with a hard wall-clock budget
(TROVEX_TOOL_TIMEOUT_SEC, default 30s) via `asyncio.wait_for`, while leaving
the module-level name bound to the original sync function so direct/test
callers are unaffected.

Hermetic: a deterministic bag-of-words embedder, no network, no real model
download.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time

import numpy as np
import pytest
from starlette.concurrency import run_in_threadpool

from trovex import mcp_app
from trovex.boot import boot_pointers
from trovex.config import Settings
from trovex.search import Searcher
from trovex.store import SqliteStore

DIM = 384


class BagEmbedder:
    name = "bag"
    dim = DIM

    def embed(self, texts):
        for t in texts:
            v = np.zeros(DIM, dtype=np.float32)
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                idx = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                v[idx % DIM] += 1.0
            norm = float(np.linalg.norm(v)) or 1.0
            yield v / norm


@pytest.fixture
def searcher(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    emb = BagEmbedder()
    store = SqliteStore(settings, embedder=emb)
    store.put("# Auth flow\n\njwt token signature validation", tags=["owner/alpha"])
    return Searcher(settings, embedder=emb)


@pytest.fixture(autouse=True)
def _fast_timeout(monkeypatch):
    """Every test in this module runs with a small tool budget so a stuck
    handler's real 1s sleep isn't actually waited out."""
    monkeypatch.setattr(mcp_app, "TOOL_TIMEOUT_SEC", 0.05)


@pytest.fixture
def slow_tool():
    """Registers a fresh `_off_loop`-wrapped tool that blocks for 1s — standing
    in for the unbounded rerank_local/embedder network call. Returns the
    dispatched (async) callable the mcp SDK would actually invoke."""
    calls: list[str] = []

    def _slow(text: str = "") -> str:
        calls.append("start")
        time.sleep(1.0)
        calls.append("end")  # only reached if the orphaned thread is allowed to finish
        return "done"

    mcp_app._off_loop(_slow)
    tool = mcp_app.mcp._tool_manager.get_tool("_slow")
    return tool.fn, calls


async def test_stuck_tool_call_times_out_instead_of_hanging(slow_tool):
    dispatched, _calls = slow_tool
    t0 = time.perf_counter()
    result = await dispatched()
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.5, "must return promptly, not wait out the stuck call's full 1s"
    payload = json.loads(result)
    assert payload["error"]["code"] == "tool_timeout"
    assert payload["error"]["isRetryable"] is True


async def test_boot_stays_responsive_while_a_tool_call_is_stuck(slow_tool, searcher):
    """The exact reported symptom: /api/boot (here, its underlying boot_pointers
    call run the same way the route runs it — off the loop, in the threadpool)
    must keep completing WHILE a different tool call is wedged, on the SAME
    shared event loop — proving the fix, not just that the stuck call times out
    in isolation."""
    dispatched, _calls = slow_tool

    async def boot_like():
        return await run_in_threadpool(boot_pointers, searcher, "alpha", k=5, floor=0.0)

    t0 = time.perf_counter()
    tool_result, boot_pack = await asyncio.gather(dispatched(), boot_like())
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.5  # both finished fast — neither waited on the stuck call's 1s sleep
    assert json.loads(tool_result)["error"]["code"] == "tool_timeout"
    assert isinstance(boot_pack, dict)  # boot_pointers never raises; got a real pack back


async def test_fast_tool_call_is_unaffected(searcher):
    """The common case: a call that finishes well inside the budget must return
    its real result, not a timeout — the wrapper must not itself add latency or
    swallow a normal result."""

    def _fast(text: str = "") -> str:
        return f"echo:{text}"

    mcp_app._off_loop(_fast)
    tool = mcp_app.mcp._tool_manager.get_tool("_fast")

    result = await tool.fn(text="hi")
    assert result == "echo:hi"


def test_off_loop_leaves_module_level_name_synchronous():
    """Direct/test callers (`mcp_app.trovex_write(...)` etc., used throughout
    the rest of the suite) must keep getting a plain sync function back — only
    the FastMCP-registered twin is async."""

    def _plain(text: str = "") -> str:
        return text.upper()

    wrapped = mcp_app._off_loop(_plain)
    assert wrapped is _plain
    assert not asyncio.iscoroutinefunction(wrapped)
    assert wrapped("hi") == "HI"
