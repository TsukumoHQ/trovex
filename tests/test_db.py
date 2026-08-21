"""open_db — SQLite bootstrap, including the loadable-extension guard.

Some Python builds (pyenv / Homebrew on macOS) compile sqlite3 without
loadable-extension support, so `enable_load_extension` is missing and sqlite-vec
can't load. That must surface as an actionable RuntimeError on the first index,
not a raw AttributeError traceback (the classic cold-dev install wall).
"""

import sqlite3

import pytest
import sqlite_vec

import trovex.db as db


def _vec_conn(tmp_path, name="raw.db"):
    """A bare sqlite-vec-loaded connection, bypassing open_db's own migration
    sequence -- so a test can hand-craft a specific pre-migration schema."""
    conn = sqlite3.connect(str(tmp_path / name))
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


class _BoomOnExecute(sqlite3.Connection):
    """Connection subclass whose execute() can be armed to raise once a given
    SQL substring is about to run -- simulates a process killed partway
    through a migration's plain (non-executescript) statement sequence."""

    boom_on = None

    def execute(self, sql, *a, **k):
        if self.boom_on and self.boom_on in sql:
            raise RuntimeError("simulated kill mid-migration")
        return super().execute(sql, *a, **k)


def _boom_execute_conn(tmp_path, name="raw.db"):
    conn = sqlite3.connect(str(tmp_path / name), factory=_BoomOnExecute)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def test_open_db_reports_missing_extension_support(tmp_path, monkeypatch):
    class _FakeConn:
        def __init__(self):
            self.row_factory = None

        def execute(self, *a, **k):
            return self

        def enable_load_extension(self, *a):
            raise AttributeError("enable_load_extension")

    monkeypatch.setattr(db.sqlite3, "connect", lambda *a, **k: _FakeConn())

    with pytest.raises(RuntimeError) as exc:
        db.open_db(tmp_path / "store.db")

    msg = str(exc.value)
    assert "loadable-extension" in msg
    assert "uv tool install" in msg  # points to the fix


# --- task 743ad0d3: a process killed mid-migration used to leave vec_docs
# dropped but vec_chunks/chunks intact (or vice versa) -- the next boot's own
# early-return guard ("if not row: return") then treated that missing table
# as "nothing to migrate" and silently skipped forever, permanently wedging
# trovex_write on "no such table: vec_docs" (found live on the deployed
# store). Fix: wrap each migration's destructive sequence in one explicit
# transaction so an interruption always leaves the OLD tables untouched.


def test_partition_migration_on_fresh_store_is_noop(tmp_path):
    conn = db.open_db(tmp_path / "fresh.db", embed_dim=8)
    row = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'vec_docs'").fetchone()
    assert row is not None
    assert "partition key" in row["sql"]  # _init_schema already made it partitioned


def test_partition_migration_on_legacy_store_migrates_and_keeps_embeddings(tmp_path):
    conn = _vec_conn(tmp_path)
    conn.executescript(
        """
        CREATE TABLE docs (
            id INTEGER PRIMARY KEY, source_id TEXT, kind TEXT, lifecycle TEXT, status TEXT
        );
        CREATE VIRTUAL TABLE vec_docs USING vec0(embedding float[8] distance_metric=cosine);
        """
    )
    conn.execute(
        "INSERT INTO docs (id, source_id, kind, lifecycle, status) "
        "VALUES (1, 'trovex', 'doc', 'active', 'canonical')"
    )
    emb = sqlite_vec.serialize_float32([0.1] * 8)
    conn.execute("INSERT INTO vec_docs(rowid, embedding) VALUES (1, ?)", (emb,))
    conn.commit()

    db._migrate_partition_vec(conn, 8)

    row = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'vec_docs'").fetchone()
    assert row is not None and "partition key" in row["sql"]
    migrated = conn.execute(
        "SELECT source_id, embedding FROM vec_docs WHERE rowid = 1"
    ).fetchone()
    assert migrated["source_id"] == "trovex"
    assert migrated["embedding"] == emb  # embedding reused, not re-derived


