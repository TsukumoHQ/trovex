"""Content-addressed (Merkle) incremental re-embedding on the write path.

Steal #2: a doc rewrite must re-embed only what CHANGED — an unchanged chunk
keeps its embedding (its row id survives), a changed/new chunk is re-embedded (a
fresh id), a removed section's chunk is dropped, and a byte-identical rewrite is
a no-op (no version snapshot, no re-embed). Correctness rail: a genuinely
changed chunk is NEVER served a stale embedding.

Hermetic: deterministic BagEmbedder, no model download / network.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex.config import Settings
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
def store(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    return SqliteStore(settings, embedder=BagEmbedder())


def _doc_id(store, ext):
    return store.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext,)).fetchone()["id"]


def _chunks(store, ext):
    """[(id, heading_path, content_hash)] for a doc, ordered by chunk_index."""
    did = _doc_id(store, ext)
    return [
        (r["id"], r["heading_path"], r["content_hash"])
        for r in store.db.execute(
            "SELECT id, heading_path, content_hash FROM chunks WHERE doc_id = ? ORDER BY chunk_index",
            (did,),
        )
    ]


def _vec_count(store):
    return store.db.execute("SELECT COUNT(*) AS c FROM vec_chunks").fetchone()["c"]


_A = "## Reverse proxy\n\nterminate tls at nginx and forward to the local port"
_B = "## Backups\n\narchive the data directory and restore it on a new host"
_TWO = f"# Guide\n\n{_A}\n\n{_B}\n"


def test_owned_doc_gets_a_content_hash(store):
    ext = store.put(_TWO, kind="record")
    row = store.db.execute("SELECT content_hash FROM docs WHERE ext_id = ?", (ext,)).fetchone()
    assert row["content_hash"] and len(row["content_hash"]) == 64


def test_identical_reput_preserves_all_chunk_ids_and_skips_snapshot(store):
    ext = store.put(_TWO, kind="record")
    before = _chunks(store, ext)
    assert len(before) == 2
    store.put(_TWO, ext_id=ext, kind="record")  # byte-identical rewrite
    after = _chunks(store, ext)
    assert [c[0] for c in after] == [c[0] for c in before]  # every embedding reused
    # a no-op write must NOT pollute version history
    assert store.list_versions(ext) == []


def test_edit_one_section_reembeds_only_that_chunk(store):
    ext = store.put(_TWO, kind="record")
    before = {hp: cid for cid, hp, _ in _chunks(store, ext)}
    edited = _TWO.replace("archive the data directory", "snapshot the whole database nightly")
    store.put(edited, ext_id=ext, kind="record")
    after = {hp: cid for cid, hp, _ in _chunks(store, ext)}
    # the untouched section keeps its id (embedding reused)...
    assert after["Guide > Reverse proxy"] == before["Guide > Reverse proxy"]
    # ...the edited section is a fresh chunk (re-embedded)
    assert after["Guide > Backups"] != before["Guide > Backups"]
    # a real content change DOES snapshot the prior body (non-clobber intact)
    assert len(store.list_versions(ext)) == 1


def test_changed_chunk_is_searchable_no_stale_embedding(store):
    ext = store.put(_TWO, kind="record")
    store.put(
        _TWO.replace("archive the data directory", "snapshot the whole database nightly"),
        ext_id=ext,
        kind="record",
    )
    hits = store.search_chunks("snapshot the whole database nightly", limit=1)
    assert hits and "snapshot the whole database nightly" in hits[0]["content"]


def test_reorder_reuses_both_embeddings(store):
    """Content-addressed: swapping section order reuses BOTH embeddings (match is
    by hash, not position) — only the chunk_index is refreshed."""
    ext = store.put(_TWO, kind="record")
    before = {hp: cid for cid, hp, _ in _chunks(store, ext)}
    swapped = f"# Guide\n\n{_B}\n\n{_A}\n"
    store.put(swapped, ext_id=ext, kind="record")
    after = {hp: cid for cid, hp, _ in _chunks(store, ext)}
    assert after["Guide > Reverse proxy"] == before["Guide > Reverse proxy"]
    assert after["Guide > Backups"] == before["Guide > Backups"]


def test_removed_section_drops_its_chunk(store):
    ext = store.put(_TWO, kind="record")
    assert _vec_count(store) == 2
    store.put(f"# Guide\n\n{_A}\n", ext_id=ext, kind="record")  # drop Backups
    chunks = _chunks(store, ext)
    assert len(chunks) == 1
    assert chunks[0][1] == "Guide > Reverse proxy"
    assert _vec_count(store) == 1  # the orphan embedding is gone, not leaked


def test_added_section_adds_one_chunk_keeps_original(store):
    ext = store.put(f"# Guide\n\n{_A}\n", kind="record")
    before = _chunks(store, ext)
    assert len(before) == 1
    store.put(_TWO, ext_id=ext, kind="record")  # add Backups
    after = _chunks(store, ext)
    assert len(after) == 2
    # original section's chunk id survives
    assert before[0][0] in {c[0] for c in after}


def test_content_unchanged_still_updates_tags(store):
    ext = store.put(_TWO, kind="record", tags=["owner/alpha"])
    store.put(_TWO, ext_id=ext, kind="record", tags=["owner/beta"])  # same content, new tags
    tags = {
        r["tag"]
        for r in store.db.execute(
            "SELECT tag FROM doc_tags WHERE doc_id = ?", (_doc_id(store, ext),)
        )
    }
    assert "owner/beta" in tags and "owner/alpha" not in tags
    assert store.list_versions(ext) == []  # still a no-op for the body


def test_reused_chunks_carry_a_hash(store):
    ext = store.put(_TWO, kind="record")
    assert all(h and len(h) == 64 for _, _, h in _chunks(store, ext))
