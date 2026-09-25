"""backup.py's pre-copy checkpoint must never stall a writer (task 2081581c).

Root cause: make_backup() ran `PRAGMA wal_checkpoint(TRUNCATE)` before the
online copy — TRUNCATE needs EXCLUSIVE access and busy-waits up to
busy_timeout (30s) against any reader holding an older WAL frame, which is
almost always true under the server's read traffic (prod 2026-08-31 task
7768dbe6 measured trovex_write/search stalling to exactly 30000ms from this
exact call). The backup path reintroduced that stall once a day. The
sqlite3 backup API (src.backup(dst)) copies a consistent snapshot including
WAL content regardless, so the pre-checkpoint is a pure optimization, never
required for correctness — PASSIVE gets it without ever blocking.

Hermetic: a deterministic bag-of-words embedder, no network.
"""

from __future__ import annotations

import hashlib
import inspect
import re
import sqlite3
import time

import numpy as np
import pytest
import sqlite_vec

from trovex import backup
from trovex.config import Settings
from trovex.query_cache import embed_query_blob
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


def test_backup_module_never_issues_truncate_checkpoint():
    """Source-guard: the actual PRAGMA call must never ask for TRUNCATE — it's
    the exact call that starves writers to the 30s busy_timeout. (Prose
    explaining that, in a comment, is fine and expected — this checks the
    real statement, not the word anywhere in the file.)"""
    source = inspect.getsource(backup.make_backup)
    assert "wal_checkpoint(TRUNCATE)" not in source
    assert "wal_checkpoint(PASSIVE)" in source


def test_make_backup_completes_fast_with_concurrent_read_transaction(settings):
    """A reader holding an open read transaction on the store — the case that
    made TRUNCATE busy-wait 30s — must not slow make_backup down at all."""
    store = SqliteStore(settings, embedder=BagEmbedder())
    ext_id = store.put("# Alpha\n\nauth database connection pool exhausted", kind="record")

    db_path = settings.data_dir / "trovex.db"
    reader = sqlite3.connect(str(db_path))
    reader.execute("BEGIN")
    reader.execute("SELECT * FROM docs")  # opens a read transaction, holds a WAL snapshot
    try:
        start = time.monotonic()
        dest = backup.make_backup(db_path, settings.data_dir)
        elapsed = time.monotonic() - start
    finally:
        reader.rollback()
        reader.close()

    assert elapsed < 5.0, f"make_backup took {elapsed:.2f}s with a concurrent reader"
    assert dest.exists()

    # The backup file is a real, independently-openable, queryable snapshot.
    conn = sqlite3.connect(str(dest))
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    try:
        row = conn.execute("SELECT id FROM docs WHERE ext_id = ?", (ext_id,)).fetchone()
        assert row is not None
        qblob = embed_query_blob(BagEmbedder(), "connection pool exhausted")
        hits = conn.execute(
            "SELECT rowid, distance FROM vec_docs WHERE embedding MATCH ? AND k = 5 ORDER BY distance",
            (qblob,),
        ).fetchall()
        assert any(h["rowid"] == row["id"] for h in hits), "backup file must answer a KNN query"
    finally:
        conn.close()


def test_prune_keeps_only_last_keep(settings):
    store = SqliteStore(settings, embedder=BagEmbedder())
    store.put("# Doc\n\nbody", kind="record")
    db_path = settings.data_dir / "trovex.db"

    for _ in range(3):
        backup.make_backup(db_path, settings.data_dir)
        time.sleep(1.01)  # filenames are second-resolution — force distinct names

    removed = backup.prune(settings.data_dir, keep=2)
    remaining = backup.list_backups(settings.data_dir)
    assert removed == 1
    assert len(remaining) == 2
