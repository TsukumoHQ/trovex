"""sync_source / gc_source: the connector sync worker (steal #5, design 61a37a82
6.3). Runs inside the single index_jobs applier, so it is the only writer.

sync_source resumes a connector from the last good cursor, replays the ids the
previous run failed on, applies records to the index in short batches, and only
then journals the new cursor in source_runs. gc_source diffs the connector's slim
listing against the index: over the safety ratio the losers go to pending_delete
(hidden from search, restorable) and are hard-deleted once the grace window ends."""

from __future__ import annotations

import dataclasses
import json
import time

from . import sources as sources_mod
from .connectors import build_connector
from .connectors.base import Cursor, RecordFailure, SlimRef, SourceRecord
from .db import delete_doc_cascade, vec_sync_meta
from .indexer import Indexer

SYNC_BATCH = 50  # records per reindex_paths call: one short write burst, never corpus-wide
GC_COMMIT_EVERY = 200
DAY = 86400


def _open(indexer: Indexer, source_id: str):
    row = sources_mod.get_source(indexer.db, source_id)
    if row is None:
        raise ValueError(f"unknown or disabled source {source_id!r}")
    source = sources_mod.to_source(row)
    return row, source, build_connector(row["kind"], source, indexer)


def _journal(indexer: Indexer, source_id: str, kind: str, started: float, **cols) -> None:
    cols.setdefault("cursor_json", None)
    names = ["source_id", "kind", "started", "ended", *cols]
    indexer.db.execute(
        f"INSERT INTO source_runs ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})",  # sql-safe: column names are this module's literals
        (source_id, kind, started, time.time(), *cols.values()),
    )
    indexer.db.commit()


def _apply_fs(indexer: Indexer, source, records: list[SourceRecord], job_id: int | None) -> dict:
    paths = [str(source.root / r.external_id) for r in records]
    return indexer.reindex_paths(paths, sources=[source], job_id=job_id)


SINKS = {"fs": _apply_fs}


def _last_good_sync(indexer: Indexer, source_id: str) -> tuple[Cursor | None, list[str]]:
    row = indexer.db.execute(
        """SELECT cursor_json, failures_json FROM source_runs
           WHERE source_id = ? AND kind = 'sync' AND error IS NULL ORDER BY id DESC LIMIT 1""",
        (source_id,),
    ).fetchone()
    if row is None:
        return None, []
    cursor = Cursor(**json.loads(row["cursor_json"])) if row["cursor_json"] else None
    retry = [f["external_id"] for f in json.loads(row["failures_json"]) if f.get("retryable") and f.get("external_id")]
    return cursor, retry


def run_sync_source(indexer: Indexer, source_id: str, job_id: int | None = None) -> dict:
    row, source, connector = _open(indexer, source_id)
    sink = SINKS[row["kind"]]
    started = time.time()
    cursor, retry_ids = _last_good_sync(indexer, source_id)
    totals = {"added": 0, "updated": 0, "unchanged": 0, "removed": 0}
    ms = {"scan": 0.0, "embed": 0.0, "write": 0.0}
    failures: dict[str, dict] = {}
    batch: dict[str, SourceRecord] = {}

    def flush() -> None:
        if not batch:
            return
        counts = sink(indexer, source, list(batch.values()), job_id)
        for k in totals:
            totals[k] += counts.get(k, 0)
        ms["embed"] += counts["phase_ms"]["embed"]
        ms["write"] += counts["phase_ms"]["write"]
        batch.clear()

    def take(item: SourceRecord | RecordFailure) -> None:
        if isinstance(item, RecordFailure):
            failures[item.external_id or repr(item.missed_range)] = dataclasses.asdict(item)
            return
        batch[item.external_id] = item
        if len(batch) >= SYNC_BATCH:
            flush()

    new_cursor = cursor
    try:
        for external_id in retry_ids:
            try:
                take(connector.fetch(SlimRef(external_id, "")))
            except Exception as e:  # noqa: BLE001 — a replay that fails again stays journaled
                take(RecordFailure(external_id, str(e), retryable=True))
        poll = connector.poll(cursor)
        while True:
            t0 = time.perf_counter()
            try:
                item = next(poll)
            except StopIteration as stop:
                new_cursor = stop.value
                ms["scan"] += (time.perf_counter() - t0) * 1000
                break
            ms["scan"] += (time.perf_counter() - t0) * 1000
            take(item)
        flush()
    except Exception as e:
        # The cursor stays where it was: what already applied is hash-gated, so the
        # next run repeats it as a no-op instead of skipping anything.
        _journal(indexer, source_id, "sync", started, error=str(e), failures_json=json.dumps(list(failures.values())))
        raise
    ok = totals["added"] + totals["updated"] + totals["unchanged"]
    _journal(
        indexer,
        source_id,
        "sync",
        started,
        cursor_json=json.dumps(dataclasses.asdict(new_cursor)) if new_cursor else None,
        added=totals["added"],
        updated=totals["updated"],
        removed=totals["removed"],
        ok=ok,
        failed=len(failures),
        failures_json=json.dumps(list(failures.values())),
        scan_ms=ms["scan"],
        embed_ms=ms["embed"],
        write_ms=ms["write"],
    )
    return {**totals, "ok": ok, "failed": len(failures)}


