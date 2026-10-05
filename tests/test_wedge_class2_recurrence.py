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
import inspect
import re
import sqlite3
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
    # task b02389c2: isolate the HEAVY pool too (capture / store writes /
    # checkpoint run there now), so a stuck-handler orphan can't bleed into a
    # later test's heavy-pool capacity the same way.
    fresh_heavy = ThreadPoolExecutor(max_workers=offload.HEAVY_WORKERS)
    monkeypatch.setattr(offload, "_heavy_pool", fresh_heavy)
    monkeypatch.setattr(offload, "_heavy_inflight", {})
    yield
    fresh_pool.shutdown(wait=False)
    fresh_heavy.shutdown(wait=False)


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


async def test_healthz_stays_responsive_during_a_slow_wal_checkpoint(client, monkeypatch):
    """task 20afcaf7 AC1: the field incident (~60s /healthz stall under a forced
    WAL checkpoint on slow prod disk) reproduced hermetically by making the
    checkpoint itself slow. checkpoint_if_wal_large runs inside
    store._retry_on_locked, post-commit, and /api/capture already dispatches
    capture_state (-> store.put -> the write + its post-commit checkpoint) via
    offload.off_loop — so a slow checkpoint must stall only the offloaded
    thread, never the event loop /healthz shares with every other route."""
    started = threading.Event()

    def _slow_checkpoint(conn, db_path):
        started.set()
        time.sleep(1.0)  # far past the 0.1s budget from _fast_timeout

    monkeypatch.setattr("trovex.store.checkpoint_if_wal_large", _slow_checkpoint)

    capture_task = asyncio.create_task(
        client.post("/api/capture", json={"agent": "y", "summary": "s" * 25})
    )
    while not started.is_set():
        await asyncio.sleep(0.005)

    t0 = time.perf_counter()
    healthz = await client.get("/healthz")
    elapsed = time.perf_counter() - t0

    assert healthz.status_code == 200
    assert elapsed < 0.2, "a slow checkpoint must never delay /healthz"

    await capture_task  # let the offloaded call finish before the fixture tears down


async def test_api_map_stays_off_loop(client, app_state, monkeypatch):
    """task 20afcaf7: /api/map called store.list_docs directly inline on the
    event loop — the same bug class as the mutation routes above, just on the
    read side. A slow store call must not block /healthz either."""
    started = threading.Event()

    def _stuck(*args, **kwargs):
        started.set()
        time.sleep(1.0)
        return []

    monkeypatch.setattr(app_state.store, "list_docs", _stuck)

    task = asyncio.create_task(client.get("/api/map"))
    while not started.is_set():
        await asyncio.sleep(0.005)

    t0 = time.perf_counter()
    healthz = await client.get("/healthz")
    elapsed = time.perf_counter() - t0
    assert healthz.status_code == 200
    assert elapsed < 0.5, "/api/map must not block /healthz while its store call is stuck"

    resp = await task
    assert resp.status_code == 504


async def test_api_stats_stays_off_loop(client, app_state, monkeypatch):
    """task 20afcaf7: /api/stats ran its db.execute() calls directly inline on
    the event loop. sqlite3.Connection is a C type (can't monkeypatch its
    methods in place, same constraint as test_locked_retry_still_works above)
    so swap the whole `searcher.db` attribute for a wrapper that stalls the
    first call."""
    started = threading.Event()
    real_db = app_state.searcher.db

    class _StuckDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, *args, **kwargs):
            started.set()
            time.sleep(1.0)
            raise sqlite3.OperationalError("stuck")

    monkeypatch.setattr(app_state.searcher, "db", _StuckDB())

    task = asyncio.create_task(client.get("/api/stats"))
    while not started.is_set():
        await asyncio.sleep(0.005)

    t0 = time.perf_counter()
    healthz = await client.get("/healthz")
    elapsed = time.perf_counter() - t0
    assert healthz.status_code == 200
    assert elapsed < 0.5, "/api/stats must not block /healthz while its db call is stuck"

    resp = await task
    assert resp.status_code == 504


async def test_api_backup_stays_off_loop(client, monkeypatch):
    """task 20afcaf7 r3: the reviewer flagged this as THE exact wedge-class-2
    pattern the whole ticket is about — backup_mod.make_backup runs a PASSIVE
    checkpoint + Connection.backup() over the full store (~340MB in prod) and
    ran inline in the route handler until now."""
    started = threading.Event()

    def _stuck_make_backup(*args, **kwargs):
        started.set()
        time.sleep(1.0)
        from pathlib import Path

        return Path("unused")

    monkeypatch.setattr("trovex.backup.make_backup", _stuck_make_backup)

    task = asyncio.create_task(client.post("/api/backup"))
    while not started.is_set():
        await asyncio.sleep(0.005)

    t0 = time.perf_counter()
    healthz = await client.get("/healthz")
    elapsed = time.perf_counter() - t0
    assert healthz.status_code == 200
    assert elapsed < 0.5, "/api/backup must not block /healthz while make_backup is stuck"

    resp = await task
    assert resp.status_code == 504


async def test_api_backups_list_stays_off_loop(client, monkeypatch):
    """task 20afcaf7 r3: backup_mod.list_backups globs the backups dir and
    stat()s every file inline — off_loop like every route above."""
    started = threading.Event()

    def _stuck_list_backups(*args, **kwargs):
        started.set()
        time.sleep(1.0)
        return []

    monkeypatch.setattr("trovex.backup.list_backups", _stuck_list_backups)

    task = asyncio.create_task(client.get("/api/backups"))
    while not started.is_set():
        await asyncio.sleep(0.005)

    t0 = time.perf_counter()
    healthz = await client.get("/healthz")
    elapsed = time.perf_counter() - t0
    assert healthz.status_code == 200
    assert elapsed < 0.5, "/api/backups must not block /healthz while list_backups is stuck"

    resp = await task
    assert resp.status_code == 504


