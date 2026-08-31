"""Wedge class 3 (task 8640b88b, successor to f2b4c872/33ca98a): MCP
`@mcp.resource` handlers ran INLINE on the event loop — 33ca98a and eda6f60e
off-loaded every `@mcp.tool()` handler and every FastAPI route, but the 6
`@mcp.resource` handlers in mcp_app.py (savings/deleted/catalog) were never
touched. Live prod sample (2026-08-31 15:47-48Z) showed the main thread stuck
in `sqliteDefaultBusyCallback -> unixSleep`: an orphaned writer held the WAL
lock, and a resource handler's inline `db.execute()` blocked on
`busy_timeout=30000` (30s) directly on the loop thread — the exact class-2
symptom, just via a different call site.

`_off_loop_resource` (mcp_app.py) is the resource analogue of `_off_loop`:
it registers an async twin that runs the handler via `offload.off_loop`
(bounded pool + wall-clock budget), so a stuck read times out bounded by
`TOOL_TIMEOUT_SEC` instead of the loop blocking up to sqlite's 30s
`busy_timeout`. Unlike tools, a timeout degrades to a plain markdown string
(matching `/api/boot`'s degrade-to-empty-pack contract), not the tool-only
CCAR `_err()` JSON shape.

Hermetic: bag embedder, no network, no real model download.
"""

from __future__ import annotations

import hashlib
import re
import time

import numpy as np
import pytest

from trovex import mcp_app
from trovex import state as state_mod
from trovex import offload
from trovex.config import Settings
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.state import AppState
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
def state(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    emb = BagEmbedder()
    store = SqliteStore(settings, embedder=emb)
    store.put("# Owned record\n\nalpha body", tags=["owner/alpha"])
    state_mod._state = AppState(
        settings=settings,
        embedder=emb,
        searcher=Searcher(settings, embedder=emb),
        indexer=Indexer(settings, embedder=emb),
        store=store,
    )
    try:
        yield state_mod._state
    finally:
        state_mod.reset_state()


@pytest.fixture(autouse=True)
def _fast_timeout(monkeypatch):
    """Small tool budget so a stuck handler's real sleep isn't waited out."""
    monkeypatch.setattr(mcp_app, "TOOL_TIMEOUT_SEC", 0.05)


class _StuckDB:
    """Wraps a real sqlite3.Connection so `.execute` blocks like a writer
    holding the WAL lock past `busy_timeout` — sqlite3.Connection itself
    forbids attribute overrides (`execute` is a read-only slot), so the
    handler's `db` attribute is swapped for this proxy instead."""

    def __init__(self, real, delay: float):
        self._real = real
        self._delay = delay

    def execute(self, *args, **kwargs):
        time.sleep(self._delay)
        return self._real.execute(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


async def test_stuck_resource_read_times_out_instead_of_hanging():
    """Mechanism test (mirrors test_wedge_class2.py's slow_tool): a handler
    registered through `_off_loop_resource` that blocks past the budget must
    return promptly with a degraded body, not hang for its real runtime."""
    calls: list[str] = []

    def _slow_resource() -> str:
        calls.append("start")
        time.sleep(1.0)
        calls.append("end")  # only reached if the orphaned thread finishes
        return "should never surface"

    mcp_app._off_loop_resource("trovex://_test/slow", name="_test_slow", mime_type="text/markdown")(
        _slow_resource
    )

    t0 = time.perf_counter()
    contents = await mcp_app.mcp.read_resource("trovex://_test/slow")
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.5, "must return promptly, not wait out the stuck read's full 1s"
    body = contents[0].content
    assert "temporarily unavailable" in body
    assert "should never surface" not in body


async def test_stuck_resource_template_read_times_out_instead_of_hanging():
    """Same mechanism, for a `{param}` templated resource — the class of
    handler `savings_for_session`/`catalog_for_source` belong to."""

    def _slow_template(x: str) -> str:
        time.sleep(1.0)
        return f"should never surface: {x}"

    mcp_app._off_loop_resource(
        "trovex://_test/slow/{x}", name="_test_slow_tpl", mime_type="text/markdown"
    )(_slow_template)

    t0 = time.perf_counter()
    contents = await mcp_app.mcp.read_resource("trovex://_test/slow/abc")
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.5
    body = contents[0].content
    assert "temporarily unavailable" in body
    assert "should never surface" not in body


async def test_fast_resource_read_is_unaffected(state):
    """The common case still returns the real markdown, not a timeout."""
    contents = await mcp_app.mcp.read_resource("trovex://sources")
    assert "temporarily unavailable" not in contents[0].content
    assert "trovex" in contents[0].content


async def test_orphaned_writer_lock_degrades_bounded_not_30s_busy_timeout(state, monkeypatch):
    """The reported prod symptom: a real resource handler (`catalog_sources`)
    whose inline `db.execute()` would otherwise block on sqlite's
    `busy_timeout=30000` because an orphaned writer holds the WAL lock. Must
    degrade bounded by `TOOL_TIMEOUT_SEC` (monkeypatched to 0.05s here), not
    block anywhere near the real 30s busy_timeout."""
    monkeypatch.setattr(state.searcher, "db", _StuckDB(state.searcher.db, delay=2.0))

    t0 = time.perf_counter()
    contents = await mcp_app.mcp.read_resource("trovex://sources")
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.5, "must be bounded by TOOL_TIMEOUT_SEC, not the writer's real 2s hold"
    assert "temporarily unavailable" in contents[0].content


def test_off_loop_resource_leaves_module_level_name_synchronous(state):
    """Direct/test callers (`mcp_app.catalog_sources()` etc., used throughout
    test_mcp_resources.py) must keep getting a plain sync function back —
    only the FastMCP-registered twin is async."""
    import inspect

    assert not inspect.iscoroutinefunction(mcp_app.catalog_sources)
    assert isinstance(mcp_app.catalog_sources(), str)


@pytest.fixture(autouse=True)
def _isolated_offload_pool(monkeypatch):
    """See test_wedge_class2_recurrence.py — give every test its own pool so
    a deliberately-orphaned thread from one test can't eat a later test's
    worker slot."""
    from concurrent.futures import ThreadPoolExecutor

    fresh_pool = ThreadPoolExecutor(max_workers=offload.OFFLOAD_MAX_WORKERS)
    monkeypatch.setattr(offload, "_pool", fresh_pool)
    monkeypatch.setattr(offload, "_inflight", {})
    yield
    fresh_pool.shutdown(wait=False)
