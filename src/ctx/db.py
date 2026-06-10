import sqlite3
from pathlib import Path

import sqlite_vec


def open_db(db_path: Path, embed_dim: int = 384) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL: concurrent readers + one writer (the reindex runs in a *separate*
    # process from the server, so the in-process write lock isn't enough).
    # busy_timeout: wait for the lock instead of failing with "database is
    # locked" — fixes ctx_write / ctx_delete racing the reindex.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    # Migration must run BEFORE _init_schema: CREATE TABLE IF NOT EXISTS won't
    # add columns to a pre-existing legacy docs table; we need to recreate it.
    _migrate_to_multi_source(conn)
    _migrate_embed_dim(conn, embed_dim)
    _migrate_add_ctx_store_columns(conn)
    _init_schema(conn, embed_dim)
    return conn


def _migrate_embed_dim(conn: sqlite3.Connection, embed_dim: int) -> None:
    """If vec_docs exists with a different dim than the configured embedder,
    drop it. The indexer will recreate it on next run and re-embed all docs.

    Detects existing dim by querying sqlite_master DDL — vec0 table SQL stores
    the dim inline like "embedding float[3072]".
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='vec_docs'"
    ).fetchone()
    if not row:
        return
    ddl = row["sql"] or ""
    # Parse the float[N] dim out of the DDL.
    import re
    m = re.search(r"float\[(\d+)\]", ddl)
    if not m:
        return
    current_dim = int(m.group(1))
    if current_dim == embed_dim:
        return
    # Dim mismatch — wipe the vec table and clear any docs that referenced it
    # (forces a full reindex). docs.content_hash will be 0 → all rows re-embed.
    conn.execute("DROP TABLE IF EXISTS vec_docs")
    conn.execute("UPDATE docs SET content_hash = ''")
    conn.commit()


def _migrate_to_multi_source(conn: sqlite3.Connection) -> None:
    """Bring an existing docs table forward to the source_id schema.

    Idempotent — checks current state before acting.
    """
    # Skip if docs table doesn't exist yet — _init_schema will create it fresh.
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='docs'"
    ).fetchone()
    if not exists:
        return

    cols = {r[1] for r in conn.execute("PRAGMA table_info(docs)")}
    if "source_id" in cols:
        return  # already migrated

    conn.executescript(
        """
        CREATE TABLE docs_new (
            id INTEGER PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            source_id TEXT NOT NULL DEFAULT 'code',
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
            dup_of_id INTEGER REFERENCES docs_new(id),
            author_agent TEXT,
            UNIQUE(workspace_id, source_id, path)
        );
        INSERT INTO docs_new
            (id, workspace_id, source_id, path, absolute_path, content_hash,
             size_bytes, tokens_est, mtime, first_indexed, last_indexed,
             title, status, dup_of_id, author_agent)
        SELECT id, workspace_id, 'code', path, absolute_path, content_hash,
               size_bytes, tokens_est, mtime, first_indexed, last_indexed,
               title, status, dup_of_id, author_agent
        FROM docs;
        DROP TABLE docs;
        ALTER TABLE docs_new RENAME TO docs;
        CREATE INDEX IF NOT EXISTS idx_docs_status ON docs(workspace_id, status);
        CREATE INDEX IF NOT EXISTS idx_docs_mtime ON docs(workspace_id, mtime DESC);
        CREATE INDEX IF NOT EXISTS idx_docs_source ON docs(workspace_id, source_id);
        """
    )
    conn.commit()


def _migrate_add_ctx_store_columns(conn: sqlite3.Connection) -> None:
    """Add the ctx-owned-store columns to an existing docs table.

    Additive (ALTER ADD COLUMN), unlike the multi-source migration — these
    columns are nullable and default NULL, so no table recreate is needed.

      content : doc body held *inside* ctx (NULL for file-backed docs, which
                are read from absolute_path as before)
      ext_id  : opaque stable id for ctx-owned docs (the handle agents/relay
                reference; survives a Pôle A→B substrate swap)
      kind    : lifecycle flag ('record' = event-anchored, never age-stale)

    Skip entirely if docs doesn't exist yet — _init_schema creates it fresh
    with these columns already present.
    """
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='docs'"
    ).fetchone()
    if not exists:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(docs)")}
    for col in ("content", "ext_id", "kind"):
        if col not in cols:
            conn.execute(f"ALTER TABLE docs ADD COLUMN {col} TEXT")
    conn.commit()


def _init_schema(conn: sqlite3.Connection, embed_dim: int) -> None:
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS docs (
            id INTEGER PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            source_id TEXT NOT NULL DEFAULT 'code',
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
            content TEXT,
            ext_id TEXT,
            kind TEXT,
            UNIQUE(workspace_id, source_id, path)
        );
        CREATE INDEX IF NOT EXISTS idx_docs_status ON docs(workspace_id, status);
        CREATE INDEX IF NOT EXISTS idx_docs_mtime ON docs(workspace_id, mtime DESC);
        CREATE INDEX IF NOT EXISTS idx_docs_source ON docs(workspace_id, source_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_docs_ext_id
            ON docs(ext_id) WHERE ext_id IS NOT NULL;

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
            top_result_tokens INTEGER NOT NULL DEFAULT 0,
            reranked INTEGER NOT NULL DEFAULT 0,
            llm_model TEXT,
            llm_tokens_in INTEGER NOT NULL DEFAULT 0,
            llm_tokens_out INTEGER NOT NULL DEFAULT 0,
            llm_elapsed_ms INTEGER NOT NULL DEFAULT 0,
            pre_top1_path TEXT,
            top1_changed INTEGER NOT NULL DEFAULT 0,
            top1_lift INTEGER NOT NULL DEFAULT 0,
            top5_overlap INTEGER NOT NULL DEFAULT 5
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
