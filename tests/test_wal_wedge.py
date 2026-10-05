"""Stranded-write-txn wedge fix (ticket eda6f60e).

Root cause: a Store write method (or an Indexer reindex pass) that raises
mid-transaction — a client disconnect, an embed failure, a genuine bug, an
IntegrityError from compute_status — left sqlite3's implicit transaction open.
The next write silently piled onto that same stranded transaction instead of
starting clean: writes accumulated but never flushed, and the WAL couldn't
checkpoint past it. Symptom: "database is locked" until the process restarts.

These tests prove: (1) ANY exception from a decorated Store write method rolls
back before propagating, and the connection is writable immediately after; (2)
the same holds for Indexer.reindex/reindex_paths; (3) the WAL watchdog forces
a checkpoint past a threshold; (4) compute_status's canonical_topic collision
(the concrete IntegrityError seen live) no longer raises — it resolves the
collision instead of crashing mid-UPDATE.

Hermetic: a deterministic bag-of-words embedder, no network.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3

import numpy as np
import pytest

from trovex.config import Settings
from trovex.db import checkpoint_if_wal_large
from trovex.indexer import Indexer
from trovex.status import compute_status
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
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


@pytest.fixture
def store(settings):
    return SqliteStore(settings, embedder=BagEmbedder())


def test_exception_mid_put_leaves_db_writable(store, monkeypatch):
    """A put() that fails partway through (e.g. the embedder blows up, or a
    client disconnects) must not strand the transaction — the exact AC5 repro."""
    real_embed = store.embedder.embed

    def _boom(texts):
        raise RuntimeError("embedder blew up mid-write")

    monkeypatch.setattr(store.embedder, "embed", _boom)
    with pytest.raises(RuntimeError):
        store.put("# will fail\n\nbody")

    assert store.db.in_transaction is False  # rolled back, not stranded

    monkeypatch.setattr(store.embedder, "embed", real_embed)
    ext_id = store.put("# recovers\n\nbody")  # must succeed on the same connection
    assert store.get(ext_id) is not None


def test_generalized_decorator_rolls_back_any_exception(store, monkeypatch):
    """The broadened decorator must catch ANY exception, not just SQLITE_BUSY —
    proving the fix generalizes to the 11 newly-decorated write methods, not
    just put()/delete()."""
    from trovex import retention

    def _boom(db):
        db.execute("UPDATE docs SET pinned = 1")  # opens a txn, never commits
        raise RuntimeError("boom mid-recompute")

    monkeypatch.setattr(retention, "recompute_importance", _boom)
    with pytest.raises(RuntimeError):
        store.recompute_importance()

    assert store.db.in_transaction is False

    ext_id = store.put("# after boom\n\nstill writable")
    assert store.get(ext_id) is not None


def test_locked_retry_still_works(store, monkeypatch):
    """Regression: broadening the except clauses must not break the original
    SQLITE_BUSY retry-then-succeed behavior.

    sqlite3.Connection is a C type — its methods can't be monkeypatched in
    place (AttributeError: read-only), so wrap the real connection instead and
    swap the whole `db` attribute, same trick the decorator's own unit tests
    (test_store.py) use with a fake target."""
    calls = {"n": 0}
    real_db = store.db

    class _FlakyDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, sql, *a, **kw):
            if sql.startswith("UPDATE docs SET pinned"):
                calls["n"] += 1
                if calls["n"] < 2:
                    raise sqlite3.OperationalError("database is locked")
            return real_db.execute(sql, *a, **kw)

    ext_id = store.put("# pin me\n\nbody")
    monkeypatch.setattr(store, "db", _FlakyDB())
    monkeypatch.setattr("trovex.store.time.sleep", lambda _s: None)

    assert store.set_pinned(ext_id, True) is True
    assert calls["n"] == 2  # failed once, retried, succeeded


class _FakeCheckpointCursor:
    """wal_checkpoint's real result row is (busy, log_pages, checkpointed_pages).
    Fully-flushed: busy=0 and checkpointed_pages == log_pages, the condition the
    periodic tick TRUNCATEs on (b02389c2 / audit Q7)."""

    def fetchone(self):
        return (0, 323, 323)


def test_checkpoint_if_wal_large_forces_checkpoint(store, monkeypatch):
    calls = []
    real_db = store.db

    class _RecordingDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, sql, *a, **kw):
            calls.append(sql)
            if "wal_checkpoint" in sql:
                return _FakeCheckpointCursor()
            return real_db.execute(sql, *a, **kw)

    class _FakeStat:
        st_size = 11 * 1024 * 1024  # over WAL_WARN_BYTES

    db_path = store.settings.data_dir / "trovex.db"
    monkeypatch.setattr(type(db_path.with_name("x")), "stat", lambda self: _FakeStat())

    checkpoint_if_wal_large(_RecordingDB(), db_path)
    assert any("wal_checkpoint" in c for c in calls)


def test_checkpoint_if_wal_large_uses_passive_not_truncate(store, monkeypatch):
    """TRUNCATE needs exclusive access and busy-waits up to busy_timeout on the
    shared write connection when a reader is active — under concurrent read
    traffic that reliably wedged writes/searches to the 30s busy_timeout (prod
    2026-08-31, task 7768dbe6). PASSIVE never blocks; pin it so it can't regress."""
    calls = []
    real_db = store.db

    class _RecordingDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, sql, *a, **kw):
            calls.append(sql)
            if "wal_checkpoint" in sql:
                return _FakeCheckpointCursor()
            return real_db.execute(sql, *a, **kw)

    class _FakeStat:
        st_size = 11 * 1024 * 1024  # over WAL_WARN_BYTES

    db_path = store.settings.data_dir / "trovex.db"
    monkeypatch.setattr(type(db_path.with_name("x")), "stat", lambda self: _FakeStat())

    checkpoint_if_wal_large(_RecordingDB(), db_path)
    checkpoint_calls = [c for c in calls if "wal_checkpoint" in c]
    assert checkpoint_calls == ["PRAGMA wal_checkpoint(PASSIVE)"]


