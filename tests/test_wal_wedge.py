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


def test_checkpoint_if_wal_large_forces_checkpoint(store, monkeypatch):
    calls = []
    real_db = store.db

    class _RecordingDB:
        def __getattr__(self, name):
            return getattr(real_db, name)

        def execute(self, sql, *a, **kw):
            calls.append(sql)
            if "wal_checkpoint" in sql:
                return None
            return real_db.execute(sql, *a, **kw)

    class _FakeStat:
        st_size = 11 * 1024 * 1024  # over WAL_WARN_BYTES

    db_path = store.settings.data_dir / "trovex.db"
    monkeypatch.setattr(type(db_path.with_name("x")), "stat", lambda self: _FakeStat())

    checkpoint_if_wal_large(_RecordingDB(), db_path)
    assert any("wal_checkpoint" in c for c in calls)


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
        "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status) VALUES (?, ?, ?, ?, ?, ?)",
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

    def _boom(db, settings):
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