def test_interrupted_partition_migration_is_atomic_and_self_heals(tmp_path):
    conn = _boom_execute_conn(tmp_path)
    conn.executescript(
        """
        CREATE TABLE docs (
            id INTEGER PRIMARY KEY, source_id TEXT, kind TEXT, lifecycle TEXT, status TEXT
        );
        CREATE VIRTUAL TABLE vec_docs USING vec0(embedding float[8] distance_metric=cosine);
        """
    )
    conn.execute(
        "INSERT INTO docs (id, source_id, kind, lifecycle, status) "
        "VALUES (1, 'trovex', 'doc', 'active', 'canonical')"
    )
    emb = sqlite_vec.serialize_float32([0.1] * 8)
    conn.execute("INSERT INTO vec_docs(rowid, embedding) VALUES (1, ?)", (emb,))
    conn.commit()

    # Simulate the process dying right as the partitioned CREATE runs, AFTER
    # the old vec_docs has already been dropped (this is the real repro: an
    # executescript()-based recreate implicitly COMMITs the pending DROPs
    # before either CREATE runs, so killing here used to leave both tables
    # gone-and-committed -- exactly the wedge this migration must prevent).
    conn.boom_on = "CREATE VIRTUAL TABLE vec_docs"
    with pytest.raises(RuntimeError):
        db._migrate_partition_vec(conn, 8)

    # The aborted attempt must not have left vec_docs half-dropped.
    row = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'vec_docs'").fetchone()
    assert row is not None, "vec_docs must survive an interrupted migration"
    assert "partition key" not in row["sql"]  # still the OLD (flat) schema
    assert conn.execute("SELECT embedding FROM vec_docs WHERE rowid = 1").fetchone()["embedding"] == emb

    # A clean retry on the next boot must now succeed and self-heal fully.
    conn.boom_on = None
    db._migrate_partition_vec(conn, 8)
    row = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'vec_docs'").fetchone()
    assert row is not None and "partition key" in row["sql"]
    assert conn.execute("SELECT source_id FROM vec_docs WHERE rowid = 1").fetchone()["source_id"] == "trovex"


def test_interrupted_embed_dim_migration_is_atomic_and_self_heals(tmp_path):
    conn = _boom_execute_conn(tmp_path)
    conn.executescript(
        """
        CREATE TABLE docs (id INTEGER PRIMARY KEY, content_hash TEXT NOT NULL DEFAULT 'h');
        CREATE VIRTUAL TABLE vec_docs USING vec0(embedding float[8] distance_metric=cosine);
        CREATE VIRTUAL TABLE vec_chunks USING vec0(embedding float[8] distance_metric=cosine);
        """
    )
    conn.execute("INSERT INTO docs (id, content_hash) VALUES (1, 'h')")
    conn.commit()

    # Kill the process right after vec_docs + vec_chunks are dropped, before
    # chunks_fts/chunks are touched or content_hash is cleared.
    conn.boom_on = "DROP TABLE IF EXISTS chunks_fts"
    with pytest.raises(RuntimeError):
        db._migrate_embed_dim(conn, 16)  # 16 != the stored dim (8) -> triggers the drop

    # Nothing must have taken effect: vec_docs survives at its OLD dim, and
    # the doc's content_hash was never cleared.
    row = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'vec_docs'").fetchone()
    assert row is not None and "float[8]" in row["sql"]
    assert conn.execute("SELECT content_hash FROM docs WHERE id = 1").fetchone()["content_hash"] == "h"

    # A clean retry must now succeed.
    conn.boom_on = None
    db._migrate_embed_dim(conn, 16)
    row = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'vec_docs'").fetchone()
    assert row is None  # dropped for real this time; _init_schema recreates it at the new dim
    assert conn.execute("SELECT content_hash FROM docs WHERE id = 1").fetchone()["content_hash"] == ""