def test_open_db_sets_wal_autocheckpoint_bound(store):
    """task 20afcaf7 AC2: wal_autocheckpoint is set at connection open to the
    configured page count, not left at whatever the linked sqlite build
    defaults to — so routine writes checkpoint themselves long before WAL_WARN_BYTES,
    and the 10MB forced path becomes a rare last resort instead of the normal case."""
    from trovex.db import WAL_AUTOCHECKPOINT_PAGES

    value = store.db.execute("PRAGMA wal_autocheckpoint").fetchone()[0]
    assert value == WAL_AUTOCHECKPOINT_PAGES


def test_write_burst_never_grows_wal_past_forced_threshold(store):
    """task 20afcaf7 AC2: with wal_autocheckpoint bound at connection open,
    sqlite auto-checkpoints itself every WAL_AUTOCHECKPOINT_PAGES pages — a
    burst of writes must never let the real WAL file grow past WAL_WARN_BYTES
    (the forced-checkpoint threshold), because sqlite is checkpointing on its
    own the whole time. Real WAL file, not a mock: this is a regression lock
    on the PRAGMA actually taking effect, not just being sent."""
    from trovex.db import WAL_WARN_BYTES

    wal_path = store.settings.data_dir / "trovex.db-wal"
    body = "word " * 2000  # a few KB of content per doc, embedding is hermetic
    for i in range(300):
        store.put(f"# Burst {i}\n\n{body}", kind="note", tags=[f"burst-{i}"])
        if wal_path.exists():
            assert wal_path.stat().st_size <= WAL_WARN_BYTES, (
                f"WAL grew past the forced threshold at doc {i} despite "
                "wal_autocheckpoint — the bound isn't taking effect"
            )


def test_checkpoint_journals_mode_pages_and_duration(store, monkeypatch, caplog):
    """task 20afcaf7 AC4: every forced checkpoint logs one line carrying mode,
    pages, and duration — so a slow prod checkpoint (the field incident: ~60s
    for 68MB) shows up in serve.log instead of only the vague pre/post-size
    warning that was there before."""
    import logging

    class _FakeStat:
        st_size = 11 * 1024 * 1024  # over WAL_WARN_BYTES

    db_path = store.settings.data_dir / "trovex.db"
    monkeypatch.setattr(type(db_path.with_name("x")), "stat", lambda self: _FakeStat())

    with caplog.at_level(logging.WARNING, logger="trovex.db"):
        checkpoint_if_wal_large(store.db, db_path)

    journal_lines = [r.message for r in caplog.records if "mode=PASSIVE" in r.message]
    assert len(journal_lines) == 1
    line = journal_lines[0]
    assert "log_pages=" in line
    assert "checkpointed_pages=" in line
    assert "duration_ms=" in line


