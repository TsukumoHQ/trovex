import re
import sqlite3
from pathlib import Path

import sqlite_vec

# Backslash is the escape char we declare with `ESCAPE '\'` on LIKE clauses.
LIKE_ESCAPE_CHAR = "\\"

# Kinds that are their OWN event/snapshot and never take part in SSOT collapse —
# kept in sync with Settings.dup_ephemeral_kinds (config.py). Duplicated here as a
# literal because db.py is the schema leaf and must not import config.
EPHEMERAL_KINDS = ("record", "checkpoint", "resume")
_EPHEMERAL_SQL = "(" + ", ".join(f"'{k}'" for k in EPHEMERAL_KINDS) + ")"


def canonical_topic_slug(title: str | None) -> str | None:
    """Topic slug for the SSOT invariant: one live canonical per (workspace, topic).

    Lower-cased, non-alphanumeric runs collapsed to '-', trimmed. Returns None for
    an empty/blank title so an untitled doc never collides on the empty slug (a
    NULL canonical_topic is exempt from the partial unique index)."""
    if not title:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or None


def like_escape(s: str) -> str:
    """Escape LIKE wildcards (% and _) plus the escape char itself, so user
    input used inside a ``%...%`` substring filter matches *literally*.

    Pair every escaped value with ``ESCAPE '\\'`` in the SQL, e.g.::

        WHERE path LIKE ? ESCAPE '\\'   -- param: f"%{like_escape(qpath)}%"

    Without this, ``qpath='%'`` (or ``_``) is a wildcard and matches everything.
    """
    return (
        s.replace(LIKE_ESCAPE_CHAR, LIKE_ESCAPE_CHAR * 2)
        .replace("%", LIKE_ESCAPE_CHAR + "%")
        .replace("_", LIKE_ESCAPE_CHAR + "_")
    )


