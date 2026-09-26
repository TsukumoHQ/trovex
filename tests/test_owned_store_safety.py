"""The trovex-owned store must survive indexing — three live-found bugs.

1. A configured source claiming the RESERVED id ("trovex") made the indexer's
   vanished-file purge destroy every owned doc (receipts, verdicts, captures)
   on each reindex. load_sources must drop it; reindex must skip it even when
   handed one explicitly.
2. The embed-dim migration wiped vec_docs but left vec_chunks at the old dim —
   every store.put then crashed with "Expected N dimensions".
3. POST /api/reindex passed an explicit root, silently forcing the
   single-source fallback and never indexing the configured sources.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient

from trovex import db
from trovex import state as state_mod
from trovex.config import RESERVED_SOURCE_ID, Settings, Source
from trovex.db import open_db
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.server import build_app
from trovex.state import AppState
from trovex.store import SqliteStore

DIM = 384


class BagEmbedder:
    """Stable hashing bag-of-words embedder (same shape as test_server's)."""

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


def _settings(tmp_path, **kw):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",  # dim 384, matches BagEmbedder
        sources_config_path=tmp_path / "sources.yaml",
        **kw,
    )


def _write_sources(settings, entries):
    settings.sources_config_path.write_text(yaml.safe_dump({"sources": entries}))


# ---------------------------------------------------------------------------
# 1. reserved source id
# ---------------------------------------------------------------------------