def test_checkpoint_backoff_after_deferred_skips_retries(store, monkeypatch, caplog):
    """task 20afcaf7 r4: a deferred (SQLITE_LOCKED) checkpoint must not be
    re-forced on every subsequent write while the WAL stays large — live
    repro 2026-09-26 23:15-23:17Z showed the same 68MB WAL re-forcing and
    re-deferring roughly every 45s, each attempt re-hitting the lock. One
    deferred attempt must back off; a call inside the backoff window must
    not touch wal_checkpoint (or log a second 'deferred' line) at all —
    once the backoff elapses, the next call retries normally."""
    import logging

    from trovex.db import _CHECKPOINT_BACKOFF_BASE_SECS, _checkpoint_backoff

    calls = []
    real_db = store.db

    class _LockedDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, sql, *a, **kw):
            if "wal_checkpoint" in sql:
                calls.append(sql)
                raise sqlite3.OperationalError("database table locked")
            return real_db.execute(sql, *a, **kw)

    class _FakeStat:
        st_size = 11 * 1024 * 1024  # over WAL_WARN_BYTES

    db_path = store.settings.data_dir / "trovex.db"
    monkeypatch.setattr(type(db_path.with_name("x")), "stat", lambda self: _FakeStat())
    _checkpoint_backoff.pop(str(db_path), None)  # isolate from any other test's state

    fake_now = [1000.0]
    monkeypatch.setattr("trovex.db.time.monotonic", lambda: fake_now[0])

    with caplog.at_level(logging.WARNING, logger="trovex.db"):
        checkpoint_if_wal_large(_LockedDB(), db_path)  # attempts, deferred, backs off
        checkpoint_if_wal_large(_LockedDB(), db_path)  # still backed off: must not retry
        fake_now[0] += _CHECKPOINT_BACKOFF_BASE_SECS + 1  # backoff window elapses
        checkpoint_if_wal_large(_LockedDB(), db_path)  # backoff cleared: retries, defers again

    assert len(calls) == 2, "the backed-off call must never touch wal_checkpoint"
    deferred_lines = [r.message for r in caplog.records if "wal checkpoint deferred" in r.message]
    assert len(deferred_lines) == 2


def test_checkpoint_backoff_after_success_still_skips_retries(store, monkeypatch):
    """task 20afcaf7 r4 root cause (measured 2026-09-26 23:23Z): PASSIVE never
    shrinks the WAL FILE (only TRUNCATE does), so a file whose high-water mark
    once crossed WAL_WARN_BYTES stays there forever from stat()'s point of
    view — a size-only gate would re-force a checkpoint on every single write
    FOREVER even when each one succeeds cleanly (busy=0, no exception). This
    must back off exactly like the deferred case, not just the error case."""
    calls = []
    real_db = store.db

    class _RecordingDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, sql, *a, **kw):
            if "wal_checkpoint" in sql:
                calls.append(sql)
                return _FakeCheckpointCursor()  # busy=0 — a clean success
            return real_db.execute(sql, *a, **kw)

    class _FakeStat:
        st_size = 11 * 1024 * 1024  # over WAL_WARN_BYTES — and stays there: PASSIVE never shrinks it

    db_path = store.settings.data_dir / "trovex.db"
    monkeypatch.setattr(type(db_path.with_name("x")), "stat", lambda self: _FakeStat())
    from trovex.db import _checkpoint_backoff

    _checkpoint_backoff.pop(str(db_path), None)  # isolate from any other test's state

    db = _RecordingDB()
    for _ in range(10):  # simulate 10 writes in a row, same permanently-oversized file
        checkpoint_if_wal_large(db, db_path)

    assert len(calls) == 1, "a successful-but-still-oversized checkpoint must not re-force every write"


