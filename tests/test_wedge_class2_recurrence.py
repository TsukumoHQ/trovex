"""Wedge class 2 RECURRENCE (task f2b4c872, 2026-08-31 — despite 33ca98a).

Root cause, confirmed from a LIVE thread dump on the wedged prod process
(macOS `sample`, py-spy needed unavailable sudo): the main event-loop thread
itself was inside `onnxruntime::InferenceSession::Run` (embedding inference,
CPU-bound, spin-waits its own worker threads — the 400%+ CPU) reached via a
plain coroutine chain, NOT via any threadpool/executor thread. 33ca98a
off-loaded the 9 MCP `@mcp.tool()` handlers but never touched FastAPI's own
routes: `/api/capture` called `capture_state()` -> `store.put()` ->
`embedder.embed()` INLINE inside its `async def`, and several doc-mutation
routes (`/api/doc/{id}/restore`, `/api/doc/{id}/undelete`, which re-embed via
`put()`; delete/tags/collections, which hit `_retry_on_locked`'s real
`time.sleep` backoff) did the same. Because the LOOP THREAD ITSELF is the one
stuck in synchronous/native code, no coroutine can run — including
`asyncio.wait_for`'s own timeout callback, which is why the existing
TROVEX_TOOL_TIMEOUT_SEC fix never fired, and why even bare `/healthz`
(zero blocking work) went dark.

Fix: every blocking call site (MCP tools AND FastAPI routes) now goes through
`offload.off_loop` — a single dedicated, size-bounded ThreadPoolExecutor
(offload.py), instead of each route inlining its own blocking call or using
the shared/unbounded default. A watchdog (`offload.run_watchdog`) self-heals
if the pool is ever fully saturated by orphaned (past-deadline) calls for too
long — the same recovery `launchctl kickstart` already does manually today,
automated.

Hermetic: BagEmbedder, no network, no real model download.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from trovex import offload
from trovex import state as state_mod
from trovex.config import Settings
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.server import build_app
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
def app_state(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",  # dim 384, matches BagEmbedder
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)
    doc_ext_id = store.put("# Auth flow\n\njwt token signature validation", tags=["owner/alpha"])
    state = AppState(
        settings=settings,
        embedder=embedder,
        searcher=Searcher(settings, embedder=embedder),
        indexer=Indexer(settings, embedder=embedder),
        store=store,
    )
    state.doc_ext_id = doc_ext_id  # type: ignore[attr-defined]
    state_mod._state = state
    try:
        yield state
    finally:
        state_mod.reset_state()


@pytest.fixture
def client(app_state):
    transport = ASGITransport(app=build_app())
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def _isolated_offload_pool(monkeypatch):
    """`offload._pool`/`_inflight` are module-level singletons shared by the
    whole process — a stuck-handler test from earlier in this file can leave
    a REAL orphaned thread still running in the pool when a later test
    starts, silently eating one of its worker slots and pool queue capacity
    (that's the realistic behavior in prod, but makes tests order-dependent).
    Give every test in this module its own fresh pool + `_inflight` dict so
    an orphan thread a test deliberately creates can never bleed into a later
    test's pool capacity. Deliberately does NOT reset `_next_id`: a leaked
    thread's done-callback closes over its `cid` and fires whenever it
    happens to actually finish, popping that `cid` from whatever `_inflight`
    dict is CURRENTLY bound — if ids were reused per test, a stale callback
    from test A could silently evict a live entry from test C's dict."""
    fresh_pool = ThreadPoolExecutor(max_workers=offload.OFFLOAD_MAX_WORKERS)
    monkeypatch.setattr(offload, "_pool", fresh_pool)
    monkeypatch.setattr(offload, "_inflight", {})
    yield
    fresh_pool.shutdown(wait=False)


@pytest.fixture(autouse=True)
def _fast_timeout(monkeypatch):
    """Small tool budget so a stuck handler's real sleep isn't waited out."""
    monkeypatch.setattr(offload, "TOOL_TIMEOUT_SEC", 0.1)


async def test_healthz_stays_responsive_while_capture_is_stuck(client, monkeypatch):
    """The exact reported symptom (f2b4c872): a stuck /api/capture must NOT
    freeze /healthz on the shared event loop. This is what a plain-`def`
    inline call (the actual bug) fails, and what routing through
    offload.off_loop fixes: the loop stays free to service other routes even
    while the offloaded call is still running past its own deadline."""
    started = threading.Event()

    def _stuck_capture_state(*args, **kwargs):
        started.set()
        time.sleep(1.0)  # far past the 0.1s budget from _fast_timeout
        return {"captured": True, "doc_id": "owner-x-current-state", "tokens": 1}

    monkeypatch.setattr("trovex.server.capture_state", _stuck_capture_state)

    capture_task = asyncio.create_task(
        client.post("/api/capture", json={"agent": "x", "summary": "s" * 25})
    )
    while not started.is_set():
        await asyncio.sleep(0.005)

    t0 = time.perf_counter()
    healthz = await client.get("/healthz")
    elapsed = time.perf_counter() - t0

    assert healthz.status_code == 200
    assert healthz.text == "ok"
    assert elapsed < 0.5, "healthz must answer promptly, not wait behind the stuck capture"

    capture_resp = await capture_task
    assert capture_resp.status_code == 504
    assert capture_resp.json()["captured"] is False


async def test_capture_times_out_bounded_not_unbounded(client, monkeypatch):
    """A capture stuck past TOOL_TIMEOUT_SEC returns a bounded error instead
    of the request hanging indefinitely (the reported symptom: the wedge
    lasted 8+ minutes with no response at all)."""

    def _stuck(*args, **kwargs):
        time.sleep(5.0)
        return {"captured": True}

    monkeypatch.setattr("trovex.server.capture_state", _stuck)

    t0 = time.perf_counter()
    resp = await client.post("/api/capture", json={"agent": "x", "summary": "s" * 25})
    elapsed = time.perf_counter() - t0

    assert elapsed < 1.0, "must be bounded by TOOL_TIMEOUT_SEC, not the handler's real 5s"
    assert resp.status_code == 504


async def test_fast_capture_is_unaffected(client, app_state):
    """The common case still returns a real result, not a timeout."""
    resp = await client.post(
        "/api/capture", json={"agent": "someone", "summary": "did the thing " * 4}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["captured"] is True
    assert app_state.store.get("owner-someone-current-state") is not None


@pytest.mark.parametrize(
    ("route", "method", "store_attr", "body"),
    [
        ("/api/doc/{ext_id}/restore", "post", "restore_version", {"version_id": 1}),
        ("/api/doc/{ext_id}/undelete", "post", "restore_deleted", None),
        ("/api/doc/{ext_id}", "delete", "delete", None),
        ("/api/doc/{ext_id}/tags", "post", "set_tags", {"add": "x"}),
    ],
)
async def test_doc_mutation_routes_stay_off_loop(
    client, app_state, monkeypatch, route, method, store_attr, body
):
    """Every write route that touches the store (delete/restore/undelete/tags)
    goes through offload.off_loop now — none of them may run their store call
    inline and block /healthz, whether the slow part is re-embedding
    (restore/undelete, via put()) or a retry-on-locked backoff (delete/tags)."""
    started = threading.Event()

    def _stuck(*args, **kwargs):
        started.set()
        time.sleep(1.0)
        return True

    monkeypatch.setattr(app_state.store, store_attr, _stuck)

    url = route.format(ext_id=app_state.doc_ext_id)
    call = getattr(client, method)
    kwargs = {"json": body} if body is not None else {}
    task = asyncio.create_task(call(url, **kwargs))
    while not started.is_set():
        await asyncio.sleep(0.005)

    t0 = time.perf_counter()
    healthz = await client.get("/healthz")
    elapsed = time.perf_counter() - t0
    assert healthz.status_code == 200
    assert elapsed < 0.5, f"{route} must not block /healthz while its store call is stuck"

    resp = await task
    # Every route wraps its off_loop call in _offloaded, which converts a
    # TimeoutError into a clean 504 — never a hang for the stuck call's real
    # 1s, and never an unhandled-exception 500 either.
    assert resp.status_code == 504


async def test_off_loop_pool_is_bounded_orphans_dont_grow_it_unbounded():
    """OFFLOAD_MAX_WORKERS bounds the dedicated pool. Firing more concurrent
    stuck calls than the pool has workers must NOT create unbounded threads —
    the excess simply queues (and each still gets its own bounded timeout,
    never an unbounded wait)."""
    n = offload.OFFLOAD_MAX_WORKERS + 2

    def _stuck(i):
        time.sleep(0.3)
        return i

    async def _call(i):
        try:
            return await offload.off_loop(_stuck, i, timeout=0.05)
        except TimeoutError:
            return "timeout"

    t0 = time.perf_counter()
    results = await asyncio.gather(*[_call(i) for i in range(n)])
    elapsed = time.perf_counter() - t0

    assert all(r == "timeout" for r in results)
    # Every call is individually bounded (0.05s) — even the ones queued behind
    # a full pool return in well under the stuck call's real 0.3s runtime,
    # not "however long it takes for a slot to free up".
    assert elapsed < 0.3


async def test_saturated_for_zero_when_pool_not_full():
    assert offload.saturated_for() == 0.0


async def test_saturated_for_ignores_unbounded_calls(monkeypatch):
    """A deliberately-unbounded call (timeout=None, e.g. /api/reindex) must
    never count as 'orphaned', however long it runs — only calls past their
    OWN deadline do."""
    monkeypatch.setattr(offload, "OFFLOAD_MAX_WORKERS", 1)
    started = threading.Event()
    release = threading.Event()

    def _long_unbounded():
        started.set()
        release.wait(timeout=2.0)
        return "ok"

    task = asyncio.create_task(offload.off_loop(_long_unbounded, timeout=None))
    try:
        while not started.is_set():
            await asyncio.sleep(0.005)
        await asyncio.sleep(0.2)  # well past a normal TOOL_TIMEOUT_SEC-style deadline
        assert offload.saturated_for() == 0.0
    finally:
        release.set()
        await task


async def test_watchdog_self_heals_on_sustained_saturation(monkeypatch):
    """If every pool slot is occupied by a call past ITS OWN deadline for
    WATCHDOG_SATURATION_SEC straight, the watchdog must call its self-heal
    hook (process restart in prod; injectable here for the test) instead of
    silently staying wedged forever."""
    monkeypatch.setattr(offload, "OFFLOAD_MAX_WORKERS", 2)
    monkeypatch.setattr(offload, "WATCHDOG_SATURATION_SEC", 0.05)
    monkeypatch.setattr(offload, "WATCHDOG_POLL_SEC", 0.02)
    monkeypatch.setattr(offload, "TOOL_TIMEOUT_SEC", 0.02)

    release = threading.Event()

    def _stuck():
        release.wait(timeout=3.0)
        return "ok"

    calls = [asyncio.create_task(_awaited_ignore_timeout(offload.off_loop(_stuck, timeout=0.02)))]
    calls.append(
        asyncio.create_task(_awaited_ignore_timeout(offload.off_loop(_stuck, timeout=0.02)))
    )

    wedged = asyncio.Event()

    def _on_wedged():
        wedged.set()

    watchdog_task = asyncio.create_task(offload.run_watchdog(on_wedged=_on_wedged))
    try:
        await asyncio.wait_for(wedged.wait(), timeout=2.0)
    finally:
        release.set()
        watchdog_task.cancel()
        for c in calls:
            await c


async def _awaited_ignore_timeout(coro):
    try:
        return await coro
    except TimeoutError:
        return "timeout"


async def test_watchdog_disabled_when_saturation_sec_zero(monkeypatch):
    monkeypatch.setattr(offload, "WATCHDOG_SATURATION_SEC", 0)
    calls = {"n": 0}

    def _on_wedged():
        calls["n"] += 1

    # Should return immediately (disabled), never touching on_wedged.
    await asyncio.wait_for(offload.run_watchdog(on_wedged=_on_wedged), timeout=1.0)
    assert calls["n"] == 0