async def test_home_page_stays_off_loop(client, monkeypatch):
    """task 20afcaf7 r3: the home page ('/') alone did ~10 db.execute() calls
    inline building its dashboard context — spot-check representative of the
    11 HTML routes the static audit below now covers exhaustively (all wrapped
    via a thin _compute_*_context helper + _offloaded, same as /api/map)."""
    started = threading.Event()
    real_db = state_mod._state.searcher.db

    class _StuckDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, *args, **kwargs):
            started.set()
            time.sleep(1.0)
            raise sqlite3.OperationalError("stuck")

    monkeypatch.setattr(state_mod._state.searcher, "db", _StuckDB())

    task = asyncio.create_task(client.get("/"))
    while not started.is_set():
        await asyncio.sleep(0.005)

    t0 = time.perf_counter()
    healthz = await client.get("/healthz")
    elapsed = time.perf_counter() - t0
    assert healthz.status_code == 200
    assert elapsed < 0.5, "/ must not block /healthz while its db calls are stuck"

    resp = await task
    assert resp.status_code == 504


# task 20afcaf7 r3/r4: the 11 HTML dashboard routes below were previously
# allowlisted as "human-browsed, not on the agent hot path" — but AC3 says
# literally "every route that touches store/db is wrapped by off_loop", and
# the r3 reviewer confirmed each of them DOES touch store/db inline. All 11
# are now off_loop'd for real (a thin _compute_*_context helper + _offloaded)
# instead of reasoned around, so only a genuine regex false-positive stays
# allowlisted.
_ALLOWED_INLINE_ROUTES = {
    "/api/savings/benchmark": (
        "savings_mod.benchmark_result() returns the static packaged corpus-"
        "benchmark result, no live db/store touch — regex false-positive on "
        "'savings_mod.'"
    ),
}

# task 20afcaf7 r3: broadened after the reviewer found 3 gaps — backup_mod
# (make_backup/list_backups: /api/backup, /api/backups), searcher.search (only
# searcher.db was matched), and index_jobs.X — none previously caught, so a
# route calling any of them inline without off_loop passed silently.
_STORE_TOUCH_RE = re.compile(
    r"\bstore\.\w|\bsearcher\.db\b|\bsearcher\.search\(|\bindexer\.db\b|\.db\.execute\(|"
    r"_sources_meta\(|\bsavings_mod\.\w|\binsights_mod\.\w|\bbackup_mod\.\w|\bindex_jobs\.\w"
)
_OFF_LOOP_RE = re.compile(r"off_loop(?:_heavy)?\(|_offloaded\(")


def test_every_store_db_route_is_off_loop_or_allowlisted(app_state):
    """task 20afcaf7 AC3: static audit over the route table — every server.py
    route touching store/searcher/indexer/a `.db` connection either goes
    through off_loop/_offloaded, or is named in _ALLOWED_INLINE_ROUTES with a
    reason. A future route that adds an inline store/db call and forgets
    off_loop fails this test instead of silently reintroducing the wedge.

    Needs the `app_state` fixture: build_app() eagerly calls get_state(),
    and without a pre-populated state it falls back to real Settings() and
    opens the actual configured trovex.db — a bare build_app() here can
    collide with a real running trovex-serve process's WAL lock."""
    app = build_app()
    violations = []
    seen_paths = set()
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        path = getattr(route, "path", None)
        if endpoint is None or path is None:
            continue
        seen_paths.add(path)
        if path in _ALLOWED_INLINE_ROUTES:
            continue
        try:
            src = inspect.getsource(endpoint)
        except (OSError, TypeError):
            continue
        if _STORE_TOUCH_RE.search(src) and not _OFF_LOOP_RE.search(src):
            violations.append(f"{path} ({endpoint.__name__})")
    assert violations == [], f"routes touching store/db without off_loop: {violations}"
    # The allowlist itself must stay honest: every entry must still be a real
    # route (nothing stale left behind once a listed page is removed/renamed).
    stale = set(_ALLOWED_INLINE_ROUTES) - seen_paths
    assert stale == set(), f"_ALLOWED_INLINE_ROUTES has stale entries: {stale}"


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


async def test_heavy_pool_independent_of_recall_pool():
    """b02389c2 AC3 separate pools: a fully saturated HEAVY pool must not occupy
    any RECALL worker — pool_saturated() (recall) stays False and a recall call
    runs immediately while every heavy worker is stuck."""
    import trovex.offload as off

    release = threading.Event()

    def _stuck(i):
        release.wait(timeout=5.0)
        return i

    heavy = [
        asyncio.create_task(off.off_loop_heavy(_stuck, i, timeout=None))
        for i in range(off.HEAVY_WORKERS)
    ]
    try:
        for _ in range(300):  # wait until every heavy worker is occupied
            if len(off._heavy_inflight) >= off.HEAVY_WORKERS:
                break
            await asyncio.sleep(0.01)
        assert len(off._heavy_inflight) >= off.HEAVY_WORKERS
        # recall pool is untouched by the heavy saturation
        assert off.pool_saturated() is False
        assert await off.off_loop(lambda: "recall-ok", timeout=2.0) == "recall-ok"
    finally:
        release.set()
        await asyncio.gather(*heavy)
