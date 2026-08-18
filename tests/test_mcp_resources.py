"""MCP resources — the doc/topic catalog exposed at connect time (CCAR G2).

trovex exposed only tools; an agent had to call a search tool just to see what
exists. These resources publish the catalog read-only and additively — the
tools stay unchanged. Hermetic: bag embedder, no model download.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex import mcp_app
from trovex import state as state_mod
from trovex.config import Settings, Source
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.state import AppState
from trovex.store import SqliteStore

DIM = 384

TOOL_NAMES = {
    "trovex",
    "trovex_write",
    "trovex_tag",
    "trovex_read",
    "trovex_search",
    "trovex_delete",
}


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
def state(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    emb = BagEmbedder()
    store = SqliteStore(settings, embedder=emb)
    store.put("# Owned record one\n\nalpha body", kind="record", tags=["owner/alpha"])
    store.put("# Owned record two\n\nbravo body")

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "guide.md").write_text("# Deploy guide\n\nkubernetes rollout steps", encoding="utf-8")
    (repo / "auth.md").write_text("# Auth flow\n\njwt token signature", encoding="utf-8")
    Indexer(settings, embedder=emb).reindex(sources=[Source(id="code", label="my-app", root=repo)])

    state_mod._state = AppState(
        settings=settings,
        embedder=emb,
        searcher=Searcher(settings, embedder=emb),
        indexer=Indexer(settings, embedder=emb),
        store=store,
    )
    try:
        yield state_mod._state
    finally:
        state_mod.reset_state()


def test_catalog_index_groups_all_sources(state):
    out = mcp_app.catalog_index()
    assert "trovex catalog" in out
    # both the owned store and the filesystem source appear, grouped.
    assert "(trovex)" in out and "(code)" in out
    assert "Owned record one" in out and "Deploy guide" in out
    assert "★" in out  # canonical marker


def test_catalog_handles_are_addressable(state):
    """A filesystem doc is addressed by its path, an owned record by its trovex id."""
    out = mcp_app.catalog_index()
    assert "guide.md" in out  # fs handle
    assert "· trovex:" in out  # owned-record handle


def test_catalog_sources_lists_counts(state):
    out = mcp_app.catalog_sources()
    assert "**code**" in out and "**trovex**" in out
    assert out.count("2 docs") == 2  # 2 owned + 2 fs


def test_catalog_for_source_is_scoped(state):
    out = mcp_app.catalog_for_source("code")
    assert "Deploy guide" in out and "Auth flow" in out
    assert "Owned record" not in out  # scoped to 'code' only


def test_catalog_for_unknown_source_is_explicit(state):
    out = mcp_app.catalog_for_source("does-not-exist")
    assert "unknown source" in out
    assert "Owned record" not in out and "Deploy guide" not in out


def test_catalog_excludes_stale_and_duplicate(state):
    """Only canonical/plan docs surface — never stale/duplicate noise."""
    # Force a doc to 'duplicate' status directly, then confirm it's filtered.
    db = state.store.db
    db.execute("UPDATE docs SET status='duplicate' WHERE title='Deploy guide'")
    db.commit()
    out = mcp_app.catalog_index()
    assert "Deploy guide" not in out
    assert "Auth flow" in out  # its canonical sibling still shows


@pytest.mark.asyncio
async def test_resources_registered_and_tools_unchanged(state):
    # Additive: the 6 tools are exactly what they were.
    tools = await mcp_app.mcp.list_tools()
    assert {t.name for t in tools} == TOOL_NAMES

    resources = await mcp_app.mcp.list_resources()
    uris = {str(r.uri) for r in resources}
    assert {"trovex://sources", "trovex://catalog"} <= uris

    templates = await mcp_app.mcp.list_resource_templates()
    assert "trovex://catalog/{source}" in {t.uriTemplate for t in templates}
