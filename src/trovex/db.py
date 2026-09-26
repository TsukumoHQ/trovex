import hashlib
import logging
import re
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

import sqlite_vec

log = logging.getLogger("trovex.db")

# Backslash is the escape char we declare with `ESCAPE '\'` on LIKE clauses.
LIKE_ESCAPE_CHAR = "\\"

# A WAL past this size means checkpointing isn't keeping up (normally sqlite
# auto-checkpoints around 1000 pages / ~4MB) — most often because a stranded
# open transaction is blocking it. Force one and warn so it shows up in logs
# instead of silently growing until a write finally hits "database is locked".
WAL_WARN_BYTES = 10 * 1024 * 1024

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


def open_db(db_path: Path, embed_dim: int = 384, embed_model: str = "") -> sqlite3.Connection:
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
    _migrate_add_query_used(conn)
    _migrate_add_chunk_hash(conn)
    _migrate_add_chunker_version(conn)
    _migrate_add_lifecycle(conn)
    _migrate_add_canonical_topic(conn)  # AFTER lifecycle: supersede sets lifecycle='archived'
    _migrate_add_importance(conn)
    _migrate_add_index_run_metrics(conn)
    _migrate_add_index_jobs_link(conn)
    _init_schema(conn, embed_dim)
    # AFTER _init_schema: on a legacy store the flat vec tables survived CREATE IF
    # NOT EXISTS; rebuild them partitioned, reusing embeddings (P2a).
    _migrate_partition_vec(conn, embed_dim)
    # AFTER partitioning: adds the embed_model metadata column (task 6851d755),
    # so it always sees the partitioned DDL shape.
    _migrate_add_vec_embed_model(conn, embed_dim, embed_model)
    _backfill_docs_fts(conn)
    _migrate_purge_orphans(conn)
    # task 6851d755: stamp store_meta['embed_model'] once — a fresh store, or
    # a pre-existing one on its first boot after this shipped. Only from this
    # point on can a LATER runtime embed_model change (same dim — the dim
    # check alone misses it) ever be detected; skipped when a rebuild is
    # already pending (the dim mismatch case) so store_meta never claims a
    # model the live vec tables don't actually hold yet.
    if (
        embed_model
        and get_store_meta(conn, "embed_model") is None
        and not rebuild_vec_needed(conn, embed_dim, embed_model)
    ):
        set_store_meta(conn, "embed_model", embed_model)
        conn.commit()
    return conn


def checkpoint_if_wal_large(conn: sqlite3.Connection, db_path: Path) -> None:
    """Force a WAL checkpoint if trovex.db-wal has grown past WAL_WARN_BYTES.

    Called after every store write COMMIT as a backstop: if a checkpoint isn't
    keeping the WAL down (e.g. a long-running reader, or the WAL has grown
    because writes were piling up before this call existed), this notices and
    forces one instead of letting it grow unbounded toward "database is locked".

    Best-effort only, by design: the caller's write already committed before
    this runs, so nothing here may ever propagate — an unexpected exception
    (a permissions error on stat(), a busy/corrupt-adjacent checkpoint) must
    not turn an already-successful write into a reported failure.

    PASSIVE, not TRUNCATE: TRUNCATE needs exclusive access (no reader on any
    older WAL frame) and will busy-wait up to busy_timeout on THIS connection
    — the shared write connection — if it can't get it, wedging every write
    queued behind it. Under concurrent read traffic there's almost always an
    in-flight reader, so TRUNCATE reliably starved out to the 30s busy_timeout
    (prod 2026-08-31, task 7768dbe6: trovex_write/search both stalled to the
    exact 30000ms busy_timeout). PASSIVE checkpoints as many frames as it can
    without waiting on anyone and returns immediately either way — it may
    leave the WAL only partially truncated under sustained load, but it never
    blocks the write path."""
    try:
        wal_path = db_path.with_name(db_path.name + "-wal")
        size = wal_path.stat().st_size
        if size <= WAL_WARN_BYTES:
            return
        log.warning("trovex.db WAL at %d bytes (> %d), forcing checkpoint", size, WAL_WARN_BYTES)
        conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    except OSError:
        pass
    except sqlite3.Error as e:
        log.warning("wal checkpoint deferred: %s", e)


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


# --- partitioned vec0 write helpers (P2a) ----------------------------------
# vec_docs/vec_chunks carry the doc's source_id (partition key) + kind/lifecycle/
# status (metadata, never NULL). These helpers are the SINGLE denormalisation
# point so the ~dozen embed/status sites can't drift the metadata out of sync.


def _doc_vec_meta(conn: sqlite3.Connection, doc_id: int) -> tuple | None:
    """(source_id, kind, lifecycle, status) for a doc, kind COALESCEd to 'doc' so
    the vec0 metadata column is never NULL (vec0 rejects NULL metadata)."""
    r = conn.execute(
        "SELECT source_id, kind, lifecycle, status FROM docs WHERE id = ?", (doc_id,)
    ).fetchone()
    if r is None:
        return None
    return (r["source_id"], r["kind"] or "doc", r["lifecycle"], r["status"])


def vec_docs_put(conn: sqlite3.Connection, doc_id: int, emb_blob: bytes, embed_model: str = "") -> None:
    """Upsert a doc's embedding + partition/metadata into vec_docs. Does NOT commit.

    `embed_model` (task 6851d755) stamps which model produced `emb_blob` — lets a
    future lazy re-embed sweep or the rebuild_vec_shadow job tell a row's current
    model apart from the store's configured one, without needing a global rebuild
    just to check. Empty string (never NULL — vec0 rejects NULL metadata) for a
    caller that hasn't been updated to pass it; treated as 'unknown', never a
    false match against a real model name."""
    meta = _doc_vec_meta(conn, doc_id)
    if meta is None:
        return
    src, kind, lifecycle, status = meta
    conn.execute("DELETE FROM vec_docs WHERE rowid = ?", (doc_id,))
    conn.execute(
        "INSERT INTO vec_docs(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (doc_id, src, emb_blob, kind, lifecycle, status, embed_model),
    )