def open_db(db_path: Path, embed_dim: int = 384) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL: concurrent readers + one writer (the reindex runs in a *separate*
    # process from the server, so the in-process write lock isn't enough).
    # busy_timeout: wait for the lock instead of failing with "database is
    # locked" — fixes trovex_write / trovex_delete racing the reindex.
    conn.execute("PRAGMA journal_mode=WAL")
    # 30s: the reindex writes the whole corpus in one ~25s transaction; a chunk
    # write or backfill racing it must wait that out, not fail at 5s.
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except AttributeError as e:
        # Some Python builds (common with pyenv / Homebrew on macOS) compile
        # sqlite3 without loadable-extension support, so `enable_load_extension`
        # is missing and trovex can't load sqlite-vec (its vector index). Fail
        # with an actionable fix instead of a raw traceback on the first index.
        raise RuntimeError(
            "This Python's sqlite3 was built without loadable-extension support, "
            "so trovex can't load sqlite-vec (its vector index). Common with some "
            "pyenv/Homebrew Python builds.\n"
            "Fix — reinstall trovex on uv's managed Python, which has it:\n"
            "  uv tool install --force --python-preference only-managed trovex\n"
            "or rebuild your Python with "
            "PYTHON_CONFIGURE_OPTS='--enable-loadable-sqlite-extensions'."
        ) from e
    # Migration must run BEFORE _init_schema: CREATE TABLE IF NOT EXISTS won't
    # add columns to a pre-existing legacy docs table; we need to recreate it.
    _migrate_to_multi_source(conn)
    _migrate_embed_dim(conn, embed_dim)
    _migrate_add_trovex_store_columns(conn)
    _migrate_add_query_session(conn)
    _migrate_add_chunk_hash(conn)
    _migrate_add_lifecycle(conn)
    _migrate_add_canonical_topic(conn)  # AFTER lifecycle: supersede sets lifecycle='archived'
    _init_schema(conn, embed_dim)
    _backfill_docs_fts(conn)
    _migrate_purge_orphans(conn)
    return conn


def upsert_docs_fts(conn: sqlite3.Connection, doc_id: int, title: str, body: str) -> None:
    """(Re)index one doc's title+body into docs_fts (the doc-level BM25 side of the
    hybrid doc-router search). Delete-then-insert — FTS5 has no UPSERT. Does NOT
    commit. Called from both write paths (indexer._upsert_doc + store.put)."""
    conn.execute("DELETE FROM docs_fts WHERE doc_id = ?", (doc_id,))
    conn.execute(
        "INSERT INTO docs_fts(title, body, doc_id) VALUES (?, ?, ?)",
        (title or "", body or "", doc_id),
    )


def _backfill_docs_fts(conn: sqlite3.Connection) -> None:
    """One-time populate docs_fts for a store created before the doc-router hybrid.
    Owned docs carry their body in docs.content; file-backed docs are read from disk
    (best-effort). Runs only when docs_fts is empty but docs exist, so it's a no-op
    on every subsequent open."""
    if conn.execute("SELECT 1 FROM docs_fts LIMIT 1").fetchone():
        return
    for r in conn.execute("SELECT id, title, content, absolute_path FROM docs").fetchall():
        body = r["content"]
        if not body and r["absolute_path"]:
            try:
                body = Path(r["absolute_path"]).read_text(encoding="utf-8", errors="replace")
            except OSError:
                body = ""
        conn.execute(
            "INSERT INTO docs_fts(title, body, doc_id) VALUES (?, ?, ?)",
            (r["title"] or "", body or "", r["id"]),
        )


# Child tables keyed by docs.id. They all declare ON DELETE CASCADE, but the
# `foreign_keys` pragma is OFF (SQLite's default) and cannot simply be turned
# on: docs.dup_of_id references docs(id) with NO ACTION, and ~2/3 of a real
# store's rows carry one, so enforcement would turn every reindex delete of a
# dup-target into "FOREIGN KEY constraint failed". Giving dup_of_id ON DELETE
# SET NULL needs a full docs rebuild — until then, deletes cascade by hand and
# this tuple is the single list both delete paths walk.
_DOC_CHILD_TABLES = ("doc_tags", "doc_versions", "collection_docs")


def delete_doc_cascade(conn: sqlite3.Connection, doc_id: int) -> None:
    """Delete a doc and every row that hangs off it. Does NOT commit.

    Both delete paths (the store's trovex-owned docs and the indexer's
    file-backed ones) must go through here: deleting from `docs` alone leaks
    tags and versions, which is how a live store reached 2395 orphaned
    doc_tags rows and 648 orphaned doc_versions.
    """
    for c in conn.execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,)).fetchall():
        conn.execute("DELETE FROM vec_chunks WHERE rowid = ?", (c["id"],))
        conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (c["id"],))
    conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    for table in _DOC_CHILD_TABLES:
        conn.execute(
            f"DELETE FROM {table} WHERE doc_id = ?",  # sql-safe: fixed literal tuple
            (doc_id,),
        )
    conn.execute("DELETE FROM docs_fts WHERE doc_id = ?", (doc_id,))
    conn.execute("DELETE FROM vec_docs WHERE rowid = ?", (doc_id,))
    conn.execute("DELETE FROM docs WHERE id = ?", (doc_id,))


def _migrate_purge_orphans(conn: sqlite3.Connection) -> None:
    """Drop child rows whose doc is already gone (idempotent).

    One-time cleanup of the rows the pre-cascade delete paths left behind. Runs
    on open and is a no-op once clean, so it costs one indexed anti-join per
    child table.
    """
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='docs'"
    ).fetchone():
        return
    existing = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    for table in _DOC_CHILD_TABLES:
        if table not in existing:
            continue
        conn.execute(
            # sql-safe: table from the fixed literal tuple above, never user input
            f"DELETE FROM {table} WHERE doc_id NOT IN (SELECT id FROM docs)"
        )
    # Chunks carry their own children keyed by chunk id, so they can't be swept
    # with a bare DELETE — drop the embeddings and FTS rows first.
    if "chunks" in existing:
        orphans = conn.execute(
            "SELECT id FROM chunks WHERE doc_id NOT IN (SELECT id FROM docs)"
        ).fetchall()
        for c in orphans:
            conn.execute("DELETE FROM vec_chunks WHERE rowid = ?", (c["id"],))
            conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (c["id"],))
        if orphans:
            conn.execute("DELETE FROM chunks WHERE doc_id NOT IN (SELECT id FROM docs)")
    conn.commit()


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
    # Dim mismatch — wipe BOTH vec tables and clear any docs that referenced
    # them (forces a full reindex). docs.content_hash '' → all rows re-embed.
    # vec_chunks must go too: leaving it at the old dim made every
    # trovex_write crash with "Expected N dimensions" after an embedder
    # switch (found live). The chunk rows themselves are re-derived from doc
    # content, so they are dropped alongside their embeddings.
    conn.execute("DROP TABLE IF EXISTS vec_docs")
    conn.execute("DROP TABLE IF EXISTS vec_chunks")
    # DROP, not DELETE: this runs before _init_schema, and a legacy db can
    # carry vec_docs without the chunk tables. _init_schema recreates all.
    conn.execute("DROP TABLE IF EXISTS chunks_fts")
    conn.execute("DROP TABLE IF EXISTS chunks")
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