def test_periodic_checkpoint_tick_always_runs_passive_never_gated_on_size(store):
    """task 20afcaf7 r4: the periodic timer's tick is unconditional — no file
    size check at all (that's the per-write backstop's job) — so it always
    attempts PASSIVE regardless of how big the WAL file has gotten."""
    from trovex.db import periodic_checkpoint_tick

    db_path = store.settings.data_dir / "trovex.db"
    result = periodic_checkpoint_tick(store.db, db_path)
    assert result is not None
    busy, _log_pages, _checkpointed_pages = result
    assert busy in (0, 1)


def test_periodic_checkpoint_tick_truncates_when_fully_checkpointed(store, monkeypatch):
    """b02389c2 / audit Q7: TRUNCATE (the only mode that shrinks the WAL FILE)
    runs exactly when the PASSIVE pass moved EVERY frame with no contention
    (busy == 0 and checkpointed_pages == log_pages) — the whole WAL is now in
    the db, nothing older is still pinned. The old gate `log_pages == 0` almost
    never held (PRAGMA reports log_pages as the total frame count, so a fully
    checkpointed WAL still reads log_pages == checkpointed_pages > 0), so
    TRUNCATE never fired and the file grew unbounded."""
    from trovex.db import periodic_checkpoint_tick

    calls = []
    real_db = store.db

    class _RecordingDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, sql, *a, **kw):
            calls.append(sql)
            if sql == "PRAGMA wal_checkpoint(PASSIVE)":

                class _Row:
                    def fetchone(self):
                        return (0, 323, 323)  # busy=0, fully flushed (checkpointed == log)

                return _Row()
            return real_db.execute(sql, *a, **kw)

    db_path = store.settings.data_dir / "trovex.db"
    periodic_checkpoint_tick(_RecordingDB(), db_path)
    assert calls == ["PRAGMA wal_checkpoint(PASSIVE)", "PRAGMA wal_checkpoint(TRUNCATE)"]


def test_periodic_checkpoint_tick_skips_truncate_when_frames_pending(store):
    """The common case: real pending WAL content (log_pages > 0) — TRUNCATE
    must not even be attempted, only the always-safe PASSIVE."""
    from trovex.db import periodic_checkpoint_tick

    calls = []
    real_db = store.db

    class _RecordingDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, sql, *a, **kw):
            calls.append(sql)
            if sql == "PRAGMA wal_checkpoint(PASSIVE)":

                class _Row:
                    def fetchone(self):
                        return (0, 323, 191)  # checkpointed (191) < log (323) — frames still pending

                return _Row()
            return real_db.execute(sql, *a, **kw)

    db_path = store.settings.data_dir / "trovex.db"
    periodic_checkpoint_tick(_RecordingDB(), db_path)
    assert calls == ["PRAGMA wal_checkpoint(PASSIVE)"]


def test_periodic_checkpoint_tick_deferred_returns_none_never_raises(store, monkeypatch):
    """Same best-effort contract as checkpoint_if_wal_large: a locked PASSIVE
    must never raise (this runs unattended in a background timer, off_loop'd,
    with no caller to report a failure to)."""
    from trovex.db import periodic_checkpoint_tick

    class _LockedDB:
        def execute(self, sql, *a, **kw):
            raise sqlite3.OperationalError("database table locked")

    db_path = store.settings.data_dir / "trovex.db"
    assert periodic_checkpoint_tick(_LockedDB(), db_path) is None  # must not raise