def test_load_sources_drops_reserved_id_keeps_rest(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    settings = _settings(tmp_path)
    _write_sources(
        settings,
        [
            {"id": RESERVED_SOURCE_ID, "label": "collides", "root": str(docs)},
            {"id": "notes", "label": "Notes", "root": str(docs)},
        ],
    )
    ids = [s.id for s in settings.load_sources()]
    assert RESERVED_SOURCE_ID not in ids
    assert ids == ["notes"]


def test_load_sources_all_reserved_falls_back_to_single_source(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    settings = _settings(tmp_path)
    _write_sources(settings, [{"id": RESERVED_SOURCE_ID, "label": "x", "root": str(docs)}])
    sources = settings.load_sources()
    # The reserved entry is dropped; legacy single-source fallback applies —
    # and it never uses the reserved id either.
    assert [s.id for s in sources] == ["code"]


def test_reindex_never_purges_owned_docs_even_with_reserved_source(tmp_path):
    """Defense in depth: a reserved-id Source handed straight to reindex()
    (bypassing load_sources) must be skipped, not scanned-and-purged."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# a\n\nfile-backed doc")
    settings = _settings(tmp_path)
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)
    ext_id = store.put("# owned\n\na receipt-like owned doc", kind="record")

    indexer = Indexer(settings, embedder=embedder)
    indexer.reindex(sources=[Source(id=RESERVED_SOURCE_ID, label="evil", root=docs)])

    row = store.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext_id,)).fetchone()
    assert row is not None, "owned doc was purged by a reserved-id source scan"


# ---------------------------------------------------------------------------
# 2. embed-dim migration must wipe vec_chunks too
# ---------------------------------------------------------------------------


def test_dim_migration_recreates_chunk_tables_at_new_dim_on_empty_store(tmp_path):
    """An EMPTY store still gets the fast inline wipe (task 6851d755's
    fallback) — nothing to lose, no write-stall risk to avoid."""
    path = tmp_path / "trovex.db"
    conn = open_db(path, embed_dim=8)
    conn.close()

    conn = open_db(path, embed_dim=4)
    for table in ("vec_docs", "vec_chunks"):
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = ?", (table,)
        ).fetchone()["sql"]
        assert "float[4]" in ddl, f"{table} still at the old dim: {ddl}"
    import sqlite_vec

    # A new-dim insert must not raise (the live failure mode).
    conn.execute(
        "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
        "VALUES (1, 's', ?, 'doc', 'active', 'canonical', 'test')",
        (sqlite_vec.serialize_float32([0.0] * 4),),
    )
    conn.close()


def test_dim_migration_on_non_empty_store_leaves_old_tables_and_flags_rebuild(tmp_path):
    """task 6851d755: a NON-EMPTY store never takes the inline wipe — the old
    (still internally consistent) vec tables keep serving reads/writes
    unchanged, and db.rebuild_vec_needed() is the signal the caller (server
    startup) uses to enqueue the real rebuild_vec_shadow swap instead."""
    import sqlite_vec

    path = tmp_path / "trovex.db"
    conn = open_db(path, embed_dim=8)
    conn.execute(
        "INSERT INTO docs (source_id, path, absolute_path, content_hash, size_bytes, "
        "tokens_est, mtime, first_indexed, last_indexed) "
        "VALUES ('s', 'p', '', 'h', 1, 1, 0, 0, 0)"
    )
    doc_id = conn.execute("SELECT id FROM docs").fetchone()["id"]
    conn.execute(
        "INSERT INTO chunks (doc_id, chunk_index, heading_path, content, tokens_est) "
        "VALUES (?, 0, 't', 'text', 1)",
        (doc_id,),
    )
    chunk_id = conn.execute("SELECT id FROM chunks").fetchone()["id"]
    conn.execute(
        "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
        "VALUES (?, 's', ?, 'doc', 'active', 'canonical', 'test')",
        (chunk_id, sqlite_vec.serialize_float32([0.0] * 8)),
    )
    conn.commit()
    conn.close()

    conn = open_db(path, embed_dim=4)  # mismatch, but the store is non-empty
    for table in ("vec_docs", "vec_chunks"):
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = ?", (table,)
        ).fetchone()["sql"]
        assert "float[8]" in ddl, f"{table} was wiped on a non-empty store: {ddl}"
    assert conn.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"] == 1  # untouched
    assert conn.execute(
        "SELECT COUNT(*) c FROM vec_chunks WHERE rowid = ?", (chunk_id,)
    ).fetchone()["c"] == 1  # old embedding still readable at the OLD dim

    assert db.rebuild_vec_needed(conn, embed_dim=4, embed_model="some-model") is True
    conn.close()


# ---------------------------------------------------------------------------
# 3. /api/reindex must index the CONFIGURED sources
# ---------------------------------------------------------------------------


@pytest.fixture
def multi_source_client(tmp_path):
    alpha = tmp_path / "alpha"
    beta = tmp_path / "beta"
    alpha.mkdir()
    beta.mkdir()
    (alpha / "one.md").write_text("# one\n\nalpha doc")
    (beta / "two.md").write_text("# two\n\nbeta doc")
    settings = _settings(tmp_path, write_token="test-token")
    _write_sources(
        settings,
        [
            {"id": "alpha", "label": "Alpha", "root": str(alpha)},
            {"id": "beta", "label": "Beta", "root": str(beta)},
        ],
    )
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)
    state_mod._state = AppState(
        settings=settings,
        embedder=embedder,
        searcher=Searcher(settings, embedder=embedder),
        indexer=Indexer(settings, embedder=embedder),
        store=store,
    )
    try:
        yield TestClient(build_app()), store
    finally:
        state_mod.reset_state()


def test_api_reindex_indexes_every_configured_source(multi_source_client):
    """task dab8766b: /api/reindex now enqueues (202) instead of indexing
    inline — drive the applier synchronously to observe the actual result."""
    client, store = multi_source_client
    resp = client.post("/api/reindex", headers={"X-TROVEX-Write-Token": "test-token"})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    assert state_mod.get_state().applier.run_one() is True

    status = client.get(f"/api/reindex/{job_id}")
    assert status.json()["state"] == "succeeded"
    by_source_id = {
        r["source_id"] for r in store.db.execute("SELECT DISTINCT source_id FROM docs").fetchall()
    }
    assert by_source_id == {"alpha", "beta"}, (
        "api_reindex fell back to the single-source root instead of sources.yaml"
    )
