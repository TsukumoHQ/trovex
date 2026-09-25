"""index_jobs op-log + single applier thread (task dab8766b).

Replaces 085f1d69/67ebd68c's per-request reindex_lock: /api/reindex now
enqueues into index_jobs and returns 202 immediately; a single background
Applier thread drains the queue, so Indexer.reindex()/reindex_paths() are
never called from two threads at once. A request arriving while its match is
already queued coalesces onto it (paths unioned); a request arriving while its
match is already PROCESSING flags rerun_after instead of a bare rejection or a
second row, so no caller's trigger is ever dropped.

Hermetic: BagEmbedder, no network, no real model download.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time

import numpy as np
import yaml
from fastapi.testclient import TestClient

from trovex import index_jobs
from trovex import state as state_mod
from trovex.config import Settings
from trovex.index_jobs import Applier
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


class TxnCheckingEmbedder(BagEmbedder):
    """Records whether the caller's sqlite connection had an open transaction
    at the moment embed() was invoked (cbb8e8fb's AC, re-asserted through the
    applier path here rather than a direct Indexer.reindex() call)."""

    def __init__(self, db) -> None:
        self._db = db
        self.saw_open_transaction = False
        self.embedded: list[str] = []

    def embed(self, texts):
        if self._db.in_transaction:
            self.saw_open_transaction = True
        yield from super().embed(list(texts))
        self.embedded.extend(texts)


def _settings_with_source(tmp_path, root) -> Settings:
    """A real sources.yaml — matches how /api/reindex resolves sources in
    prod (Indexer.reindex() with no explicit `sources=` reads this), unlike
    most other indexer tests which pass an explicit sources list directly."""
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(yaml.safe_dump({"sources": [{"id": "code", "label": "repo", "root": str(root)}]}))
    return Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=cfg,
    )


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# ── enqueue(): coalescing (AC1 core, AC2) ──────────────────────────────────


def test_enqueue_coalesces_repeated_scan_source_while_queued(tmp_path):
    idx = Indexer(_settings_with_source(tmp_path, tmp_path / "repo"), embedder=BagEmbedder())
    lock = threading.Lock()
    r1 = index_jobs.enqueue(idx.db, lock, "scan_source")
    r2 = index_jobs.enqueue(idx.db, lock, "scan_source")
    r3 = index_jobs.enqueue(idx.db, lock, "scan_source")

    assert r1["job_id"] == r2["job_id"] == r3["job_id"], "3 enqueues while queued must be ONE row"
    assert r1["coalesced"] is False
    assert r2["coalesced"] is True and r3["coalesced"] is True
    assert idx.db.execute("SELECT COUNT(*) AS c FROM index_jobs").fetchone()["c"] == 1


def test_enqueue_unions_paths_for_same_source_while_queued(tmp_path):
    idx = Indexer(_settings_with_source(tmp_path, tmp_path / "repo"), embedder=BagEmbedder())
    lock = threading.Lock()
    r1 = index_jobs.enqueue(idx.db, lock, "paths", source_key="code", paths=["a.md"])
    r2 = index_jobs.enqueue(idx.db, lock, "paths", source_key="code", paths=["b.md", "a.md"])

    assert r1["job_id"] == r2["job_id"]
    job = index_jobs.get_job(idx.db, r1["job_id"])
    assert sorted(job["payload"]["paths"]) == ["a.md", "b.md"]
    assert idx.db.execute("SELECT COUNT(*) AS c FROM index_jobs").fetchone()["c"] == 1


def test_enqueue_different_source_key_gets_its_own_job(tmp_path):
    idx = Indexer(_settings_with_source(tmp_path, tmp_path / "repo"), embedder=BagEmbedder())
    lock = threading.Lock()
    r_a = index_jobs.enqueue(idx.db, lock, "paths", source_key="a", paths=["x.md"])
    r_b = index_jobs.enqueue(idx.db, lock, "paths", source_key="b", paths=["y.md"])

    assert r_a["job_id"] != r_b["job_id"]
    assert idx.db.execute("SELECT COUNT(*) AS c FROM index_jobs").fetchone()["c"] == 2


def test_enqueue_while_processing_flags_rerun_after_not_a_new_row(tmp_path):
    idx = Indexer(_settings_with_source(tmp_path, tmp_path / "repo"), embedder=BagEmbedder())
    lock = threading.Lock()
    r1 = index_jobs.enqueue(idx.db, lock, "scan_source")
    idx.db.execute("UPDATE index_jobs SET state = 'processing' WHERE id = ?", (r1["job_id"],))
    idx.db.commit()

    r2 = index_jobs.enqueue(idx.db, lock, "scan_source")

    assert r2["job_id"] == r1["job_id"], "a request during a running scan must not insert a new row"
    assert r2["coalesced"] is True
    assert idx.db.execute("SELECT COUNT(*) AS c FROM index_jobs").fetchone()["c"] == 1
    job = index_jobs.get_job(idx.db, r1["job_id"])
    assert job["rerun_after"] == 1


# ── Applier: single writer, rerun-after chains onto the SAME row ──────────


def test_applier_run_one_executes_a_scan_source_job(tmp_path):
    root = tmp_path / "repo"
    _write(root, "a.md", "# A\n\nalpha body")
    idx = Indexer(_settings_with_source(tmp_path, root), embedder=BagEmbedder())
    lock = threading.Lock()
    r1 = index_jobs.enqueue(idx.db, lock, "scan_source")

    applier = Applier(idx, lock=lock)
    ran = applier.run_one()

    assert ran is True
    job = index_jobs.get_job(idx.db, r1["job_id"])
    assert job["state"] == "succeeded"
    assert idx.db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"] == 1
    run_row = idx.db.execute("SELECT job_id FROM index_runs ORDER BY id DESC LIMIT 1").fetchone()
    assert run_row["job_id"] == r1["job_id"], "the index_runs row must link back to the job"


def test_applier_rerun_after_reruns_the_same_row_not_a_new_job(tmp_path):
    """The core AC1 behavior: flag set while processing -> applier reruns the
    SAME job immediately after finishing, no new row, no dropped trigger."""
    root = tmp_path / "repo"
    _write(root, "a.md", "# A\n\nalpha body")
    idx = Indexer(_settings_with_source(tmp_path, root), embedder=BagEmbedder())
    lock = threading.Lock()
    r1 = index_jobs.enqueue(idx.db, lock, "scan_source")

    applier = Applier(idx, lock=lock)
    real_execute = applier._execute
    calls = []

    def _tracking_execute(kind, payload, job_id):
        calls.append(job_id)
        if len(calls) == 1:
            # A 2nd caller's request lands WHILE this first execution is
            # still "running" (from the queue's point of view the row is
            # 'processing' right now) — exactly enqueue()'s processing branch.
            index_jobs.enqueue(idx.db, lock, "scan_source")
        return real_execute(kind, payload, job_id)

    applier._execute = _tracking_execute
    applier.run_one()  # drains the rerun_after chain internally in one call

    assert calls == [r1["job_id"], r1["job_id"]], "must re-run the SAME job id, not a new one"
    assert idx.db.execute("SELECT COUNT(*) AS c FROM index_jobs").fetchone()["c"] == 1
    job = index_jobs.get_job(idx.db, r1["job_id"])
    assert job["state"] == "succeeded"
    assert job["rerun_after"] == 0


def test_applier_no_open_transaction_during_embed(tmp_path):
    """AC3: every applier write batch is BEGIN IMMEDIATE ... COMMIT with
    embeddings computed before BEGIN — re-asserts cbb8e8fb's fix still holds
    when the run is driven by the applier, not a direct reindex() call."""
    root = tmp_path / "repo"
    for i in range(5):
        _write(root, f"doc{i}.md", f"# Doc {i}\n\nunique body {i}")
    idx = Indexer(_settings_with_source(tmp_path, root), embedder=BagEmbedder())
    embedder = TxnCheckingEmbedder(idx.db)
    idx.embedder = embedder
    lock = threading.Lock()
    index_jobs.enqueue(idx.db, lock, "scan_source")

    Applier(idx, lock=lock).run_one()

    assert embedder.embedded, "the fixture must actually exercise embed()"
    assert not embedder.saw_open_transaction, (
        "a transaction was open on the applier's connection when embed() ran"
    )


def test_applier_recovers_a_job_left_processing_at_startup(tmp_path):
    """AC4: a job left 'processing' (the process crashed mid-run) is re-run
    to completion, not stuck forever."""
    root = tmp_path / "repo"
    _write(root, "a.md", "# A\n\nalpha body")
    idx = Indexer(_settings_with_source(tmp_path, root), embedder=BagEmbedder())
    lock = threading.Lock()
    r1 = index_jobs.enqueue(idx.db, lock, "scan_source")
    # Simulate a crash: claimed but never finished.
    idx.db.execute(
        "UPDATE index_jobs SET state = 'processing', started_at = ? WHERE id = ?",
        (1_700_000_000.0, r1["job_id"]),
    )
    idx.db.commit()

    applier = Applier(idx, lock=lock)
    # start() runs recovery synchronously (state -> 'queued') THEN launches the
    # background thread, which races to claim it immediately — so observe the
    # outcome by polling, not by calling run_one() ourselves (that would race
    # the same thread for the same row).
    applier.start()
    try:
        deadline = time.monotonic() + 5.0
        job = index_jobs.get_job(idx.db, r1["job_id"])
        while job["state"] not in ("succeeded", "failed") and time.monotonic() < deadline:
            time.sleep(0.02)
            job = index_jobs.get_job(idx.db, r1["job_id"])
    finally:
        applier.stop()

    assert job["state"] == "succeeded", f"recovered job never completed: {job}"
    assert idx.db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"] == 1


# ── HTTP: /api/reindex enqueues + 202, never 409 ───────────────────────────


def test_api_reindex_returns_202_with_job_id(tmp_path):
    settings = _settings_with_source(tmp_path, tmp_path / "repo")
    settings.write_token = settings.resolve_write_token()
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)
    searcher = Searcher(settings, embedder=embedder)
    indexer = Indexer(settings, embedder=embedder)
    state_mod._state = AppState(
        settings=settings, embedder=embedder, searcher=searcher, indexer=indexer, store=store
    )
    try:
        client = TestClient(build_app())
        r1 = client.post("/api/reindex", headers={"x-trovex-write-token": settings.write_token})
        r2 = client.post("/api/reindex", headers={"x-trovex-write-token": settings.write_token})

        assert r1.status_code == 202
        assert r2.status_code == 202
        assert "job_id" in r1.json()
        assert r2.json()["coalesced"] is True
        assert r2.json()["job_id"] == r1.json()["job_id"]

        status = client.get(f"/api/reindex/{r1.json()['job_id']}")
        assert status.status_code == 200
        assert status.json()["state"] in ("queued", "processing", "succeeded")
    finally:
        state_mod.reset_state()


def test_api_reindex_status_404_for_unknown_job(tmp_path):
    settings = _settings_with_source(tmp_path, tmp_path / "repo")
    settings.write_token = settings.resolve_write_token()
    embedder = BagEmbedder()
    state_mod._state = AppState(
        settings=settings,
        embedder=embedder,
        searcher=Searcher(settings, embedder=embedder),
        indexer=Indexer(settings, embedder=embedder),
        store=SqliteStore(settings, embedder=embedder),
    )
    try:
        client = TestClient(build_app())
        assert client.get("/api/reindex/999999").status_code == 404
    finally:
        state_mod.reset_state()
