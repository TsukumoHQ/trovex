"""Doc curation lifecycle — active / archived / pending_delete.

Steal #5: a reversible cleanup path instead of hard-delete. Retrieval shows the
active canon only; archiving hides a doc without removing it (reachable
explicitly); pending_delete is a grace window, never surfaced. Fully reversible.

Hermetic: deterministic BagEmbedder, no model download / network.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex import mcp_app
from trovex import state as state_mod
from trovex.config import Settings
from trovex.indexer import Indexer
from trovex.search import Searcher
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


_DOC = (
    "# Deploy guide\n\n## Reverse proxy\n\nterminate tls at nginx and forward to the local port\n"
)


def _lifecycle(store, ext):
    return store.db.execute("SELECT lifecycle FROM docs WHERE ext_id = ?", (ext,)).fetchone()[
        "lifecycle"
    ]


# --- store model ------------------------------------------------------------


def test_new_doc_is_active(store):
    ext = store.put(_DOC, kind="record")
    assert _lifecycle(store, ext) == "active"


def test_set_lifecycle_is_reversible(store):
    ext = store.put(_DOC, kind="record")
    assert store.set_lifecycle(ext, "archived") is True
    assert _lifecycle(store, ext) == "archived"
    assert store.set_lifecycle(ext, "active") is True
    assert _lifecycle(store, ext) == "active"


def test_set_lifecycle_unknown_state_raises(store):
    ext = store.put(_DOC, kind="record")
    with pytest.raises(ValueError):
        store.set_lifecycle(ext, "banana")


def test_set_lifecycle_missing_doc_returns_false(store):
    assert store.set_lifecycle("no-such-ext", "archived") is False


# --- chunk retrieval filter -------------------------------------------------


def test_archived_hidden_by_default_reachable_explicitly(store):
    ext = store.put(_DOC, kind="record")
    assert store.search_chunks("reverse proxy tls", limit=5)  # active → found
    store.set_lifecycle(ext, "archived")
    assert store.search_chunks("reverse proxy tls", limit=5) == []  # hidden
    hits = store.search_chunks("reverse proxy tls", limit=5, include_archived=True)
    assert hits and hits[0]["ext_id"] == ext  # reachable explicitly


def test_pending_delete_never_surfaced(store):
    ext = store.put(_DOC, kind="record")
    store.set_lifecycle(ext, "pending_delete")
    assert store.search_chunks("reverse proxy tls", limit=5) == []
    # even with include_archived, pending_delete stays hidden
    assert store.search_chunks("reverse proxy tls", limit=5, include_archived=True) == []


# --- doc-router filter ------------------------------------------------------


def test_doc_router_respects_lifecycle(store, settings):
    ext = store.put(_DOC, kind="record")
    searcher = Searcher(settings, embedder=BagEmbedder())
    assert searcher.search("reverse proxy tls", limit=5)  # active
    store.set_lifecycle(ext, "archived")
    assert searcher.search("reverse proxy tls", limit=5) == []  # hidden by default
    assert searcher.search("reverse proxy tls", limit=5, include_archived=True)  # explicit


# --- MCP tool ---------------------------------------------------------------


@pytest.fixture
def wired(settings, monkeypatch):
    monkeypatch.setenv("TROVEX_ALLOW_UNAUTH_WRITES", "1")
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


def test_trovex_archive_tool_hides_then_restores(wired):
    ext = wired.store.put(_DOC, kind="record")
    assert "archived" in mcp_app.trovex_archive(doc_id=ext)
    assert mcp_app.trovex_search(q="reverse proxy tls") == "(no results)"
    # reachable explicitly
    assert ext in mcp_app.trovex_search(q="reverse proxy tls", include_archived=True)
    # reversible
    assert "restored" in mcp_app.trovex_archive(doc_id=ext, restore=True)
    assert ext in mcp_app.trovex_search(q="reverse proxy tls")


def test_trovex_archive_missing_doc(wired):
    assert mcp_app.trovex_archive(doc_id="no-such") == "(not found)"


def test_trovex_archive_requires_write_auth(wired, monkeypatch):
    ext = wired.store.put(_DOC, kind="record")
    monkeypatch.delenv("TROVEX_ALLOW_UNAUTH_WRITES", raising=False)
    monkeypatch.setattr(mcp_app, "_authorized", lambda: False)
    out = mcp_app.trovex_archive(doc_id=ext)
    assert out == mcp_app._DENY
    assert _lifecycle(wired.store, ext) == "active"  # unchanged
