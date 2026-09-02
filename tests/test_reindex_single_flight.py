"""Reindex single-flight guard + reader-stays-responsive fix (085f1d69, fast-follow
to eda6f60e).

Root cause: /api/reindex ran state.indexer.reindex() INLINE on the event loop
(no run_in_threadpool) with no concurrency guard, and indexer.reindex() held ONE
write transaction open for the entire corpus scan, committing only at the very
end. Reproduced on prod: firing /api/reindex twice concurrently serialized
readers and grew the WAL 5.8M -> 10M, clearing only with a manual kickstart —
not the ClientDisconnect wedge (that's fixed by eda6f60e), a distinct stall
class.

Fix:
  - api_reindex takes a non-blocking threading.Lock (state.reindex_lock) — a 2nd
    concurrent call gets 409 instead of piling onto the first.
  - indexer.reindex() and store.sweep_bloat() now run via run_in_threadpool, off
    the event loop, so /api/boot and friends stay responsive during a reindex.
  - indexer.reindex() commits + checkpoints every REINDEX_COMMIT_BATCH docs
    instead of holding one txn open for the whole run, bounding WAL growth.

Hermetic: BagEmbedder, no network, no real model download.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import threading
import time

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from trovex import indexer as indexer_mod
from trovex import state as state_mod
from trovex import status as status_mod
from trovex.config import Settings, Source
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


def _stats() -> dict:
    return {
        "added": 0,
        "updated": 0,
        "unchanged": 0,
        "removed": 0,
        "duration_sec": 0.0,
        "status": {},
        "by_source": [],
        "capacity_warnings": [],
    }


@pytest.fixture
def app_state(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",  # dim 384, matches BagEmbedder
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)
    store.put("# Auth flow\n\njwt token signature validation", tags=["owner/alpha"])
    searcher = Searcher(settings, embedder=embedder)
    indexer = Indexer(settings, embedder=embedder)
    state = AppState(
        settings=settings,
        embedder=embedder,
        searcher=searcher,
        indexer=indexer,
        store=store,
    )
    state_mod._state = state
    try:
        yield state
    finally:
        state_mod.reset_state()


@pytest.fixture
def client(app_state):
    transport = ASGITransport(app=build_app())
    return AsyncClient(transport=transport, base_url="http://test")


async def test_second_concurrent_reindex_is_refused(client, app_state, monkeypatch):
    started = threading.Event()  # set from the threadpool worker, not the loop

    def _slow_reindex(*args, **kwargs):
        started.set()
        time.sleep(0.3)
        return _stats()

    monkeypatch.setattr(app_state.indexer, "reindex", _slow_reindex)

    r1_task = asyncio.create_task(client.post("/api/reindex"))
    while not started.is_set():
        await asyncio.sleep(0.01)
    r2 = await client.post("/api/reindex")
    r1 = await r1_task

    assert r1.status_code == 200
    assert r2.status_code == 409
    assert not app_state.reindex_lock.locked(), "lock must be released after the call finishes"


async def test_boot_stays_responsive_during_reindex(client, app_state, monkeypatch):
    def _slow_reindex(*args, **kwargs):
        time.sleep(0.5)
        return _stats()

    monkeypatch.setattr(app_state.indexer, "reindex", _slow_reindex)

    async def boot_call():
        t0 = time.perf_counter()
        r = await client.get("/api/boot", params={"agent": "alpha"})
        return r, time.perf_counter() - t0

    reindex_resp, (boot_resp, boot_elapsed) = await asyncio.gather(
        client.post("/api/reindex"), boot_call()
    )

    assert reindex_resp.status_code == 200
    assert boot_resp.status_code == 200
    assert boot_elapsed < 2.0, "boot must not wait out the in-flight reindex"


def test_reindex_commits_in_bounded_batches(tmp_path, monkeypatch):
    """A large reindex must commit periodically, not hold one txn open for the
    whole corpus — otherwise the WAL grows unbounded for the run's full
    duration (the actual prod symptom)."""
    monkeypatch.setattr(indexer_mod, "REINDEX_COMMIT_BATCH", 3)

    src_root = tmp_path / "src"
    src_root.mkdir()
    for i in range(7):
        (src_root / f"doc{i}.md").write_text(f"# Doc {i}\n\nbody text {i}\n")

    settings = Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    embedder = BagEmbedder()
    indexer = Indexer(settings, embedder=embedder)

    commit_calls = 0
    real_commit_progress = indexer._commit_progress

    def _counting_commit_progress(embed_batch, chunk_embed_batch):
        nonlocal commit_calls
        commit_calls += 1
        return real_commit_progress(embed_batch, chunk_embed_batch)

    monkeypatch.setattr(indexer, "_commit_progress", _counting_commit_progress)

    stats = indexer.reindex(sources=[Source(id="t", label="t", root=src_root)])

    assert stats["added"] == 7
    # 7 docs / batch-of-3 => 2 mid-run commits via _commit_progress (the final
    # commit at reindex()'s tail is separate, not counted here).
    assert commit_calls >= 2, f"expected periodic commits mid-reindex, got {commit_calls}"


def test_concurrent_write_stays_fast_during_compute_status(tmp_path, monkeypatch):
    """compute_status's Pass 1 (status.py) must commit periodically, not hold
    the write lock for its whole file-I/O scan — the write-cost P2 root cause:
    compute_status ran as one uncommitted full-corpus txn (~5510 docs prod),
    blocking store.put()'s busy_timeout/_retry_on_locked. A concurrent write on
    a SEPARATE connection to the same db file (WAL, same as a live server's
    store.db vs indexer.db split) must complete in well under the full pass
    duration, not wait it out."""
    monkeypatch.setattr(indexer_mod, "REINDEX_COMMIT_BATCH", 3)

    src_root = tmp_path / "src"
    src_root.mkdir()
    n_docs = 30
    for i in range(n_docs):
        # Every 3rd doc's filename matches settings.plan_path_patterns ("DRAFT"),
        # so Pass 1 actually performs a status UPDATE on it — otherwise every row
        # is a no-op and the periodic in-loop db.commit() (status.py ~148-149)
        # would never be exercised by this test at all.
        name = f"docDRAFT{i}.md" if i % 3 == 0 else f"doc{i}.md"
        (src_root / name).write_text(f"# Doc {i}\n\nbody text {i}\n")

    settings = Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    embedder = BagEmbedder()
    indexer = Indexer(settings, embedder=embedder)
    indexer.reindex(sources=[Source(id="t", label="t", root=src_root)])

    # Slow Pass 1's per-doc file reads so the pass takes long enough to make
    # lock-release timing measurable, and signal once it's clearly mid-flight
    # (past the first REINDEX_COMMIT_BATCH commit).
    real_read_head = status_mod._read_head
    calls = 0
    mid_pass = threading.Event()

    def _slow_read_head(path, n):
        nonlocal calls
        calls += 1
        if calls == 8:
            mid_pass.set()
        time.sleep(0.05)
        return real_read_head(path, n)

    monkeypatch.setattr(status_mod, "_read_head", _slow_read_head)

    result: dict = {}

    def _run_compute_status():
        result["stats"] = status_mod.compute_status(indexer.db, settings)

    # Open the writer's connection (open_db's migrations run their own write
    # statements against the same file) BEFORE the slow pass starts — opening
    # it mid-pass would itself block on the held lock and silently absorb the
    # wait this test exists to measure, passing even on pre-fix code.
    writer_store = SqliteStore(settings, embedder=embedder)

    thread = threading.Thread(target=_run_compute_status)
    t0 = time.perf_counter()
    thread.start()
    assert mid_pass.wait(timeout=5.0), "compute_status never reached the mid-pass marker"

    write_t0 = time.perf_counter()
    writer_store.put("# Concurrent probe\n\nmust not wait out the whole pass", tags=["probe"])
    write_elapsed = time.perf_counter() - write_t0

    thread.join(timeout=10.0)
    total_elapsed = time.perf_counter() - t0

    assert not thread.is_alive(), "compute_status thread did not finish"
    assert "stats" in result
    assert total_elapsed > 1.0, "pass wasn't actually slow enough to be a measurable test"
    assert write_elapsed < 1.0, (
        f"concurrent write waited {write_elapsed:.2f}s (pass took {total_elapsed:.2f}s total) "
        "— compute_status must release the write lock between batches"
    )


def test_concurrent_write_stays_fast_during_low_change_ratio_scan(tmp_path, monkeypatch):
    """Task 3771564e (prod P1, 2026-09-02): REINDEX_COMMIT_BATCH is a
    CHANGE-count threshold — it only advances on a real add/update, so a run
    with few real changes relative to many unchanged docs (prod: 25 added vs
    11160 unchanged, well under the 200-doc batch) never reaches it. The
    whole scan stayed one open transaction for its full wall-clock duration
    however long the unchanged docs took to walk (confirmed live: a lone
    in-progress reindex, no other writer, still made trovex_write time out at
    30s). REINDEX_COMMIT_INTERVAL_SEC must flush on elapsed time regardless
    of the change/unchanged ratio, checked on every scanned path (not only
    ones that write) so it also fires mid-run-of-unchanged-docs."""
    monkeypatch.setattr(indexer_mod, "REINDEX_COMMIT_INTERVAL_SEC", 0.3)

    src_root = tmp_path / "src"
    src_root.mkdir()
    n_docs = 40
    for i in range(n_docs):
        (src_root / f"doc{i}.md").write_text(f"# Doc {i}\n\nbody text {i}\n")

    settings = Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    embedder = BagEmbedder()
    indexer = Indexer(settings, embedder=embedder)
    # Seed: first pass makes every doc "existing" with a stable mtime.
    indexer.reindex(sources=[Source(id="t", label="t", root=src_root)])

    # Half the docs get real new content (real writes, since_commit-worthy);
    # the rest keep their seeded mtime (the fast-path "unchanged" branch).
    # Spread real changes through the set (not just one) so REGARDLESS of
    # scan order, since_commit is already > 0 well before the test's
    # mid-scan marker — otherwise an unlucky order could scan every
    # unchanged doc first and never actually exercise the time-based flush.
    # Total changes (20) stays well under REINDEX_COMMIT_BATCH (200), so the
    # existing count-based path provably never fires on its own here.
    for i in range(0, n_docs, 2):
        (src_root / f"doc{i}.md").write_text(f"# Doc {i} UPDATED\n\nnew body {i}\n")

    # Slow _accept — called for EVERY scanned path (changed or not) — so
    # walking 40 mostly-quick files takes long enough to make lock-release
    # timing measurable. Same technique as the compute_status test above
    # (_slow_read_head), scoped to one method, no real I/O slowdown needed.
    real_accept = Indexer._accept
    calls = 0
    mid_scan = threading.Event()

    def _slow_accept(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 10:
            mid_scan.set()
        time.sleep(0.05)
        return real_accept(self, *args, **kwargs)

    monkeypatch.setattr(Indexer, "_accept", _slow_accept)

    result: dict = {}

    def _run_reindex():
        result["stats"] = indexer.reindex(sources=[Source(id="t", label="t", root=src_root)])

    # Open the writer's connection BEFORE the slow scan starts — opening it
    # mid-scan would itself block on a held lock and silently absorb the
    # wait this test exists to measure, passing even on pre-fix code.
    writer_store = SqliteStore(settings, embedder=embedder)

    thread = threading.Thread(target=_run_reindex)
    t0 = time.perf_counter()
    thread.start()
    assert mid_scan.wait(timeout=5.0), "scan never reached the mid-scan marker"

    write_t0 = time.perf_counter()
    writer_store.put("# Concurrent probe\n\nmust not wait out the whole scan", tags=["probe"])
    write_elapsed = time.perf_counter() - write_t0

    thread.join(timeout=10.0)
    total_elapsed = time.perf_counter() - t0

    assert not thread.is_alive(), "reindex thread did not finish"
    assert "stats" in result
    assert result["stats"]["added"] == 0
    assert result["stats"]["updated"] == 20
    assert total_elapsed > 1.0, "scan wasn't actually slow enough to be a measurable test"
    assert write_elapsed < 1.0, (
        f"concurrent write waited {write_elapsed:.2f}s (scan took {total_elapsed:.2f}s total) "
        "— reindex must release the write lock on elapsed time, not just change count"
    )
