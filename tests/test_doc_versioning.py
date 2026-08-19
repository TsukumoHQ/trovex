"""Versioned / non-clobber doc writes — the fix for the vague2 silent-loss class.

An overwrite of an owned doc must snapshot the prior body so a bad save is
recoverable; a restore must roll back CONTENT without wiping the doc's identity
(kind + tags); history is bounded by a cap and exposed on read.

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
from trovex.config import Settings
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
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


@pytest.fixture
def store(settings):
    return SqliteStore(settings, embedder=BagEmbedder())


def test_overwrite_snapshots_prior_body(store):
    """The vague2 case: a save over an existing doc_id keeps the old body."""
    ext = store.put("# Backlog\n\nv1: alpha beta gamma", kind="record")
    store.put("# Backlog\n\nv2: clobbered", ext_id=ext, kind="record")

    versions = store.list_versions(ext)
    assert len(versions) == 1  # the prior (v1) body was snapshotted
    old = store.get_version(ext, versions[0]["id"])
    assert "v1: alpha beta gamma" in old
    # current reader API unchanged — returns the latest body
    assert "v2: clobbered" in store.get(ext).content


def test_overwrite_then_recover(store):
    ext = store.put("# Doc\n\noriginal content", kind="record", tags=["owner/alpha"])
    store.put("# Doc\n\nbad overwrite", ext_id=ext, kind="record", tags=["owner/alpha"])
    vid = store.list_versions(ext)[0]["id"]

    assert store.restore_version(ext, vid) is True
    assert "original content" in store.get(ext).content
    # restore snapshots the (bad) current first → it's also recoverable
    assert any("bad overwrite" in store.get_version(ext, v["id"]) for v in store.list_versions(ext))


def test_restore_preserves_kind_and_tags(store):
    """Rolling back CONTENT must not wipe the doc's identity (the bare-put bug)."""
    ext = store.put("# Rec\n\nfirst", kind="record", tags=["owner/coo", "type/report"])
    store.put("# Rec\n\nsecond", ext_id=ext, kind="record", tags=["owner/coo", "type/report"])
    vid = store.list_versions(ext)[0]["id"]

    store.restore_version(ext, vid)
    doc = store.get(ext)
    assert doc.kind == "record"
    assert "owner/coo" in doc.tags and "type/report" in doc.tags
    assert "kind/record" in doc.tags
    assert "first" in doc.content


def test_first_write_has_no_versions(store):
    ext = store.put("# New\n\nonly ever written once")
    assert store.list_versions(ext) == []


def test_version_cap_bounds_growth(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no.yaml",
        doc_version_cap=3,
    )
    store = SqliteStore(settings, embedder=BagEmbedder())
    ext = store.put("# D\n\nrev 0")
    for i in range(1, 8):
        store.put(f"# D\n\nrev {i}", ext_id=ext)
    versions = store.list_versions(ext)
    assert len(versions) == 3  # capped
    # the newest snapshots survive (rev 6 is the body just before the final rev 7)
    newest_body = store.get_version(ext, versions[0]["id"])
    assert "rev 6" in newest_body


def test_get_version_missing_returns_none(store):
    ext = store.put("# X\n\nbody")
    assert store.get_version(ext, 99999) is None
    assert store.restore_version(ext, 99999) is False


def test_put_batch_overwrite_snapshots(store):
    store.put_batch([{"content": "# B\n\nbatch v1", "ext_id": "fixed-id"}])
    store.put_batch([{"content": "# B\n\nbatch v2", "ext_id": "fixed-id"}])
    versions = store.list_versions("fixed-id")
    assert len(versions) == 1
    assert "batch v1" in store.get_version("fixed-id", versions[0]["id"])


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


def test_mcp_read_lists_and_reads_versions(wired, monkeypatch):
    monkeypatch.setenv("TROVEX_ALLOW_UNAUTH_WRITES", "1")
    ext = wired.store.put("# M\n\nmcp original", kind="record")
    wired.store.put("# M\n\nmcp changed", ext_id=ext, kind="record")

    listing = mcp_app.trovex_read(doc_id=ext, versions=True)
    assert "prior version" in listing
    assert "version_id=" in listing

    vid = wired.store.list_versions(ext)[0]["id"]
    assert "mcp original" in mcp_app.trovex_read(doc_id=ext, version_id=vid)
    # no prior versions → explicit, not empty
    solo = wired.store.put("# S\n\nsolo")
    assert "no prior versions" in mcp_app.trovex_read(doc_id=solo, versions=True)


def test_mcp_restore_rolls_back(wired):
    # writes are open in this test env (no write_token configured on the settings)
    ext = wired.store.put("# R\n\nkeep me", kind="record", tags=["owner/x"])
    wired.store.put("# R\n\noops", ext_id=ext, kind="record", tags=["owner/x"])
    vid = wired.store.list_versions(ext)[0]["id"]

    out = mcp_app.trovex_restore(doc_id=ext, version_id=vid)
    assert "restored" in out
    doc = wired.store.get(ext)
    assert "keep me" in doc.content
    assert doc.kind == "record" and "owner/x" in doc.tags

    assert "not found" in mcp_app.trovex_restore(doc_id="nope", version_id=1)


def test_http_versions_endpoint(wired):
    """The existing read-only history endpoint reflects the new snapshots."""
    ext = wired.store.put("# H\n\nhttp v1")
    wired.store.put("# H\n\nhttp v2", ext_id=ext)
    client = TestClient(build_app())
    r = client.get(f"/api/doc/{ext}/versions")
    assert r.status_code == 200
    versions = r.json()
    assert len(versions) == 1
    assert versions[0]["title"]  # snapshot carried the prior title
    # unknown doc → empty history, not an error
    assert client.get("/api/doc/does-not-exist/versions").json() == []
