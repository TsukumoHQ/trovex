"""Survive-delete tombstone — close the delete arm of the vague2 loss class.

Deleting an owned doc snapshots its body to doc_tombstones (which has NO FK to
docs, so it outlives the cascade) → the delete is recoverable. File-backed docs
(bytes still on disk) are NOT tombstoned. Recovery is exposed on the MCP + HTTP
surfaces.

Hermetic: the deterministic BagEmbedder, no model download / network.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient

from trovex import mcp_app
from trovex import state as state_mod
from trovex.config import Settings, Source
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.server import build_app
from trovex.state import AppState
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
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no.yaml",
    )


@pytest.fixture
def store(settings):
    return SqliteStore(settings, embedder=BagEmbedder())


def test_delete_tombstones_owned_doc(store):
    ext = store.put("# Backlog\n\nvague2 tickets A B C", kind="record", tags=["owner/wraith"])
    assert store.delete(ext) is True

    # doc is gone from the live store...
    assert store.get(ext) is None
    # ...but recoverable from a tombstone.
    tombs = store.list_tombstones()
    assert len(tombs) == 1
    assert tombs[0]["ext_id"] == ext
    assert tombs[0]["title"]


def test_delete_then_recover_roundtrip(store):
    ext = store.put("# Rec\n\nkeep this body", kind="record", tags=["owner/coo", "type/report"])
    store.delete(ext)

    restored = store.restore_deleted(ext_id=ext)
    assert restored == ext
    doc = store.get(ext)
    assert doc is not None
    assert "keep this body" in doc.content
    assert doc.kind == "record"
    assert "owner/coo" in doc.tags and "type/report" in doc.tags
    assert "kind/record" in doc.tags
    # the consumed tombstone is cleared
    assert store.list_tombstones() == []


def test_restore_by_tombstone_id(store):
    ext = store.put("# D\n\nbody one")
    store.delete(ext)
    tid = store.list_tombstones()[0]["id"]
    assert store.restore_deleted(tombstone_id=tid) == ext
    assert "body one" in store.get(ext).content


def test_restore_deleted_missing_returns_none(store):
    assert store.restore_deleted(ext_id="never-existed") is None
    assert store.restore_deleted(tombstone_id=99999) is None
    assert store.restore_deleted() is None  # neither arg


def test_file_backed_doc_not_tombstoned(settings):
    """A file-backed doc keeps its bytes on disk — removing it from the index is
    not data loss, so it must NOT create a tombstone."""
    store = SqliteStore(settings, embedder=BagEmbedder())
    repo = settings.data_dir / "repo"
    repo.mkdir()
    (repo / "guide.md").write_text("# Guide\n\non-disk body", encoding="utf-8")
    Indexer(settings, embedder=BagEmbedder()).reindex(
        sources=[Source(id="code", label="app", root=repo)]
    )
    row = store.db.execute("SELECT id, content FROM docs WHERE source_id='code'").fetchone()
    assert row["content"] is None  # file-backed → no in-DB body
    assert store.delete_by_id(row["id"]) is True
    assert store.list_tombstones() == []  # nothing to lose → no tombstone


def test_tombstone_cap_prunes(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no.yaml",
        doc_tombstone_cap=3,
    )
    store = SqliteStore(settings, embedder=BagEmbedder())
    for i in range(6):
        ext = store.put(f"# D{i}\n\nbody {i}")
        store.delete(ext)
    assert len(store.list_tombstones()) == 3  # capped, newest kept


# --- MCP + HTTP surfaces ---


@pytest.fixture
def wired(settings):
    store = SqliteStore(settings, embedder=BagEmbedder())
    state_mod._state = AppState(
        settings=settings,
        embedder=BagEmbedder(),
        searcher=Searcher(settings, embedder=BagEmbedder()),
        indexer=Indexer(settings, embedder=BagEmbedder()),
        store=store,
    )
    try:
        yield state_mod._state
    finally:
        state_mod.reset_state()


def test_mcp_undelete_and_deleted_resource(wired):
    ext = wired.store.put("# M\n\nmcp deleted body", kind="record", tags=["owner/x"])
    wired.store.delete(ext)

    listing = mcp_app.deleted_docs()
    assert "deleted docs" in listing
    assert ext in listing

    out = mcp_app.trovex_undelete(doc_id=ext)
    assert "undeleted" in out
    doc = wired.store.get(ext)
    assert "mcp deleted body" in doc.content and doc.kind == "record" and "owner/x" in doc.tags

    # empty state + missing id are explicit, not crashes
    assert "no recoverable tombstones" in mcp_app.deleted_docs()
    assert "no recoverable tombstone" in mcp_app.trovex_undelete(doc_id="nope")


def test_http_tombstones_and_undelete(wired):
    ext = wired.store.put("# H\n\nhttp deleted body")
    wired.store.delete(ext)
    client = TestClient(build_app())

    listed = client.get("/api/tombstones").json()
    assert any(t["ext_id"] == ext for t in listed)

    r = client.post(f"/api/doc/{ext}/undelete")
    assert r.status_code == 200 and r.json()["undeleted"] is True
    assert "http deleted body" in wired.store.get(ext).content

    # nothing to recover → 404
    assert client.post("/api/doc/does-not-exist/undelete").status_code == 404