def test_periodic_tick_truncate_shrink_resets_write_path_backoff(store, monkeypatch):
    """cto-tsukumo r4 condition 1: once the timer's TRUNCATE actually shrinks
    the file, checkpoint_if_wal_large's backoff for this db_path must clear —
    the condition that started the backoff (a permanently-oversized file) is
    gone, so the write-path backstop goes back to normal instead of staying
    capped at its last backoff for up to 10 minutes after a real cleanup."""
    import time

    from trovex.db import _checkpoint_backoff, periodic_checkpoint_tick

    db_path = store.settings.data_dir / "trovex.db"
    key = str(db_path)
    _checkpoint_backoff[key] = (time.monotonic() + 600.0, 600.0)  # simulate a capped-out backoff

    sizes = iter([11 * 1024 * 1024, 0])  # size_before (oversized), size_after (shrunk to 0)
    monkeypatch.setattr(type(db_path.with_name("x")), "stat", lambda self: type("S", (), {"st_size": next(sizes)})())
    monkeypatch.setattr(type(db_path.with_name("x")), "exists", lambda self: True)

    real_db = store.db

    class _RecordingDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, sql, *a, **kw):
            if sql == "PRAGMA wal_checkpoint(PASSIVE)":
                return _FakeCheckpointCursor()  # busy=0, fully flushed (checkpointed == log) -> TRUNCATE fires
            if sql == "PRAGMA wal_checkpoint(TRUNCATE)":
                return _FakeCheckpointCursor()
            return real_db.execute(sql, *a, **kw)

    periodic_checkpoint_tick(_RecordingDB(), db_path)
    assert key not in _checkpoint_backoff, "a real shrink must clear the write-path backoff"


def test_periodic_tick_truncate_no_shrink_keeps_write_path_backoff(store, monkeypatch):
    """The mirror case: TRUNCATE ran but the file didn't actually shrink (e.g.
    another reader grabbed a snapshot in between) — the backoff must stay in
    place, since the oversized-file condition it exists for is still true."""
    import time

    from trovex.db import _checkpoint_backoff, periodic_checkpoint_tick

    db_path = store.settings.data_dir / "trovex.db"
    key = str(db_path)
    _checkpoint_backoff[key] = (time.monotonic() + 600.0, 600.0)

    sizes = iter([11 * 1024 * 1024, 11 * 1024 * 1024])  # unchanged
    monkeypatch.setattr(type(db_path.with_name("x")), "stat", lambda self: type("S", (), {"st_size": next(sizes)})())
    monkeypatch.setattr(type(db_path.with_name("x")), "exists", lambda self: True)

    real_db = store.db

    class _RecordingDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, sql, *a, **kw):
            if sql in ("PRAGMA wal_checkpoint(PASSIVE)", "PRAGMA wal_checkpoint(TRUNCATE)"):
                return _FakeCheckpointCursor()
            return real_db.execute(sql, *a, **kw)

    periodic_checkpoint_tick(_RecordingDB(), db_path)
    assert key in _checkpoint_backoff, "backoff must stay while the file is still oversized"


def test_checkpoint_backoff_logs_once_per_window_not_per_request(store, monkeypatch, caplog):
    """cto-tsukumo r4 condition 2: the 'forcing checkpoint' WARNING logs once
    per backoff window (the first attempt, then again only on the next
    escalation) — never once per request, or the incident's own log spam
    (the symptom that made it visible) never actually clears."""
    import logging

    from trovex.db import _CHECKPOINT_BACKOFF_BASE_SECS, _checkpoint_backoff

    real_db = store.db

    class _RecordingDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, sql, *a, **kw):
            if "wal_checkpoint" in sql:
                return _FakeCheckpointCursor()
            return real_db.execute(sql, *a, **kw)

    class _FakeStat:
        st_size = 11 * 1024 * 1024

    db_path = store.settings.data_dir / "trovex.db"
    monkeypatch.setattr(type(db_path.with_name("x")), "stat", lambda self: _FakeStat())
    _checkpoint_backoff.pop(str(db_path), None)

    fake_now = [1000.0]
    monkeypatch.setattr("trovex.db.time.monotonic", lambda: fake_now[0])

    db = _RecordingDB()
    with caplog.at_level(logging.WARNING, logger="trovex.db"):
        for _ in range(5):  # 5 "requests" all inside the same backoff window
            checkpoint_if_wal_large(db, db_path)
        fake_now[0] += _CHECKPOINT_BACKOFF_BASE_SECS + 1  # escalate to the next window
        for _ in range(5):  # 5 more, all inside the NEW window
            checkpoint_if_wal_large(db, db_path)

    forcing_lines = [r.message for r in caplog.records if "forcing checkpoint" in r.message]
    assert len(forcing_lines) == 2, "one log line per backoff window, not one per request"


def test_checkpoint_if_wal_large_noop_below_threshold(store):
    # No .db-wal file exists at all under a fresh tmp_path in some environments,
    # or it's tiny — either way this must not raise or touch the connection.
    db_path = store.settings.data_dir / "trovex.db"
    checkpoint_if_wal_large(store.db, db_path)  # must not raise


