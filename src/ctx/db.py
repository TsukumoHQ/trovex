import sqlite3
from pathlib import Path

import sqlite_vec


def open_db(db_path: Path, embed_dim: int = 384) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    _init_schema(conn, embed_dim)
    return conn


def _init_schema(conn: sqlite3.Connection, embed_dim: int) -> None:
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS docs (
            id INTEGER PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            path TEXT NOT NULL,
            absolute_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            tokens_est INTEGER NOT NULL,
            mtime REAL NOT NULL,
            first_indexed REAL NOT NULL,
            last_indexed REAL NOT NULL,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'canonical',
            dup_of_id INTEGER REFERENCES docs(id),
            author_agent TEXT,
            UNIQUE(workspace_id, path)
        );
        CREATE INDEX IF NOT EXISTS idx_docs_status ON docs(workspace_id, status);
        CREATE INDEX IF NOT EXISTS idx_docs_mtime ON docs(workspace_id, mtime DESC);

        CREATE TABLE IF NOT EXISTS index_runs (
            id INTEGER PRIMARY KEY,
            ts REAL NOT NULL,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            duration_sec REAL,
            added INTEGER, updated INTEGER, unchanged INTEGER, removed INTEGER
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS vec_docs USING vec0(
            embedding float[{embed_dim}] distance_metric=cosine
        );
        """
    )
    conn.commit()
