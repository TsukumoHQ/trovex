"""chunker_version stamping + reuse gating (task 6851d755).

sync_doc_chunks's Merkle content-hash reuse must NOT trust a chunk whose
content_hash still matches if it was cut by an OLDER chunker — a boundary or
breadcrumb change in chunking.py/chunking_code.py must re-derive every chunk
of a re-synced doc, not silently keep stale structure. Hermetic: direct
db-level calls, no embedder/model needed (sync_doc_chunks only touches
chunks/chunks_fts/vec_chunks rows, embedding happens separately)."""

from __future__ import annotations

from trovex import db
from trovex.chunking import chunk_markdown


def _open(tmp_path):
    return db.open_db(tmp_path / "trovex.db", 8, "test-model")


def _mkdoc(conn, ext_id: str = "d1") -> int:
    conn.execute(
        "INSERT INTO docs (source_id, path, absolute_path, content_hash, size_bytes, "
        "tokens_est, mtime, first_indexed, last_indexed, title, ext_id) "
        "VALUES ('trovex', ?, '', 'h', 1, 1, 0, 0, 0, 'T', ?)",
        (ext_id, ext_id),
    )
    return conn.execute("SELECT id FROM docs WHERE ext_id = ?", (ext_id,)).fetchone()["id"]


CONTENT = "# H\n\nbody text here, stable across both chunker versions"


def test_same_chunker_version_reuses_unchanged_chunks(tmp_path):
    conn = _open(tmp_path)
    doc_id = _mkdoc(conn)

    to_embed = db.sync_doc_chunks(conn, doc_id, CONTENT, "T", chunk_markdown, chunker_version="1")
    conn.commit()
    assert to_embed  # first sync always embeds
    ids_v1 = {cid for cid, _ in to_embed}

    # Re-sync: same content, same version — nothing new to embed, same rows.
    to_embed2 = db.sync_doc_chunks(conn, doc_id, CONTENT, "T", chunk_markdown, chunker_version="1")
    conn.commit()
    assert to_embed2 == []
    ids_after = {r["id"] for r in conn.execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,))}
    assert ids_after == ids_v1


def test_chunker_version_bump_re_derives_every_chunk(tmp_path):
    conn = _open(tmp_path)
    doc_id = _mkdoc(conn)

    to_embed_v1 = db.sync_doc_chunks(conn, doc_id, CONTENT, "T", chunk_markdown, chunker_version="1")
    conn.commit()
    ids_v1 = {cid for cid, _ in to_embed_v1}
    assert ids_v1

    # SAME content — content_hash would still match — but chunker_version
    # bumped: every existing chunk must be treated as non-reusable.
    to_embed_v2 = db.sync_doc_chunks(conn, doc_id, CONTENT, "T", chunk_markdown, chunker_version="2")
    conn.commit()
    assert to_embed_v2, "a chunker_version bump must re-derive (re-embed), not skip"
    ids_v2 = {cid for cid, _ in to_embed_v2}
    assert ids_v2.isdisjoint(ids_v1), "old rows must be deleted, not reused, on a version bump"

    stamped = {
        r["chunker_version"]
        for r in conn.execute("SELECT chunker_version FROM chunks WHERE doc_id = ?", (doc_id,))
    }
    assert stamped == {"2"}


def test_legacy_chunks_with_blank_version_are_non_reusable(tmp_path):
    """A pre-migration chunk (chunker_version='' from the additive ALTER TABLE
    default) must be treated exactly like a version mismatch — re-derived on
    the doc's next sync, never silently trusted."""
    conn = _open(tmp_path)
    doc_id = _mkdoc(conn)
    conn.execute(
        "INSERT INTO chunks (doc_id, chunk_index, heading_path, content, tokens_est, "
        "content_hash, chunker_version) VALUES (?, 0, 'H', 'body text here, stable across "
        "both chunker versions', 5, ?, '')",
        (doc_id, __import__("hashlib").sha256(b"T\n\nbody text here, stable across both chunker versions").hexdigest()),
    )
    conn.commit()

    to_embed = db.sync_doc_chunks(conn, doc_id, CONTENT, "T", chunk_markdown, chunker_version="1")
    conn.commit()
    assert to_embed  # the legacy '' row is never in the reusable pool


def test_store_insert_chunks_re_embeds_on_chunker_version_bump(tmp_path, monkeypatch):
    """Integration-level pin through the real SqliteStore._insert_chunks path
    (store.py's thin wrapper over sync_doc_chunks, stamping the live
    trovex.chunking.CHUNKER_VERSION): bumping it between two calls on the SAME
    content must re-embed every chunk, not silently keep the old rows.

    Exercised at _insert_chunks directly rather than through the public put()
    — put() has its own, DELIBERATE content_hash+title fast path that skips
    re-chunking entirely for a byte-identical rewrite (the "lazy via the
    applier" design: a version bump alone never forces an otherwise-untouched
    doc to redo work; it takes effect the next time that doc is genuinely
    touched, exactly like content_hash gating already works for re-embeds)."""
    import numpy as np

    from trovex import store as store_mod
    from trovex.config import Settings
    from trovex.store import SqliteStore

    class BagEmbedder:
        name = "bag"
        dim = 384

        def embed(self, texts):
            for _ in texts:
                yield np.zeros(self.dim, dtype=np.float32)

    settings = Settings(
        data_dir=tmp_path, embed_model="bag", sources_config_path=tmp_path / "none.yaml"
    )
    store = SqliteStore(settings, embedder=BagEmbedder())
    body = "# Deploy\n\nkubernetes rollback runbook, unchanged text"
    ext_id = store.put(body, ext_id="fixed-id")
    doc_id = store.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext_id,)).fetchone()["id"]
    ids_v1 = {r["id"] for r in store.db.execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,))}
    assert ids_v1

    monkeypatch.setattr(store_mod, "CHUNKER_VERSION", "bumped-version")
    store._insert_chunks(doc_id, body, "Deploy")  # same content, forced version bump
    store.db.commit()
    ids_v2 = {r["id"] for r in store.db.execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,))}
    assert ids_v2.isdisjoint(ids_v1)
    stamped = {
        r["chunker_version"]
        for r in store.db.execute("SELECT chunker_version FROM chunks WHERE doc_id = ?", (doc_id,))
    }
    assert stamped == {"bumped-version"}
