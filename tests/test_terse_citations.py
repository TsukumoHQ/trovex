"""Terse citation outputs — trovex_search returns pointers, not dumps.

Steal #4: a search result is a compact ANCHORED citation (heading breadcrumb +
doc-id over a short snippet) plus one 'climb the ladder' affordance — never k
full sections concatenated. Pairs with the access ladder (#3): search to triage,
trovex_read to climb.

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


_LONG = " ".join(f"reverse proxy tls nginx word{i}" for i in range(80))
_DOC = f"# Deploy guide\n\n## Reverse proxy\n\n{_LONG}\n"


@pytest.fixture
def wired(tmp_path, monkeypatch):
    monkeypatch.setenv("TROVEX_ALLOW_UNAUTH_WRITES", "1")
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    store = SqliteStore(settings, embedder=BagEmbedder())
    store.put(_DOC, kind="record")
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


def test_search_result_is_an_anchored_citation(wired):
    out = mcp_app.trovex_search(q="reverse proxy tls")
    assert "Deploy guide > Reverse proxy" in out  # breadcrumb
    assert "trovex:" in out  # doc-id anchor
    assert "Climb the ladder" in out  # affordance


def test_search_snippet_is_trimmed_not_a_dump(wired):
    """The citation snippet must be a short pointer, not the whole section — the
    full section has 80 marker words; the citation truncates well before that."""
    out = mcp_app.trovex_search(q="reverse proxy tls")
    assert "…" in out  # snippet truncated
    assert "word79" not in out  # the tail of the section is NOT dumped
    # strictly smaller than the whole section it points at
    section = wired.store.section_text(
        wired.store.db.execute("SELECT id FROM docs LIMIT 1").fetchone()["id"],
        "Deploy guide > Reverse proxy",
    )
    assert len(out) < len(section)


def test_ladder_hint_appears_once_for_many_hits(wired):
    wired.store.put("# Other\n\n## Reverse proxy notes\n\n" + _LONG, kind="record")
    out = mcp_app.trovex_search(q="reverse proxy tls", k=5)
    assert out.count("Climb the ladder") == 1  # one affordance, not per-hit
    assert out.count("———") >= 1  # multiple citations separated


def test_no_results_is_clean(tmp_path, monkeypatch):
    """An empty store yields the clean sentinel, no citation scaffolding."""
    monkeypatch.setenv("TROVEX_ALLOW_UNAUTH_WRITES", "1")
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    store = SqliteStore(settings, embedder=BagEmbedder())  # empty
    state_mod._state = AppState(
        settings=settings,
        embedder=BagEmbedder(),
        searcher=Searcher(settings, embedder=BagEmbedder()),
        indexer=Indexer(settings, embedder=BagEmbedder()),
        store=store,
    )
    try:
        out = mcp_app.trovex_search(q="anything at all")
        assert "(no results)" in out
        assert "Climb the ladder" not in out
    finally:
        state_mod.reset_state()