def _tombstone(indexer: Indexer, doc_id: int) -> None:
    """Snapshot a doc whose content lives IN the db (a remote connector's) before it
    is removed. A file-backed doc (content NULL) keeps its bytes on disk: no tombstone
    (same rule as SqliteStore._tombstone_locked)."""
    db = indexer.db
    d = db.execute(
        "SELECT external_id, path, title, content, kind, source_id FROM docs WHERE id = ?", (doc_id,)
    ).fetchone()
    if d is None or d["content"] is None:
        return
    tags = [r["tag"] for r in db.execute("SELECT tag FROM doc_tags WHERE doc_id = ?", (doc_id,))]
    db.execute(
        """INSERT INTO doc_tombstones (ext_id, title, content, kind, tags_json, source_id, deleted_ts)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (d["external_id"] or d["path"], d["title"], d["content"], d["kind"], json.dumps(tags), d["source_id"], time.time()),
    )


def _set_lifecycle(indexer: Indexer, doc_id: int, lifecycle: str) -> None:
    indexer.db.execute(
        "UPDATE docs SET lifecycle = ?, lifecycle_changed_at = ? WHERE id = ?", (lifecycle, time.time(), doc_id)
    )
    vec_sync_meta(indexer.db, doc_id)  # vec0 filters on its own lifecycle copy


def run_gc_source(indexer: Indexer, source_id: str, job_id: int | None = None) -> dict:
    row, _source, connector = _open(indexer, source_id)
    started = time.time()
    db = indexer.db
    # Indexed ids are read BEFORE the listing, so a doc indexed mid-listing can never
    # be classified as gone.
    known = {
        r["eid"]: (r["id"], r["lifecycle"], r["lifecycle_changed_at"])
        for r in db.execute(
            """SELECT id, COALESCE(external_id, path) AS eid, lifecycle, lifecycle_changed_at
               FROM docs WHERE source_id = ? AND workspace_id = 'default'""",
            (source_id,),
        )
    }
    listing = {ref.external_id for ref in connector.list_slim()}
    present = len(listing & known.keys())
    ratio = row["deletion_safety_ratio"]
    if known and present / len(known) < ratio:
        err = (
            f"listing returned {present}/{len(known)} known ids "
            f"({present / len(known):.2f}) below deletion_safety_ratio {ratio:.2f}; nothing removed"
        )
        _journal(indexer, source_id, "gc", started, error=err)
        return {"removed": 0, "error": err}

    grace_cut = time.time() - indexer.settings.hard_delete_grace_days * DAY
    removed: list[str] = []
    hard_deleted = 0
    for i, (eid, (doc_id, lifecycle, changed_at)) in enumerate(sorted(known.items()), 1):
        if eid in listing:
            if lifecycle == "pending_delete":
                _set_lifecycle(indexer, doc_id, "active")  # the record is back
        elif lifecycle != "pending_delete":
            _tombstone(indexer, doc_id)
            _set_lifecycle(indexer, doc_id, "pending_delete")
            removed.append(eid)
        elif 0 < changed_at < grace_cut:
            delete_doc_cascade(db, doc_id)
            hard_deleted += 1
            removed.append(eid)
        if i % GC_COMMIT_EVERY == 0:
            db.commit()
    db.commit()
    if hard_deleted:
        from .status import compute_status

        compute_status(db, indexer.settings)  # a removed canonical may promote its duplicates
    _journal(indexer, source_id, "gc", started, removed=len(removed), removed_ids=json.dumps(removed))
    return {"removed": len(removed), "removed_ids": removed}