def test_checkpoint_if_wal_large_never_propagates(store, monkeypatch):
    """This runs AFTER the caller's write already committed (store._retry_on_locked
    calls it post-fn(), same for indexer._rollback_on_error) — any exception from
    this best-effort watchdog (a stat() PermissionError, a checkpoint-time sqlite
    error) must never propagate, or a successful/committed write gets reported to
    the caller as a failure."""
    db_path = store.settings.data_dir / "trovex.db"

    def _boom(self):
        raise PermissionError("no access")

    monkeypatch.setattr(type(db_path.with_name("x")), "stat", _boom)
    checkpoint_if_wal_large(store.db, db_path)  # must not raise despite the PermissionError


def test_compute_status_resolves_canonical_topic_collision(store, settings):
    """Two non-superseded docs sharing a canonical_topic (e.g. one left over as
    'plan'/'stale' from before compute_status ran) used to crash the blanket
    UPDATE with IntegrityError on idx_docs_canonical_topic the moment the
    second row transitioned to 'canonical' — stranding the reindex transaction.
    compute_status must resolve the collision instead of raising."""
    a = store.put("# Topic\n\nfirst", kind="record")
    b = store.put("# Topic Two\n\nsecond", kind="record")
    # Force both into the SAME canonical_topic + non-superseded status, bypassing
    # the application-level SSOT guard (store.put) — this is exactly the shape
    # compute_status must defend against, regardless of how it arises upstream.
    store.db.execute(
        "UPDATE docs SET canonical_topic = 'shared-topic', status = 'canonical' WHERE ext_id = ?", (a,)
    )
    store.db.execute(
        "UPDATE docs SET canonical_topic = 'shared-topic', status = 'plan' WHERE ext_id = ?", (b,)
    )
    store.db.commit()

    compute_status(store.db, settings)  # must not raise sqlite3.IntegrityError

    statuses = {
        row["ext_id"]: row["status"]
        for row in store.db.execute("SELECT ext_id, status FROM docs WHERE ext_id IN (?, ?)", (a, b))
    }
    # Exactly one winner (the previously-canonical row) stays canonical; the
    # loser is demoted to 'duplicate', not left to collide.
    assert statuses[a] == "canonical"
    assert statuses[b] == "duplicate"


def test_tag_scoped_search_survives_over_4096_chunk_partition(store):
    """AC1 regression lock-in: sqlite-vec hard-caps a single KNN `k` at 4096
    (VEC0_K_CEILING). search_chunks's tag-scoped path used k=doc_count before
    the P2a partition refactor (commit c9c5320) — a >4096-chunk partition
    raised `sqlite3.OperationalError: k value ... too large`, stranding the
    write txn mid-request (the live incident). store.py:999 now hardcodes
    k=4096 for the tag-scoped branch (no doc-count-dependent widen), so this
    must stay unreachable regardless of how many chunks share the partition."""
    ext_id = store.put("# Bulk\n\nauth token refresh rotation policy", kind="note", tags=["bulk"])
    doc = store.db.execute("SELECT id, source_id, kind, lifecycle, status FROM docs WHERE ext_id = ?", (ext_id,)).fetchone()

    real_embed = next(store.embedder.embed(["auth token refresh rotation policy"]))
    import sqlite_vec

    blob = sqlite_vec.serialize_float32(real_embed.tolist())

    n = 4200  # over VEC0_MAX_K (4096) — proves the partition, not the ceiling, bounds k
    store.db.executemany(
        "INSERT INTO chunks (id, doc_id, chunk_index, heading_path, content, tokens_est, content_hash) "
        "VALUES (?, ?, ?, '', 'auth token refresh rotation policy', 5, '')",
        [(1000 + i, doc["id"], i) for i in range(n)],
    )
    store.db.executemany(
        "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
        "VALUES (?, ?, ?, ?, ?, ?, 'test')",
        [
            (1000 + i, doc["source_id"], blob, doc["kind"], doc["lifecycle"], doc["status"])
            for i in range(n)
        ],
    )
    store.db.commit()

    hits = store.search_chunks("auth token refresh rotation policy", limit=5, tags=["bulk"])  # must not raise
    assert hits, "expected hits from the over-capacity partition"