def _migrate_add_trovex_store_columns(conn: sqlite3.Connection) -> None:
    """Add the trovex-owned-store columns to an existing docs table.

    Additive (ALTER ADD COLUMN), unlike the multi-source migration — these
    columns are nullable and default NULL, so no table recreate is needed.

      content : doc body held *inside* trovex (NULL for file-backed docs, which
                are read from absolute_path as before)
      ext_id  : opaque stable id for trovex-owned docs (the handle agents/relay
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
    for col in ("content", "ext_id", "kind", "origin"):
        if col not in cols:
            conn.execute(
                f"ALTER TABLE docs ADD COLUMN {col} TEXT"
            )  # sql-safe: col from fixed literal tuple above, never user input
    conn.commit()


def _migrate_add_chunk_hash(conn: sqlite3.Connection) -> None:
    """Add chunks.content_hash to an existing store (additive).

    Enables content-addressed incremental re-embed: a chunk whose hash is
    unchanged on a doc rewrite reuses its embedding. Nullable-safe default '' so
    pre-migration chunks read as non-reusable and get re-embedded + stamped on
    the next rewrite of their doc. Skip if the table doesn't exist yet —
    _init_schema creates it with the column.
    """
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='chunks'"
    ).fetchone()
    if not exists:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
    if "content_hash" not in cols:
        conn.execute("ALTER TABLE chunks ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(doc_id, content_hash)")
        conn.commit()


def _migrate_add_lifecycle(conn: sqlite3.Connection) -> None:
    """Add docs.lifecycle to an existing store (additive).

    The curation-lifecycle axis (active/archived/pending_delete) that retrieval
    filters on, distinct from the quality `status`. Default 'active' so every
    pre-migration doc stays visible — no retrieval regression. Skip if the docs
    table doesn't exist yet; _init_schema creates it with the column.
    """
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='docs'"
    ).fetchone()
    if not exists:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(docs)")}
    if "lifecycle" not in cols:
        conn.execute("ALTER TABLE docs ADD COLUMN lifecycle TEXT NOT NULL DEFAULT 'active'")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_docs_lifecycle ON docs(workspace_id, lifecycle)"
        )
        conn.commit()


def _migrate_add_query_session(conn: sqlite3.Connection) -> None:
    """Add mcp_queries.session_id to an existing query log (additive).

    The savings receipt aggregates per session as well as per agent/lifetime;
    a store created before that has the rows but not the column. Nullable with a
    'unknown' default so old rows attribute to no session rather than breaking.
    Skip if the table doesn't exist yet — _init_schema creates it with the column.
    """
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='mcp_queries'"
    ).fetchone()
    if not exists:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(mcp_queries)")}
    if "session_id" not in cols:
        conn.execute(
            "ALTER TABLE mcp_queries ADD COLUMN session_id TEXT NOT NULL DEFAULT 'unknown'"
        )
        conn.commit()


def _migrate_add_canonical_topic(conn: sqlite3.Connection) -> None:
    """Add docs.canonical_topic + enforce SSOT (one live canonical per topic).

    canonical_topic is set ONLY for trovex-OWNED (source_id='trovex') non-ephemeral
    docs — file-backed code docs stay NULL, so two repos' READMEs never collide on
    the same slug. Backfills existing rows, then DE-DUPES the same-title canonical
    pairs that already exist (keep the newest, downgrade the rest to superseded +
    archived) BEFORE creating the partial unique index — otherwise the index build
    would fail on the pre-existing collision. Idempotent: skips once the column
    exists. _init_schema creates the column + index on a fresh store.
    """
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='docs'"
    ).fetchone()
    if not exists:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(docs)")}
    if "canonical_topic" in cols:
        return
    conn.execute("ALTER TABLE docs ADD COLUMN canonical_topic TEXT")
    # Backfill trovex-owned non-ephemeral docs (Python-side: the slug rules match
    # the live write path exactly).
    rows = conn.execute(
        f"""SELECT id, title FROM docs
            WHERE source_id = 'trovex' AND (kind IS NULL OR kind NOT IN {_EPHEMERAL_SQL})"""
    ).fetchall()
    for r in rows:
        slug = canonical_topic_slug(r["title"])
        if slug:
            conn.execute("UPDATE docs SET canonical_topic = ? WHERE id = ?", (slug, r["id"]))
    # De-dupe existing canonical collisions: per (workspace_id, canonical_topic),
    # keep the newest canonical, downgrade the rest to superseded + archived.
    groups = conn.execute(
        f"""SELECT workspace_id, canonical_topic
            FROM docs
            WHERE status = 'canonical' AND canonical_topic IS NOT NULL
              AND (kind IS NULL OR kind NOT IN {_EPHEMERAL_SQL})
            GROUP BY workspace_id, canonical_topic
            HAVING COUNT(*) > 1"""
    ).fetchall()
    for g in groups:
        ids = [
            row["id"]
            for row in conn.execute(
                """SELECT id FROM docs
                   WHERE status = 'canonical' AND workspace_id = ? AND canonical_topic = ?
                   ORDER BY mtime DESC, id DESC""",
                (g["workspace_id"], g["canonical_topic"]),
            )
        ]
        for stale_id in ids[1:]:  # keep ids[0] (newest) canonical, supersede the rest
            conn.execute(
                "UPDATE docs SET status = 'superseded', lifecycle = 'archived' WHERE id = ?",
                (stale_id,),
            )
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_docs_canonical_topic
           ON docs(workspace_id, canonical_topic)
           WHERE status = 'canonical' AND canonical_topic IS NOT NULL"""
    )
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
            origin TEXT,
            -- Curation lifecycle (distinct from `status`, which is a
            -- quality/dup CLASS that only *weights* ranking). Lifecycle
            -- FILTERS visibility: retrieval shows 'active' only by default.
            -- 'archived' = reversibly hidden (reachable explicitly), the soft
            -- alternative to hard-deleting a superseded/near-dup doc;
            -- 'pending_delete' = queued for removal (a grace window, hidden
            -- from retrieval). Everything defaults to 'active'.
            lifecycle TEXT NOT NULL DEFAULT 'active',
            -- SSOT: topic slug (slug of title) for trovex-owned non-ephemeral docs;
            -- NULL for file-backed + ephemeral docs. The partial unique index below
            -- enforces one LIVE canonical per (workspace, topic).
            canonical_topic TEXT,
            UNIQUE(workspace_id, source_id, path)
        );
        CREATE INDEX IF NOT EXISTS idx_docs_status ON docs(workspace_id, status);
        CREATE INDEX IF NOT EXISTS idx_docs_lifecycle ON docs(workspace_id, lifecycle);
        CREATE INDEX IF NOT EXISTS idx_docs_mtime ON docs(workspace_id, mtime DESC);
        CREATE INDEX IF NOT EXISTS idx_docs_source ON docs(workspace_id, source_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_docs_ext_id
            ON docs(ext_id) WHERE ext_id IS NOT NULL;
        -- One live canonical per topic (canonical_topic is NULL for file/ephemeral
        -- docs, and NULLs never collide in a unique index, so only trovex-owned
        -- non-ephemeral canonicals are constrained).
        CREATE UNIQUE INDEX IF NOT EXISTS idx_docs_canonical_topic
            ON docs(workspace_id, canonical_topic)
            WHERE status = 'canonical' AND canonical_topic IS NOT NULL;

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
            session_id TEXT NOT NULL DEFAULT 'unknown',
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
        CREATE INDEX IF NOT EXISTS idx_mcp_queries_session ON mcp_queries(session_id, ts DESC);

        -- Latest retrieval-quality eval runs (retrieval_eval.evaluate_retrieval),
        -- persisted so the savings receipt can gate its number on measured hit@1
        -- instead of assuming perfect routing. The receipt reads the newest row.
        CREATE TABLE IF NOT EXISTS retrieval_eval_runs (
            id INTEGER PRIMARY KEY,
            ts REAL NOT NULL,
            n INTEGER NOT NULL,
            k INTEGER NOT NULL,
            hit_at_1 REAL NOT NULL,
            hit_at_k REAL NOT NULL,
            mrr REAL NOT NULL,
            recall_at_k REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_retrieval_eval_ts ON retrieval_eval_runs(ts DESC);

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

        -- Chunk-level retrieval (structure-aware chunks + their embeddings)
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            doc_id INTEGER NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            heading_path TEXT,
            content TEXT NOT NULL,
            tokens_est INTEGER NOT NULL DEFAULT 0,
            -- Merkle/content-addressed incremental re-embed: sha256 of the chunk's
            -- embed_text (title + heading + text — everything that feeds the
            -- embedding). On a doc rewrite, a chunk whose hash is unchanged keeps
            -- its existing embedding instead of being re-embedded. Legacy rows have
            -- '' → treated as non-reusable, so the first rewrite re-embeds + stamps.
            content_hash TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(doc_id, content_hash);
        CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
            embedding float[{embed_dim}] distance_metric=cosine
        );
        -- Keyword side of hybrid retrieval (BM25). chunk_id = chunks.id.
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content, chunk_id UNINDEXED
        );
        -- Keyword side of the DOC-ROUTER hybrid (BM25 over whole docs). doc_id =
        -- docs.id. The flagship `trovex`/`trovex_search` fuses this with the dense
        -- vec_docs KNN via RRF so exact tokens (error codes, fn/API names, paths,
        -- flags, versions) the embedding blurs still rank. Maintained on every doc
        -- upsert (indexer + store) and pruned in delete_doc_cascade.
        CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
            title, body, doc_id UNINDEXED
        );

        -- Tags (free + hierarchical 'a/b/c') for org + metadata filtering
        CREATE TABLE IF NOT EXISTS doc_tags (
            doc_id INTEGER NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
            tag TEXT NOT NULL,
            PRIMARY KEY (doc_id, tag)
        );
        CREATE INDEX IF NOT EXISTS idx_doc_tags_tag ON doc_tags(tag);

        -- Collections = named saved filters (kind 'filter') or curated lists
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL DEFAULT 'filter',
            filter_json TEXT,
            created REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS collection_docs (
            collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
            doc_id INTEGER NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
            PRIMARY KEY (collection_id, doc_id)
        );

        -- Doc history: a snapshot of the previous content on every overwrite
        CREATE TABLE IF NOT EXISTS doc_versions (
            id INTEGER PRIMARY KEY,
            doc_id INTEGER NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            title TEXT,
            ts REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_doc_versions_doc ON doc_versions(doc_id, ts DESC);

        -- Delete tombstones: a recoverable snapshot of an owned doc taken BEFORE
        -- it is deleted. Deliberately has NO foreign key to docs — it must
        -- OUTLIVE the doc row (doc_versions FK-cascades away with the doc, so it
        -- can't serve this). Closes the delete arm of the vague2 silent-loss
        -- class: a deleted owned doc is restorable, not vaporized.
        CREATE TABLE IF NOT EXISTS doc_tombstones (
            id INTEGER PRIMARY KEY,
            ext_id TEXT,
            title TEXT,
            content TEXT NOT NULL,
            kind TEXT,
            tags_json TEXT,
            source_id TEXT,
            deleted_ts REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_doc_tombstones_ts ON doc_tombstones(deleted_ts DESC);
        CREATE INDEX IF NOT EXISTS idx_doc_tombstones_ext ON doc_tombstones(ext_id);
        """
    )
    conn.commit()
