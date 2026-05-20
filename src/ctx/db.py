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

        CREATE TABLE IF NOT EXISTS mcp_queries (
            id INTEGER PRIMARY KEY,
            ts REAL NOT NULL,
            user TEXT NOT NULL DEFAULT 'unknown',
            query TEXT NOT NULL,
            n_results INTEGER NOT NULL DEFAULT 0,
            summary INTEGER NOT NULL DEFAULT 0,
            response_tokens_est INTEGER NOT NULL DEFAULT 0,
            elapsed_ms INTEGER NOT NULL DEFAULT 0,
            would_have_read_tokens INTEGER NOT NULL DEFAULT 0,
            top_result_tokens INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_mcp_queries_ts ON mcp_queries(ts DESC);
        CREATE INDEX IF NOT EXISTS idx_mcp_queries_user ON mcp_queries(user, ts DESC);

        CREATE TABLE IF NOT EXISTS mcp_query_results (
            query_id INTEGER NOT NULL REFERENCES mcp_queries(id) ON DELETE CASCADE,
            rank INTEGER NOT NULL,
            path TEXT NOT NULL,
            status TEXT,
            tokens_est INTEGER,
            score REAL,
            PRIMARY KEY (query_id, rank)
        );
        CREATE INDEX IF NOT EXISTS idx_mqr_path ON mcp_query_results(path);
        CREATE INDEX IF NOT EXISTS idx_mqr_query ON mcp_query_results(query_id);

        CREATE VIRTUAL TABLE IF NOT EXISTS vec_docs USING vec0(
            embedding float[{embed_dim}] distance_metric=cosine
        );
        """
    )
    conn.commit()