def vec_chunks_put(conn: sqlite3.Connection, chunk_id: int, emb_blob: bytes, embed_model: str = "") -> None:
    """Upsert a chunk's embedding into vec_chunks with its PARENT doc's partition +
    metadata (a chunk inherits them). Looks up the parent doc from the chunk row.
    Does NOT commit. `embed_model`: see vec_docs_put."""
    parent = conn.execute("SELECT doc_id FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
    if parent is None:
        return
    meta = _doc_vec_meta(conn, parent["doc_id"])
    if meta is None:
        return
    src, kind, lifecycle, status = meta
    conn.execute("DELETE FROM vec_chunks WHERE rowid = ?", (chunk_id,))
    conn.execute(
        "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (chunk_id, src, emb_blob, kind, lifecycle, status, embed_model),
    )


def embed_cache_get_many(
    conn: sqlite3.Connection, text_hashes: list[str], embed_model: str, chunker_version: str
) -> dict[str, bytes]:
    """Batch-lookup cached embeddings for `text_hashes` under (embed_model,
    chunker_version). Returns only the hits, as {text_hash: serialized_blob} —
    ready to write straight into vec_docs/vec_chunks. Read-only."""
    if not text_hashes:
        return {}
    placeholders = ",".join("?" * len(text_hashes))
    rows = conn.execute(
        f"""SELECT text_hash, embedding FROM embed_cache
            WHERE text_hash IN ({placeholders})
              AND embed_model = ? AND chunker_version = ?""",
        (*text_hashes, embed_model, chunker_version),
    ).fetchall()
    return {r["text_hash"]: r["embedding"] for r in rows}


def embed_cache_put_many(
    conn: sqlite3.Connection,
    rows: list[tuple[str, str, str, bytes, float]],
) -> None:
    """Batch-insert freshly computed embeddings, each row a
    (text_hash, embed_model, chunker_version, embedding_blob, created_at) tuple.
    INSERT OR REPLACE: a rare hash collision across two different real texts
    would only mean one of them re-embeds on its next miss, never a wrong
    vector served silently. Does NOT commit."""
    if not rows:
        return
    conn.executemany(
        """INSERT OR REPLACE INTO embed_cache
           (text_hash, embed_model, chunker_version, embedding, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        rows,
    )


# embed_cache chunker_version sentinels for non-chunked embeddings — there's
# no chunker involved, but the cache's primary key needs a value in that
# column, and a fixed sentinel per embedding KIND keeps doc-level (both the
# file-indexed and the trovex-owned store paths — same content, same model,
# same vector, so they deliberately SHARE this one) and markdown-chunk
# entries from ever colliding with each other or with cAST code-chunk
# entries (chunking_code.CHUNKER_VERSION) under the same text_hash.
DOC_EMBED_NS = "doc"
MARKDOWN_CHUNK_EMBED_NS = "md-chunk-1"


def resolve_embedding_blobs(
    conn: sqlite3.Connection,
    embedder,
    texts: list[str],
    embed_model: str,
    chunker_version: str,
    *,
    commit_before_embed: bool = True,
) -> tuple[list[bytes], int, int]:
    """Resolve `texts` to serialized sqlite-vec blobs via embed_cache, calling
    the embedder only for what's missing. Shared by Indexer (reindex/fs-watch)
    and SqliteStore (trovex_write) — both had the same bug (task cbb8e8fb):
    the ONNX model call is CPU-bound and can run seconds to minutes, and
    calling it while `conn` has an open transaction holds the WAL writer slot
    for the whole duration, starving every other writer on the shared db file.

    commit_before_embed=True (Indexer's case) commits `conn` before calling
    embedder.embed() on a miss, so no transaction is open while the model
    runs — the caller must have nothing pending it needs atomic with the row
    writes that follow this call (Indexer's periodic-commit design already
    accepts that: a crash mid-run only loses work since the last checkpoint).
    commit_before_embed=False (SqliteStore's case) skips that commit: a single
    trovex_write is one atomic doc write end-to-end, and committing mid-flow
    would let a crash between the commit and the final vector write leave a
    doc row with content but no vector — silently unsearchable. The embed
    cache still helps there (a hit skips the model call outright); the
    transaction-narrowing half of the fix is store.py's own to do later,
    without breaking that atomicity (task cbb8e8fb follow-up).

    Deduplicates WITHIN `texts` too, not just against the persisted table:
    two identical texts in one call (a duplicate doc, a rename) share one
    embed() call even though neither was cached yet when this call started.

    Returns (blobs in the SAME order as `texts`, cache hits, cache misses).
    """
    if not texts:
        return [], 0, 0
    hashes = [hashlib.sha256(t.encode("utf-8", errors="replace")).hexdigest() for t in texts]
    resolved = embed_cache_get_many(conn, hashes, embed_model, chunker_version)
    miss_order: list[str] = []  # first-seen order of hashes with no vector yet
    hash_to_text: dict[str, str] = {}
    for h, t in zip(hashes, texts, strict=True):
        if h not in resolved and h not in hash_to_text:
            miss_order.append(h)
        hash_to_text.setdefault(h, t)
    hits = len(hashes) - len(miss_order)
    misses = len(miss_order)
    if miss_order:
        if commit_before_embed:
            conn.commit()  # no transaction open while the model runs
        fresh = list(embedder.embed([hash_to_text[h] for h in miss_order]))
        new_rows = []
        now = time.time()
        for h, emb in zip(miss_order, fresh, strict=True):
            blob = sqlite_vec.serialize_float32(emb.tolist())
            resolved[h] = blob
            new_rows.append((h, embed_model, chunker_version, blob, now))
        embed_cache_put_many(conn, new_rows)
    return [resolved[h] for h in hashes], hits, misses


def _doc_embed_text(content: str, title: str) -> str:
    """Same shape as Indexer._embed_text / SqliteStore._embed (task cbb8e8fb
    keeps all three identical on purpose so they share embed_cache entries)."""
    import re as _re

    stripped = _re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=_re.DOTALL)
    return f"{title}\n\n{stripped}"[:8000]


def _chunk_embed_text(doc_title: str, heading_path: str, content: str) -> str:
    """Reconstructs Chunk.embed_text(title) from stored columns (no Chunk
    object survives past the original chunk_fn() call) — same prefix-fusion
    shape: breadcrumb (title > heading path) + blank line + body."""
    bc = f"{doc_title} > {heading_path}" if heading_path else doc_title
    return f"{bc}\n\n{content}" if bc else content


def rebuild_vec_shadow(
    conn: sqlite3.Connection,
    embedder,
    embed_dim: int,
    *,
    batch_size: int = 200,
    on_batch: Callable[[str, int, int], None] | None = None,
) -> dict:
    """Rebuild vec_docs/vec_chunks under embedder's CURRENT model/dim, without
    ever holding a write lock for the expensive part (task 6851d755).

    sqlite-vec's vec0 module does NOT support ALTER TABLE RENAME — verified
    empirically: SQLite renames the master-table entry but vec0 never gets a
    chance to rename its own internal shadow tables (_rowids, _chunks, ...),
    so every read after a literal rename fails with "no such table:
    ..._rowids". A rename-based atomic swap (the ticket's original wording)
    is not achievable for vec0; this is the correct equivalent instead: build
    a plain (non-vec0) STAGING snapshot of every re-embedded row in short,
    individually-committed batches (each batch's model calls run with NO
    transaction open — resolve_embedding_blobs's commit_before_embed), then
    do the mechanical part — drop the old vec0 tables, create fresh ones at
    the new dim, bulk-copy from staging — in ONE short transaction. Only that
    final bulk-copy briefly excludes another WRITER; a reader on any other
    connection (WAL) keeps seeing the OLD vec_docs/vec_chunks intact right up
    until this transaction commits, then sees the fully-swapped new ones —
    never a torn or partial read either way.

    Returns {"docs": n, "chunks": n, "elapsed_sec": float}."""
    t0 = time.time()
    embed_model = embedder.name
    conn.execute("DROP TABLE IF EXISTS temp._vec_rebuild_docs")
    conn.execute("DROP TABLE IF EXISTS temp._vec_rebuild_chunks")
    conn.execute(
        "CREATE TEMP TABLE _vec_rebuild_docs "
        "(rid INTEGER PRIMARY KEY, source_id TEXT, embedding BLOB, kind TEXT, lifecycle TEXT, status TEXT)"
    )
    conn.execute(
        "CREATE TEMP TABLE _vec_rebuild_chunks "
        "(rid INTEGER PRIMARY KEY, source_id TEXT, embedding BLOB, kind TEXT, lifecycle TEXT, status TEXT)"
    )

    # --- docs, batched -----------------------------------------------------
    doc_rows = conn.execute(
        "SELECT id, title, content, absolute_path, source_id, "
        "COALESCE(kind, 'doc') AS kind, lifecycle, status FROM docs"
    ).fetchall()
    n_docs = len(doc_rows)
    for i in range(0, n_docs, batch_size):
        batch = doc_rows[i : i + batch_size]
        texts: list[str] = []
        keep: list[sqlite3.Row] = []
        for r in batch:
            if r["content"] is not None:
                body = r["content"]
            else:
                try:
                    body = Path(r["absolute_path"]).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    log.warning(
                        "rebuild_vec_shadow: %s vanished since indexing, skipping", r["absolute_path"]
                    )
                    continue
            texts.append(_doc_embed_text(body, r["title"] or ""))
            keep.append(r)
        blobs, _, _ = resolve_embedding_blobs(
            conn, embedder, texts, embed_model, DOC_EMBED_NS, commit_before_embed=True
        )
        for r, blob in zip(keep, blobs, strict=True):
            conn.execute(
                "INSERT OR REPLACE INTO _vec_rebuild_docs VALUES (?, ?, ?, ?, ?, ?)",
                (r["id"], r["source_id"], blob, r["kind"], r["lifecycle"], r["status"]),
            )
        conn.commit()
        if on_batch:
            on_batch("docs", min(i + batch_size, n_docs), n_docs)

    # --- chunks, batched -----------------------------------------------------
    chunk_rows = conn.execute(
        "SELECT c.id, c.heading_path, c.content, d.title AS doc_title, d.source_id, "
        "COALESCE(d.kind, 'doc') AS kind, d.lifecycle, d.status "
        "FROM chunks c JOIN docs d ON d.id = c.doc_id"
    ).fetchall()
    n_chunks = len(chunk_rows)
    for i in range(0, n_chunks, batch_size):
        batch = chunk_rows[i : i + batch_size]
        texts = [
            _chunk_embed_text(r["doc_title"] or "", r["heading_path"] or "", r["content"]) for r in batch
        ]
        blobs, _, _ = resolve_embedding_blobs(
            conn, embedder, texts, embed_model, MARKDOWN_CHUNK_EMBED_NS, commit_before_embed=True
        )
        for r, blob in zip(batch, blobs, strict=True):
            conn.execute(
                "INSERT OR REPLACE INTO _vec_rebuild_chunks VALUES (?, ?, ?, ?, ?, ?)",
                (r["id"], r["source_id"], blob, r["kind"], r["lifecycle"], r["status"]),
            )
        conn.commit()
        if on_batch:
            on_batch("chunks", min(i + batch_size, n_chunks), n_chunks)

    # --- swap: one short transaction, mechanical only -----------------------
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DROP TABLE IF EXISTS vec_docs")
        conn.execute("DROP TABLE IF EXISTS vec_chunks")
        conn.execute(
            f"""CREATE VIRTUAL TABLE vec_docs USING vec0(
                source_id TEXT partition key,
                embedding float[{embed_dim}] distance_metric=cosine,
                kind TEXT, lifecycle TEXT, status TEXT, embed_model TEXT
            )"""
        )
        conn.execute(
            f"""CREATE VIRTUAL TABLE vec_chunks USING vec0(
                source_id TEXT partition key,
                embedding float[{embed_dim}] distance_metric=cosine,
                kind TEXT, lifecycle TEXT, status TEXT, embed_model TEXT
            )"""
        )
        conn.execute(
            "INSERT INTO vec_docs(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
            "SELECT rid, source_id, embedding, kind, lifecycle, status, ? FROM _vec_rebuild_docs",
            (embed_model,),
        )
        conn.execute(
            "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
            "SELECT rid, source_id, embedding, kind, lifecycle, status, ? FROM _vec_rebuild_chunks",
            (embed_model,),
        )
        conn.execute("DROP TABLE _vec_rebuild_docs")
        conn.execute("DROP TABLE _vec_rebuild_chunks")
        set_store_meta(conn, "embed_model", embed_model)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {"docs": len(doc_rows), "chunks": len(chunk_rows), "elapsed_sec": time.time() - t0}


def sync_doc_chunks(
    conn: sqlite3.Connection, doc_id: int, content: str, title: str, chunk_fn, chunker_version: str = ""
) -> list[tuple[int, str]]:
    """(Re)chunk a doc via `chunk_fn(content) -> list[Chunk]`; return (chunk_id,
    embed_text) for chunks that NEED embedding — i.e. only the new/changed ones.

    Content-addressed (Merkle) incremental, chunker-agnostic: each new chunk is
    keyed by the sha256 of its embed_text (title + heading/breadcrumb + text —
    the full embedding input). A new chunk whose hash already exists among the
    doc's current chunks reuses that chunk's row + embedding + FTS unchanged
    (only its position is refreshed), so an edit to one section/symbol re-embeds
    one chunk, not the whole doc. Chunks whose hash is no longer present are
    deleted. Shared by SqliteStore (markdown, via chunk_markdown) and Indexer
    (markdown + code, via chunk_markdown/chunk_code dispatch) — the sync
    mechanism itself needs no per-chunker special-casing. Does NOT commit.

    `chunker_version` (task 6851d755) gates reuse on TOP of the content-hash
    match: an existing chunk stamped with a DIFFERENT chunker_version is never
    put in the reusable pool, even if its hash happens to still match — a
    chunker boundary/breadcrumb change must never be silently trusted just
    because the resulting text coincided with the old output. Every kept
    (reused) row is already correct by construction (same doc, same call), so
    only new/inserted rows need the current version stamped."""
    existing = conn.execute(
        "SELECT id, content_hash, chunker_version FROM chunks WHERE doc_id = ? ORDER BY id", (doc_id,)
    ).fetchall()
    reusable: dict[str, list[int]] = {}
    for row in existing:
        h = row["content_hash"]
        if h and row["chunker_version"] == chunker_version:
            reusable.setdefault(h, []).append(row["id"])

    to_embed: list[tuple[int, str]] = []
    kept: set[int] = set()
    for ch in chunk_fn(content):
        embed_text = ch.embed_text(title)
        h = hashlib.sha256(embed_text.encode("utf-8", errors="replace")).hexdigest()
        heading = " > ".join(ch.heading_path)
        pool = reusable.get(h)
        if pool:
            cid = pool.pop()
            kept.add(cid)
            conn.execute("UPDATE chunks SET chunk_index = ? WHERE id = ?", (ch.index, cid))
        else:
            cur = conn.execute(
                """INSERT INTO chunks
                       (doc_id, chunk_index, heading_path, content, tokens_est, content_hash, chunker_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, ch.index, heading, ch.text, ch.tokens_est, h, chunker_version),
            )
            cid = cur.lastrowid
            conn.execute("INSERT INTO chunks_fts(content, chunk_id) VALUES (?, ?)", (ch.text, cid))
            kept.add(cid)
            to_embed.append((cid, embed_text))

    for row in existing:
        if row["id"] not in kept:
            conn.execute("DELETE FROM vec_chunks WHERE rowid = ?", (row["id"],))
            conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (row["id"],))
            conn.execute("DELETE FROM chunks WHERE id = ?", (row["id"],))
    return to_embed


def vec_sync_meta(conn: sqlite3.Connection, doc_id: int) -> None:
    """Sync a doc's (and its chunks') vec0 METADATA to the current docs row after a
    status/lifecycle/kind change that did NOT re-embed. source_id (partition key)
    never changes for a doc, so it is not touched. Does NOT commit."""
    meta = _doc_vec_meta(conn, doc_id)
    if meta is None:
        return
    _src, kind, lifecycle, status = meta
    conn.execute(
        "UPDATE vec_docs SET kind = ?, lifecycle = ?, status = ? WHERE rowid = ?",
        (kind, lifecycle, status, doc_id),
    )
    for c in conn.execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,)).fetchall():
        conn.execute(
            "UPDATE vec_chunks SET kind = ?, lifecycle = ?, status = ? WHERE rowid = ?",
            (kind, lifecycle, status, c["id"]),
        )


def reconcile_vec_meta(
    conn: sqlite3.Connection,
    *,
    on_batch: Callable[[], None] | None = None,
    batch_size: int = 200,
) -> int:
    """Sync vec0 metadata to docs for every row whose kind/lifecycle/status DRIFTED
    (e.g. after compute_status' bulk status rewrite). Only touches genuinely-changed
    rows — cheap when most are unchanged. vec0 forbids a correlated bulk UPDATE
    (partition-key restriction), so it re-syncs the mismatches one rowid at a time.
    Returns the count synced. Does NOT commit.

    ``on_batch``, when given, is called after every ``batch_size`` synced rows.
    The per-row loop can be long — a sweep's bulk stale/lifecycle UPDATE can
    leave thousands of mismatched rows (live: 4538 after one sweep_bloat) — and
    a caller holding a lock across the whole loop starves concurrent writers.
    The store passes a callback that commits and briefly RELEASES its writer
    lock so a concurrent put() isn't blocked for the full resync (the residual
    in-process write wedge). ``on_batch`` never fires for the final partial
    batch — the caller commits that. The ``mismatched`` set is materialized up
    front, so releasing the lock between batches can't invalidate the loop and a
    row deleted by a racing writer mid-loop is a safe no-op (vec_sync_meta skips
    a missing doc)."""
    mismatched = conn.execute(
        """SELECT d.id FROM docs d JOIN vec_docs v ON v.rowid = d.id
           WHERE v.kind != COALESCE(d.kind, 'doc')
              OR v.lifecycle != d.lifecycle
              OR v.status != d.status"""
    ).fetchall()
    for i, r in enumerate(mismatched, 1):
        vec_sync_meta(conn, r["id"])
        if on_batch is not None and i % batch_size == 0:
            on_batch()
    return len(mismatched)


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
    # task 6851d755: a NON-EMPTY store never takes the inline wipe below —
    # that used to mean "database is locked" for every writer racing the
    # DROP+rebuild, and the store stays fully empty of vectors until a full
    # reindex finishes (minutes, for a real corpus). Leave the OLD (still
    # internally consistent) vec tables serving reads/writes exactly as
    # before; the caller (server startup — see rebuild_vec_needed) is
    # responsible for enqueueing a 'rebuild_vec' index job, which does the
    # equivalent swap WITHOUT the blocking window (rebuild_vec_shadow).
    # An EMPTY store has nothing to lose and no write stall to avoid — wipe
    # it instantly, exactly as before (the fallback this migration keeps).
    doc_count = conn.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
    if doc_count > 0:
        log.warning(
            "embed dim mismatch (%d -> %d) on a non-empty store (%d docs) — leaving old "
            "vec tables in place; enqueue a 'rebuild_vec' index job (db.rebuild_vec_shadow) "
            "to complete the swap instead of blocking here",
            current_dim, embed_dim, doc_count,
        )
        return
    # Dim mismatch on an EMPTY store — wipe BOTH vec tables and clear any docs
    # that referenced them (forces a full reindex). docs.content_hash '' →
    # all rows re-embed. vec_chunks must go too: leaving it at the old dim
    # made every trovex_write crash with "Expected N dimensions" after an
    # embedder switch (found live). The chunk rows themselves are re-derived
    # from doc content, so they are dropped alongside their embeddings.
    #
    # BEGIN IMMEDIATE makes the whole drop+clear sequence atomic: a process
    # killed mid-sequence (crash, kickstart restart, machine sleep) used to
    # leave vec_docs dropped but vec_chunks/chunks/chunks_fts intact (or vice
    # versa) — a state _init_schema's CREATE IF NOT EXISTS never repairs on
    # its own reliably, since a later boot's own guard (`if not row: return`
    # above) treats the missing table as "nothing to migrate" and silently
    # skips the rest forever, permanently wedging trovex_write on "no such
    # table: vec_docs" (found live — task 743ad0d3). Now either the full
    # sequence commits or none of it does; an interruption leaves the OLD
    # tables untouched for a clean retry on the next boot.
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DROP TABLE IF EXISTS vec_docs")
        conn.execute("DROP TABLE IF EXISTS vec_chunks")
        # DROP, not DELETE: this runs before _init_schema, and a legacy db can
        # carry vec_docs without the chunk tables. _init_schema recreates all.
        conn.execute("DROP TABLE IF EXISTS chunks_fts")
        conn.execute("DROP TABLE IF EXISTS chunks")
        conn.execute("UPDATE docs SET content_hash = ''")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def get_store_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM store_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_store_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Does NOT commit — caller controls the transaction (rebuild_vec_shadow
    stamps this inside its own swap transaction; a standalone caller commits)."""
    conn.execute(
        "INSERT INTO store_meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def rebuild_vec_needed(conn: sqlite3.Connection, embed_dim: int, embed_model: str) -> bool:
    """True when vec_docs/vec_chunks need a rebuild_vec_shadow pass (task
    6851d755) — checked at server startup instead of _migrate_embed_dim's
    inline wipe. EITHER of:
      - a dim mismatch (float[N] in the vec_docs DDL != embed_dim) — the hard
        case: sqlite-vec can't hold a different-dim vector in the same table
        at all, so old rows are unreadable at the new dim the instant it
        starts writing.
      - a store_meta['embed_model'] mismatch — a SAME-dim model swap (the
        task's own validation scenario: bge-small-en-v1.5 -> paraphrase-
        multilingual-MiniLM-L12-v2 are BOTH 384-dim, so the dim check alone
        would never see this case at all).
    False for an empty store (nothing to rebuild) or when store_meta has
    never been stamped (a legacy store on its first boot after this shipped —
    open_db stamps it then, assumed to match rather than forcing a spurious
    rebuild on the very next boot with no real model change)."""
    if conn.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"] == 0:
        return False
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='vec_docs'"
    ).fetchone()
    if ddl:
        m = re.search(r"float\[(\d+)\]", ddl["sql"] or "")
        if m and int(m.group(1)) != embed_dim:
            return True
    stamped = get_store_meta(conn, "embed_model")
    return stamped is not None and stamped != embed_model


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


def _migrate_add_chunker_version(conn: sqlite3.Connection) -> None:
    """Add chunks.chunker_version to an existing store (additive; task
    6851d755). A chunker boundary/breadcrumb change bumps CHUNKER_VERSION
    (chunking.py / chunking_code.py) so sync_doc_chunks re-derives every
    existing chunk of a re-synced doc instead of trusting a stale-boundary
    chunk whose content_hash still coincidentally matches. Nullable-safe
    default '' so pre-migration chunks read as non-reusable and get
    re-chunked + stamped on the next rewrite of their doc — same shape as
    _migrate_add_chunk_hash. Skip if the table doesn't exist yet."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='chunks'"
    ).fetchone()
    if not exists:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
    if "chunker_version" not in cols:
        conn.execute("ALTER TABLE chunks ADD COLUMN chunker_version TEXT NOT NULL DEFAULT ''")
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