def test_indexer_reindex_rolls_back_on_compute_status_failure(settings, tmp_path, monkeypatch):
    """A reindex that crashes inside compute_status (the live IntegrityError
    incident) must roll back its uncommitted docs/vec writes instead of
    stranding them — proving the fix covers the Indexer's own connection, not
    just SqliteStore's."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.md").write_text("# Alpha\n\nalpha body", encoding="utf-8")

    from trovex.config import Source

    indexer = Indexer(settings, embedder=BagEmbedder())

    def _boom(db, settings, touched_doc_ids=None):
        raise sqlite3.IntegrityError("UNIQUE constraint failed: docs.workspace_id, docs.canonical_topic")

    # reindex() imports compute_status LOCALLY inside the function body, so the
    # name is resolved from trovex.status at call time — patching the module
    # attribute there is what a local `from .status import compute_status`
    # actually picks up.
    import trovex.status as status_mod

    monkeypatch.setattr(status_mod, "compute_status", _boom)

    with pytest.raises(sqlite3.IntegrityError):
        indexer.reindex(sources=[Source(id="code", label="repo", root=root)])

    assert indexer.db.in_transaction is False  # rolled back, not stranded

    # The connection must still be usable for a subsequent write.
    indexer.db.execute("INSERT INTO index_runs (ts, duration_sec, added, updated, unchanged, removed) "
                        "VALUES (0, 0, 0, 0, 0, 0)")
    indexer.db.commit()


# ── b02389c2 / audit Q7: WAL TRUNCATE gate ───────────────────────────────────


def test_periodic_checkpoint_tick_truncates_wal_after_full_checkpoint(store):
    """AC5: once a PASSIVE pass has moved every frame into the db, the periodic
    tick must TRUNCATE so the WAL file returns under its cap. The old gate
    `log_pages == 0` never held — PRAGMA reports log_pages as the WAL's total
    frame count, so after a full checkpoint it equals checkpointed_pages and
    TRUNCATE never fired, leaving the WAL (140 MB in prod) to grow forever."""
    from trovex.db import periodic_checkpoint_tick

    db_path = store.settings.data_dir / "trovex.db"
    wal_path = db_path.with_name(db_path.name + "-wal")

    # Real committed writes grow the WAL; a handful of small docs stays well
    # under the forced/auto checkpoint thresholds, so frames pile up unflushed.
    for i in range(50):
        store.put(f"# doc {i}\n\n" + ("lorem ipsum dolor sit amet " * 40), tags=[f"owner/n{i}"])
    size_before = wal_path.stat().st_size
    assert size_before > 0, "precondition: the WAL should hold committed frames"

    row = periodic_checkpoint_tick(store.db, db_path)
    assert row is not None  # (busy, log_pages, checkpointed_pages)

    size_after = wal_path.stat().st_size
    # Pre-fix (log_pages == 0 gate): TRUNCATE never fires, PASSIVE leaves the
    # file at its high-water mark -> size unchanged. Post-fix: TRUNCATE shrinks.
    assert size_after < size_before, (
        f"WAL did not shrink: {size_before} -> {size_after} (TRUNCATE never fired)"
    )


# ── b02389c2 AC3: per-thread read connection (audit #4) ──────────────────────


def test_threadlocal_read_conn_is_per_thread(store):
    """Each thread gets its OWN read connection (so recall-pool workers don't
    serialize on one connection's mutex), and every connection sees the
    committed store (task b02389c2 AC3)."""
    import threading as _threading

    from trovex.db import ThreadLocalReadConn

    store.put("# doc\n\nbody one two three", tags=["owner/x"])
    proxy = ThreadLocalReadConn(store.settings.data_dir / "trovex.db")
    assert proxy.execute("SELECT COUNT(*) FROM docs").fetchone()[0] >= 1

    conn_ids: dict[int, int] = {}

    def worker(tid: int) -> None:
        conn_ids[tid] = id(proxy._conn())
        assert proxy.execute("SELECT COUNT(*) FROM docs").fetchone()[0] >= 1

    threads = [_threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(conn_ids.values())) == 3  # three distinct per-thread connections
