"""The reindex op-log + single applier thread (task dab8766b).

Pattern: Meilisearch's async tasks (single writer, consecutive same-type tasks
batched, statuses enqueued/processing/succeeded/failed) and Qdrant's WAL
sequence numbers (each applied record carries its seq, so a crash-time replay
is idempotent).

Today /api/reindex enqueues a row here and returns immediately (202) instead
of running Indexer.reindex() inline; a single background Applier thread drains
the queue in seq order, so indexer.reindex()/reindex_paths() are NEVER called
from two threads at once — the concurrency guarantee moves from a per-request
non-blocking lock (085f1d69's reindex_lock, which only coalesced a SECOND
caller onto an already-running one) to "there is structurally only one caller,
ever". A request that arrives while its match is already 'processing' doesn't
get a bare rejection OR silently piggyback on a run that might finish before
its own trigger's changes are even on disk — it flags that job to run again
the moment the current pass finishes (`rerun_after`), so no request's intent
is ever dropped.

Scope note (task dab8766b): kind='paths' exists and coalesces exactly like
'scan_source'/'rebuild' (see enqueue()'s tests), but nothing in `trovex serve`
enqueues it yet — the server has no live filesystem watch today (Watcher/
`trovex watch` is a separate, standalone CLI foreground command with its own
Indexer + own debounce, untouched by this change). Wiring a live watch into
`trovex serve` is a materially separate feature; this module is the primitive
it would plug into.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time

from .indexer import Indexer
from .store import SqliteStore

log = logging.getLogger("trovex.index_jobs")

KINDS = ("scan_source", "paths", "rebuild", "rebuild_vec")

POLL_INTERVAL_SEC = 1.0


def enqueue(
    db: sqlite3.Connection,
    lock: threading.Lock,
    kind: str,
    *,
    source_key: str | None = None,
    paths: list[str] | None = None,
    full: bool = False,
) -> dict:
    """Enqueue a reindex job, coalescing with any existing job of the same
    (kind, source_key):
      - a match already 'queued' is merged into (paths unioned for kind=paths;
        scan_source/rebuild have no per-call payload to merge, so the existing
        row simply stands for this request too) — no new row;
      - a match already 'processing' is flagged rerun_after=1 (paths unioned
        into rerun_payload) instead of a new row, so it reruns the instant the
        current pass finishes;
      - otherwise a fresh 'queued' row is inserted at the tail (next seq).

    Returns {"job_id", "coalesced", "position"} — position is how many queued
    jobs sit ahead of this one (0 = next up or already running)."""
    if kind not in KINDS:
        raise ValueError(f"unknown index job kind: {kind!r}")
    payload: dict = {}
    if kind == "paths":
        payload["paths"] = sorted(set(paths or ()))
    if full:
        payload["full"] = True

    with lock:
        db.execute("BEGIN IMMEDIATE")
        try:
            queued = db.execute(
                "SELECT id, payload FROM index_jobs WHERE kind = ? AND source_key IS ? AND state = 'queued'",
                (kind, source_key),
            ).fetchone()
            if queued is not None:
                if kind == "paths":
                    existing = json.loads(queued["payload"]).get("paths", [])
                    merged = sorted(set(existing) | set(payload["paths"]))
                    db.execute(
                        "UPDATE index_jobs SET payload = ? WHERE id = ?",
                        (json.dumps({"paths": merged, **({"full": True} if full else {})}), queued["id"]),
                    )
                db.commit()
                return {"job_id": queued["id"], "coalesced": True, "position": _position(db, queued["id"])}

            processing = db.execute(
                "SELECT id, rerun_payload FROM index_jobs WHERE kind = ? AND source_key IS ? AND state = 'processing'",
                (kind, source_key),
            ).fetchone()
            if processing is not None:
                if kind == "paths":
                    existing = json.loads(processing["rerun_payload"] or "{}").get("paths", [])
                    rerun_payload = json.dumps(
                        {"paths": sorted(set(existing) | set(payload["paths"])), **({"full": True} if full else {})}
                    )
                else:
                    rerun_payload = json.dumps(payload)
                db.execute(
                    "UPDATE index_jobs SET rerun_after = 1, rerun_payload = ? WHERE id = ?",
                    (rerun_payload, processing["id"]),
                )
                db.commit()
                return {"job_id": processing["id"], "coalesced": True, "position": 0}

            seq = db.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM index_jobs").fetchone()["n"]
            cur = db.execute(
                """INSERT INTO index_jobs (kind, source_key, payload, seq, state, enqueued_at)
                   VALUES (?, ?, ?, ?, 'queued', ?)""",
                (kind, source_key, json.dumps(payload), seq, time.time()),
            )
            db.commit()
            job_id = cur.lastrowid
            return {"job_id": job_id, "coalesced": False, "position": _position(db, job_id)}
        except Exception:
            db.rollback()
            raise


def _position(db: sqlite3.Connection, job_id: int) -> int:
    row = db.execute(
        """SELECT COUNT(*) AS n FROM index_jobs
           WHERE state = 'queued' AND seq < (SELECT seq FROM index_jobs WHERE id = ?)""",
        (job_id,),
    ).fetchone()
    return row["n"]


def get_job(db: sqlite3.Connection, job_id: int) -> dict | None:
    row = db.execute("SELECT * FROM index_jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["payload"] = json.loads(d["payload"])
    if d.get("rerun_payload"):
        d["rerun_payload"] = json.loads(d["rerun_payload"])
    return d


class Applier:
    """The single writer for reindex work. One background thread drains
    index_jobs in seq order, one job at a time — Indexer.reindex() and
    Indexer.reindex_paths() are never called from two threads at once while
    this owns the queue. Reuses those methods unchanged (their own BEGIN
    IMMEDIATE / COMMIT batching and embed-before-BEGIN split, task cbb8e8fb,
    is exactly what makes a long job safe to run here without holding the
    write lock for the run's whole duration)."""

    def __init__(
        self, indexer: Indexer, store: SqliteStore | None = None, lock: threading.Lock | None = None
    ) -> None:
        self.indexer = indexer
        # Corpus hygiene (finding 085f1d69): sweep_bloat tombstones superseded
        # forks + collapses ephemeral-owner forks, idempotent, so running it
        # after every successful job is safe — matches /api/reindex's prior
        # inline behavior exactly. Optional only so a caller that only cares
        # about the queue (most tests) doesn't need a SqliteStore around.
        self.store = store
        self.db = indexer.db
        self.lock = lock or threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Recover any job a crash left 'processing', then start the loop."""
        self._recover_crashed_jobs()
        self._thread = threading.Thread(target=self._loop, name="index-jobs-applier", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    def notify(self) -> None:
        """Wake the loop immediately instead of waiting out the poll interval —
        called after enqueue() so a fresh job doesn't sit for up to
        POLL_INTERVAL_SEC before the applier notices it."""
        self._wake.set()

    def _recover_crashed_jobs(self) -> None:
        """A job left 'processing' at startup means the process died mid-run.
        Reset it to 'queued' — safe to just run again because both
        reindex()/reindex_paths() gate re-embed on content_hash/mtime, so a
        replay of already-applied work is a fast no-op, not a duplicate write."""
        with self.lock:
            n = self.db.execute(
                "UPDATE index_jobs SET state = 'queued', started_at = NULL WHERE state = 'processing'"
            ).rowcount
            self.db.commit()
        if n:
            log.warning("recovered %d index job(s) left 'processing' by a prior crash", n)

    def run_one(self) -> bool:
        """Claim and run exactly one queued job (synchronous — for tests and
        for draining the queue without the background thread). False if the
        queue was empty."""
        job = self._claim_next()
        if job is None:
            return False
        self._run_job(job)
        return True

    def _loop(self) -> None:
        while not self._stop.is_set():
            if not self.run_one():
                self._wake.wait(timeout=POLL_INTERVAL_SEC)
                self._wake.clear()

    def _claim_next(self) -> dict | None:
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                row = self.db.execute(
                    "SELECT * FROM index_jobs WHERE state = 'queued' ORDER BY seq LIMIT 1"
                ).fetchone()
                if row is None:
                    self.db.commit()
                    return None
                self.db.execute(
                    "UPDATE index_jobs SET state = 'processing', started_at = ? WHERE id = ?",
                    (time.time(), row["id"]),
                )
                self.db.commit()
                return dict(row)
            except Exception:
                self.db.rollback()
                raise

    def _run_job(self, job: dict) -> None:
        job_id = job["id"]
        payload = json.loads(job["payload"])
        while True:
            error = None
            try:
                self._execute(job["kind"], payload, job_id)
                if self.store is not None:
                    self.store.sweep_bloat()
            except Exception as e:  # noqa: BLE001 — one bad job must never kill the applier thread
                log.exception("index job %d (%s) failed", job_id, job["kind"])
                error = str(e)
            with self.lock:
                self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute(
                    "SELECT rerun_after, rerun_payload, payload FROM index_jobs WHERE id = ?", (job_id,)
                ).fetchone()
                if row["rerun_after"]:
                    payload = json.loads(row["rerun_payload"] or row["payload"])
                    self.db.execute(
                        """UPDATE index_jobs SET rerun_after = 0, rerun_payload = NULL, payload = ?,
                           started_at = ?, error = NULL WHERE id = ?""",
                        (json.dumps(payload), time.time(), job_id),
                    )
                    self.db.commit()
                    continue  # same row, run again — never a new job for "changed while running"
                self.db.execute(
                    "UPDATE index_jobs SET state = ?, finished_at = ?, error = ? WHERE id = ?",
                    ("failed" if error else "succeeded", time.time(), error, job_id),
                )
                self.db.commit()
                return

    def _execute(self, kind: str, payload: dict, job_id: int) -> dict:
        if kind == "paths":
            return self.indexer.reindex_paths(
                payload.get("paths", []), sources=self.indexer.settings.load_sources(), job_id=job_id
            )
        if kind == "rebuild_vec":
            # task 6851d755: an embed_model/dim change, swapped without the
            # blocking inline wipe _migrate_embed_dim used to do — see
            # db.rebuild_vec_shadow for the actual (staging + short-
            # transaction swap) mechanism. Routed through the SAME single-
            # writer applier as every other index job, so it can never run
            # concurrently with a reindex().
            from . import db as db_mod

            return db_mod.rebuild_vec_shadow(
                self.indexer.db, self.indexer.embedder, self.indexer.settings.resolved_embed_dim()
            )
        return self.indexer.reindex(full=bool(payload.get("full")), job_id=job_id)