def _migrate_add_query_used(conn: sqlite3.Connection) -> None:
    """Add mcp_query_results.used to an existing query log (additive, task
    b47301eb). Nullable-by-default (0) so a store created before this migration
    just has every served row unlabelled until the next read marks one, rather
    than breaking. Skip if the table doesn't exist yet — _init_schema creates it
    with the column."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='mcp_query_results'"
    ).fetchone()
    if not exists:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(mcp_query_results)")}
    if "used" not in cols:
        conn.execute("ALTER TABLE mcp_query_results ADD COLUMN used INTEGER NOT NULL DEFAULT 0")
        conn.commit()


def _migrate_add_importance(conn: sqlite3.Connection) -> None:
    """Add docs.importance + docs.pinned to an existing store (additive, P3).

    importance is a derived ranking signal (status + pinned + access frequency),
    recomputed by the retention sweep; pinned marks a doc exempt from TTL
    eviction. Both default to 0 so existing rows rank exactly as before until the
    first recompute. Skip if the table doesn't exist yet — _init_schema creates
    the columns."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='docs'"
    ).fetchone()
    if not exists:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(docs)")}
    if "importance" not in cols:
        conn.execute("ALTER TABLE docs ADD COLUMN importance REAL NOT NULL DEFAULT 0")
    if "pinned" not in cols:
        conn.execute("ALTER TABLE docs ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
    if "lifecycle_changed_at" not in cols:
        conn.execute("ALTER TABLE docs ADD COLUMN lifecycle_changed_at REAL NOT NULL DEFAULT 0")
    conn.commit()


def _migrate_add_index_run_metrics(conn: sqlite3.Connection) -> None:
    """Add index_runs.docs_changed/docs_total/wall_ms to an existing store
    (additive). Lets a run's cost be measured directly (task 67ebd68c) instead
    of inferred from added+updated+removed and duration_sec alone. Skip if the
    table doesn't exist yet — _init_schema creates it with the columns."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='index_runs'"
    ).fetchone()
    if not exists:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(index_runs)")}
    for col, decl in (
        ("docs_changed", "INTEGER NOT NULL DEFAULT 0"),
        ("docs_total", "INTEGER NOT NULL DEFAULT 0"),
        ("wall_ms", "REAL NOT NULL DEFAULT 0"),
        # task cbb8e8fb: per-phase cost breakdown + embed-cache effectiveness,
        # so a slow run's dominant phase is visible without re-profiling live.
        ("phase_ms", "TEXT NOT NULL DEFAULT '{}'"),
        ("embed_cache_hits", "INTEGER NOT NULL DEFAULT 0"),
        ("embed_cache_misses", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if col not in cols:
            conn.execute(
                f"ALTER TABLE index_runs ADD COLUMN {col} {decl}"
            )  # sql-safe: col/decl from fixed literal tuple above, never user input
    conn.commit()


def _migrate_add_index_jobs_link(conn: sqlite3.Connection) -> None:
    """Add index_runs.job_id to an existing store (additive) — links a run row
    back to the index_jobs row that produced it (task dab8766b). Skip if the
    table doesn't exist yet — _init_schema creates it with the column."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='index_runs'"
    ).fetchone()
    if not exists:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(index_runs)")}
    if "job_id" not in cols:
        conn.execute("ALTER TABLE index_runs ADD COLUMN job_id INTEGER")
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


