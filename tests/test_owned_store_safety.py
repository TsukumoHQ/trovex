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


def test_dim_migration_recreates_chunk_tables_at_new_dim(tmp_path):
    path = tmp_path / "trovex.db"
    conn = open_db(path, embed_dim=8)
    # Seed a chunk + its embedding at the old dim.
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
    import sqlite_vec

    chunk_id = conn.execute("SELECT id FROM chunks").fetchone()["id"]
    conn.execute(
        "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status) "
        "VALUES (?, 's', ?, 'doc', 'active', 'canonical')",
        (chunk_id, sqlite_vec.serialize_float32([0.0] * 8)),
    )
    conn.commit()
    conn.close()

    conn = open_db(path, embed_dim=4)
    for table in ("vec_docs", "vec_chunks"):
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = ?", (table,)
        ).fetchone()["sql"]
        assert "float[4]" in ddl, f"{table} still at the old dim: {ddl}"
    assert conn.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"] == 0
    # A new-dim insert must not raise (the live failure mode).
    conn.execute(
        "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status) "
        "VALUES (1, 's', ?, 'doc', 'active', 'canonical')",
        (sqlite_vec.serialize_float32([0.0] * 4),),
    )
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
    client, _store = multi_source_client
    resp = client.post("/api/reindex", headers={"X-TROVEX-Write-Token": "test-token"})
    assert resp.status_code == 200
    stats = resp.json()
    by_source = {s["id"]: s for s in stats["by_source"]}
    assert set(by_source) == {"alpha", "beta"}, (
        "api_reindex fell back to the single-source root instead of sources.yaml"
    )
    assert by_source["alpha"]["added"] == 1
    assert by_source["beta"]["added"] == 1