def _migrate_partition_vec(conn: sqlite3.Connection, embed_dim: int) -> None:
    """Rebuild vec_docs/vec_chunks as PARTITIONED vec0 (P2a), REUSING the existing
    embeddings — no re-embed. Runs AFTER _init_schema: on a fresh store _init_schema
    already made the partitioned tables (DDL has 'partition key') so this no-ops; on
    a legacy store _init_schema's CREATE IF NOT EXISTS left the flat tables in place
    and this rebuilds them.

    Offline + fast: snapshot each old embedding to a temp table, drop the flat vec
    tables, recreate partitioned, and re-insert with source_id (partition key) +
    kind/lifecycle/status (from docs/chunks; kind COALESCEd to 'doc'). boot stays
    fail-open throughout — a partial state just yields empty recall, never a 500.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='vec_docs'"
    ).fetchone()
    if not row:
        return  # no vec_docs at all — nothing to migrate
    if "partition key" in (row["sql"] or ""):
        return  # already partitioned (fresh store or prior run)

    # BEGIN IMMEDIATE: same reasoning as _migrate_embed_dim -- a process killed
    # partway through this drop+recreate+reinsert sequence used to leave
    # vec_docs gone while vec_chunks survived at its old schema (or vice
    # versa), and the "if not row: return" guard above then treats that
    # missing table as "already migrated / nothing to do" on every later
    # boot, permanently wedging trovex_write on "no such table: vec_docs"
    # (found live — task 743ad0d3). Atomic: either the whole rebuild commits
    # or none of it does, so an interrupted run just retries cleanly.
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Snapshot old embeddings (plain temp tables survive until dropped / conn close).
        conn.execute(
            "CREATE TEMP TABLE _vd_old AS SELECT rowid AS rid, embedding AS emb FROM vec_docs"
        )
        has_chunks = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vec_chunks'"
        ).fetchone()
        if has_chunks:
            conn.execute(
                "CREATE TEMP TABLE _vc_old AS SELECT rowid AS rid, embedding AS emb FROM vec_chunks"
            )
        conn.execute("DROP TABLE vec_docs")
        conn.execute("DROP TABLE IF EXISTS vec_chunks")
        # Recreate partitioned (keep in sync with _init_schema's vec0 DDL).
        # Two conn.execute() calls, NOT executescript(): executescript() implicitly
        # COMMITs any pending transaction before running the script (Python sqlite3
        # legacy behavior), which would commit the DROPs above before either CREATE
        # runs -- silently breaking the atomicity this BEGIN IMMEDIATE exists for.
        conn.execute(
            f"""CREATE VIRTUAL TABLE vec_docs USING vec0(
                source_id TEXT partition key,
                embedding float[{embed_dim}] distance_metric=cosine,
                kind TEXT, lifecycle TEXT, status TEXT
            )"""
        )
        conn.execute(
            f"""CREATE VIRTUAL TABLE vec_chunks USING vec0(
                source_id TEXT partition key,
                embedding float[{embed_dim}] distance_metric=cosine,
                kind TEXT, lifecycle TEXT, status TEXT
            )"""
        )
        # Re-insert docs (JOIN docs for partition + metadata; orphan embeddings dropped).
        for r in conn.execute(
            """SELECT o.rid, o.emb, d.source_id, COALESCE(d.kind, 'doc') AS kind,
                      d.lifecycle, d.status
               FROM _vd_old o JOIN docs d ON d.id = o.rid"""
        ).fetchall():
            conn.execute(
                "INSERT INTO vec_docs(rowid, source_id, embedding, kind, lifecycle, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (r["rid"], r["source_id"], r["emb"], r["kind"], r["lifecycle"], r["status"]),
            )
        if has_chunks:
            for r in conn.execute(
                """SELECT o.rid, o.emb, d.source_id, COALESCE(d.kind, 'doc') AS kind,
                          d.lifecycle, d.status
                   FROM _vc_old o JOIN chunks c ON c.id = o.rid JOIN docs d ON d.id = c.doc_id"""
            ).fetchall():
                conn.execute(
                    "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (r["rid"], r["source_id"], r["emb"], r["kind"], r["lifecycle"], r["status"]),
                )
            conn.execute("DROP TABLE _vc_old")
        conn.execute("DROP TABLE _vd_old")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _migrate_add_vec_embed_model(conn: sqlite3.Connection, embed_dim: int, embed_model: str) -> None:
    """Add an `embed_model` vec0 metadata column to vec_docs/vec_chunks on an
    existing (already-partitioned) store — task 6851d755. Same rebuild shape
    as _migrate_partition_vec (vec0 has no ALTER TABLE ADD COLUMN; a schema
    change means drop + recreate + reinsert), run AFTER it so it only ever
    sees the partitioned DDL. Every existing row is stamped with the store's
    CURRENT `embed_model` — accurate for a store that has never swapped
    models (the overwhelming common case this one-time migration handles); a
    deliberate model swap afterwards is the SEPARATE rebuild_vec_shadow path
    (never this migration), which re-embeds and stamps the new model for real.

    Runs unconditionally at every open_db (like _migrate_partition_vec) but
    no-ops instantly once the column exists — PRAGMA table_info is cheap."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='vec_docs'"
    ).fetchone()
    if not row:
        return  # no vec_docs at all — nothing to migrate, _init_schema creates it fresh
    cols = {r[1] for r in conn.execute("PRAGMA table_info(vec_docs)")}
    if "embed_model" in cols:
        return  # already migrated

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "CREATE TEMP TABLE _vd_old2 AS "
            "SELECT rowid AS rid, source_id, embedding AS emb, kind, lifecycle, status FROM vec_docs"
        )
        has_chunks = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vec_chunks'"
        ).fetchone()
        if has_chunks:
            conn.execute(
                "CREATE TEMP TABLE _vc_old2 AS "
                "SELECT rowid AS rid, source_id, embedding AS emb, kind, lifecycle, status FROM vec_chunks"
            )
        conn.execute("DROP TABLE vec_docs")
        conn.execute("DROP TABLE IF EXISTS vec_chunks")
        conn.execute(
            f"""CREATE VIRTUAL TABLE vec_docs USING vec0(
                source_id TEXT partition key,
                embedding float[{embed_dim}] distance_metric=cosine,
                kind TEXT, lifecycle TEXT, status TEXT, embed_model TEXT
            )"""
        )
        conn.execute(
            f"""CREATE VIRTUAL TABLE vec_chunks USING vec0(
                source_id TEXT partition key,
                embedding float[{embed_dim}] distance_metric=cosine,
                kind TEXT, lifecycle TEXT, status TEXT, embed_model TEXT
            )"""
        )
        for r in conn.execute("SELECT * FROM _vd_old2").fetchall():
            conn.execute(
                "INSERT INTO vec_docs(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (r["rid"], r["source_id"], r["emb"], r["kind"], r["lifecycle"], r["status"], embed_model),
            )
        conn.execute("DROP TABLE _vd_old2")
        if has_chunks:
            for r in conn.execute("SELECT * FROM _vc_old2").fetchall():
                conn.execute(
                    "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (r["rid"], r["source_id"], r["emb"], r["kind"], r["lifecycle"], r["status"], embed_model),
                )
            conn.execute("DROP TABLE _vc_old2")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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
            -- Retention/importance (P3): importance blends status + pinned +
            -- access-frequency into the flagship ranking so an old-but-critical
            -- doc outranks recent trivia; pinned marks a doc exempt from TTL
            -- eviction (records are exempt by kind).
            importance REAL NOT NULL DEFAULT 0,
            pinned INTEGER NOT NULL DEFAULT 0,
            -- When lifecycle last changed (epoch secs), so the TTL sweep can
            -- measure time-IN-STATE for the grace windows. 0 = never transitioned.
            lifecycle_changed_at REAL NOT NULL DEFAULT 0,
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
            added INTEGER, updated INTEGER, unchanged INTEGER, removed INTEGER,
            docs_changed INTEGER NOT NULL DEFAULT 0,
            docs_total INTEGER NOT NULL DEFAULT 0,
            wall_ms REAL NOT NULL DEFAULT 0,
            phase_ms TEXT NOT NULL DEFAULT '{{}}',
            embed_cache_hits INTEGER NOT NULL DEFAULT 0,
            embed_cache_misses INTEGER NOT NULL DEFAULT 0,
            job_id INTEGER
        );

        -- The reindex op-log (task dab8766b): every /api/reindex call and every
        -- fs-watch burst enqueues a row here instead of running inline — a single
        -- applier thread (index_jobs.py) drains it, so two callers hitting the
        -- same source while a run is in flight coalesce onto one row (queued) or
        -- flag the in-flight one to rerun (processing) instead of piling up a
        -- second concurrent indexer.reindex() call or a bare rejection.
        CREATE TABLE IF NOT EXISTS index_jobs (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL,           -- 'scan_source' | 'paths' | 'rebuild'
            -- Coalescing key: a source id, or NULL for "every configured source"
            -- (scan_source/rebuild with no explicit source). Two rows with the
            -- same (kind, source_key) never both sit 'queued' at once.
            source_key TEXT,
            payload TEXT NOT NULL DEFAULT '{{}}',   -- json: {{"paths": [...], "full": bool}}
            seq INTEGER NOT NULL,
            state TEXT NOT NULL DEFAULT 'queued',   -- queued|processing|succeeded|failed
            -- Set instead of inserting a new row when a matching request arrives
            -- while this job is already 'processing'; rerun_payload carries what
            -- the rerun should use (paths already unioned in), consumed and
            -- cleared by the applier the moment it re-claims this same row.
            rerun_after INTEGER NOT NULL DEFAULT 0,
            rerun_payload TEXT,
            enqueued_at REAL NOT NULL,
            started_at REAL,
            finished_at REAL,
            error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_index_jobs_state_seq ON index_jobs(state, seq);
        CREATE INDEX IF NOT EXISTS idx_index_jobs_coalesce
            ON index_jobs(kind, source_key, state);

        -- Cross-doc/cross-run embedding cache (task cbb8e8fb): identical text
        -- (a rename, a duplicate paragraph, an unchanged doc re-embedded by a
        -- full=true rebuild) reuses its vector instead of paying the ONNX model
        -- again. Keyed by the exact embedded text's hash (not docs.content_hash
        -- — that excludes the title prefix _embed_text adds), the model id (a
        -- model swap must never serve another model's vectors), and the chunker
        -- version (chunk_code's boundaries changing invalidates old chunk-text
        -- hashes' cached vectors). embedding is the sqlite-vec serialized blob,
        -- ready to write straight into vec_docs/vec_chunks on a hit.
        CREATE TABLE IF NOT EXISTS embed_cache (
            text_hash TEXT NOT NULL,
            embed_model TEXT NOT NULL,
            chunker_version TEXT NOT NULL,
            embedding BLOB NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (text_hash, embed_model, chunker_version)
        );

        -- Small store-wide key/value facts that outlive any single doc/chunk
        -- row (task 6851d755). Currently one key: 'embed_model' — the model
        -- vec_docs/vec_chunks were last (re)built under, so a same-DIM model
        -- swap (bge-small -> paraphrase-multilingual, both 384-dim — the dim
        -- comparison alone would miss it) is still detectable at startup.
        CREATE TABLE IF NOT EXISTS store_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
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
            -- task b47301eb: the free relevance label. Set by
            -- usage.mark_result_used when the SAME session reads this served
            -- path back (trovex_read(doc_id=...)) within the labeling window —
            -- the fleet's own traffic tells us which served result was actually
            -- relevant, no hand-written cases.jsonl needed. 0 stays the default
            -- for served-but-never-read rows (not "irrelevant", just unlabelled).
            used INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (query_id, rank)
        );
        CREATE INDEX IF NOT EXISTS idx_mqr_path ON mcp_query_results(path);
        CREATE INDEX IF NOT EXISTS idx_mqr_query ON mcp_query_results(query_id);
        CREATE INDEX IF NOT EXISTS idx_mqr_used ON mcp_query_results(used) WHERE used = 1;

        -- Partitioned vector index (P2a). source_id is a vec0 PARTITION KEY: a KNN
        -- constrained to `source_id = ?` scans ONLY that source's shard, so k stays
        -- tiny and bounded per source — the 4096 KNN ceiling is gone structurally
        -- (no more clamp/widen). kind/lifecycle/status are METADATA columns, usable
        -- in the KNN WHERE to pre-filter WITHIN the partition (never NULL — vec0
        -- rejects NULL metadata; kind is COALESCEd to 'doc' at the write boundary).
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_docs USING vec0(
            source_id TEXT partition key,
            embedding float[{embed_dim}] distance_metric=cosine,
            kind TEXT,
            lifecycle TEXT,
            status TEXT,
            embed_model TEXT
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
            content_hash TEXT NOT NULL DEFAULT '',
            -- Chunker identity (task 6851d755): chunking.CHUNKER_VERSION /
            -- chunking_code.CHUNKER_VERSION at the time this chunk was cut. A
            -- version bump makes sync_doc_chunks treat every one of a re-synced
            -- doc's chunks as non-reusable regardless of content_hash — a stale
            -- chunker's boundaries are never silently trusted just because the
            -- text happened not to change. Legacy rows have '' → non-reusable.
            chunker_version TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(doc_id, content_hash);
        CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
        -- Same partitioning as vec_docs; chunk metadata is DENORMALISED from its
        -- parent doc (a chunk inherits source_id/kind/lifecycle/status), kept in
        -- sync by vec_sync_meta on any parent-doc status/lifecycle change.
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
            source_id TEXT partition key,
            embedding float[{embed_dim}] distance_metric=cosine,
            kind TEXT,
            lifecycle TEXT,
            status TEXT,
            embed_model TEXT
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
