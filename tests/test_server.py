"""HTTP route tests for the Active-Memory surface (RFC 330e7d43).

Store-level scope/recall is covered in test_store.py; this exercises the FastAPI
routes that wrap it — /api/search (kind/tags query params) and /api/boot
(owner+kind scope, mixed-case agent recall). Hermetic: the deterministic
BagEmbedder, an in-memory-ish tmp store, and a TestClient WITHOUT a lifespan
context (so the /mcp session manager is never started — these routes don't need
it, and get_state() returns the injected test state per request).
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient

from trovex import state as state_mod
from trovex.config import Settings
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.server import build_app
from trovex.state import AppState
from trovex.store import SqliteStore

DIM = 384


class BagEmbedder:
    """Stable hashing bag-of-words embedder — shared tokens → high cosine."""

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
def client(tmp_path):
    """A TestClient backed by a known corpus, with the app's global state injected.

    Corpus is written BEFORE the searcher is built so every connection sees it.
    The trailing reset_state() keeps the process-wide singleton from leaking into
    other tests.
    """
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",  # dim 384, matches BagEmbedder
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)

    # owner/alpha record + owner/beta living doc → kind/tag scope can separate them.
    store.put(
        "# Auth incident\n\ncurrent state resume open work in flight next steps gotchas",
        kind="record",
        tags=["owner/alpha"],
    )
    store.put(
        "# Auth note\n\ncurrent state resume open work in flight next steps gotchas",
        tags=["owner/beta"],
    )
    # A record owned by a MIXED-CASE agent. Tags are stored lower-cased
    # (owner/coo); /api/boot must lower-case the queried agent to match it.
    store.put(
        "# COO handoff\n\ncurrent state resume open work in flight next steps gotchas",
        kind="record",
        tags=["owner/coo"],
    )

    searcher = Searcher(settings, embedder=embedder)
    indexer = Indexer(settings, embedder=embedder)
    state_mod._state = AppState(
        settings=settings,
        embedder=embedder,
        searcher=searcher,
        indexer=indexer,
        store=store,
    )
    try:
        yield TestClient(build_app())
    finally:
        state_mod.reset_state()


def test_api_search_scopes_by_kind_and_tags(client):
    """/api/search threads kind + (comma-separated) tags into the store scope."""
    q = "current state resume work"

    # No scope → both auth docs come back.
    base = client.get("/api/search", params={"q": q, "limit": 5}).json()
    titles = {r["title"] for r in base}
    assert "Auth incident" in titles and "Auth note" in titles

    # kind=record → drops the living (kind-less) note.
    by_kind = client.get("/api/search", params={"q": q, "limit": 5, "kind": "record"}).json()
    kind_titles = {r["title"] for r in by_kind}
    assert "Auth note" not in kind_titles
    assert "Auth incident" in kind_titles

    # tags scope (any-match) → only the alpha-owned doc.
    by_tag = client.get("/api/search", params={"q": q, "limit": 5, "tags": "owner/alpha"}).json()
    assert [r["title"] for r in by_tag] == ["Auth incident"]


def test_api_boot_recalls_mixed_case_owner(client):
    """Regression for the silent mixed-case bug: GET /api/boot?agent=COO must
    recall the owner/coo record (tags are stored lower-cased)."""
    upper = client.get("/api/boot", params={"agent": "COO", "floor": 0.0}).json()
    assert upper["agent"] == "COO"
    assert [p["title"] for p in upper["pointers"]] == ["COO handoff"]
    assert upper["tokens_est"] > 0

    # The already-lower-case spelling resolves to the same record.
    lower = client.get("/api/boot", params={"agent": "coo", "floor": 0.0}).json()
    assert [p["title"] for p in lower["pointers"]] == ["COO handoff"]


def test_api_boot_unknown_agent_is_empty(client):
    """An agent with no records injects nothing — even at floor 0 it's scope, not
    score, that excludes it (zero-cost boot for an unknown session)."""
    out = client.get("/api/boot", params={"agent": "nobody", "floor": 0.0}).json()
    assert out["pointers"] == []
    assert out["tokens_est"] == 0


def test_api_boot_owner_scope_excludes_other_owners(client):
    """Boot is owner-scoped: alpha never sees beta's or coo's records."""
    out = client.get("/api/boot", params={"agent": "alpha", "floor": 0.0}).json()
    titles = {p["title"] for p in out["pointers"]}
    assert titles == {"Auth incident"}


def test_search_page_renders_states(client):
    """The /search surface ships all four UX states. Empty (no query) prompts; a real
    query renders the result list; and the page wires the error-state template + the
    htmx error handlers so a failed /search/partial isn't a silent freeze."""
    empty = client.get("/search")
    assert empty.status_code == 200
    assert "type a query to search" in empty.text  # empty/no-query state

    hit = client.get("/search", params={"q": "current state work in flight"})
    assert hit.status_code == 200
    assert "result-list" in hit.text and "Auth incident" in hit.text  # results state

    # Error state: the template + the three htmx error hooks must be present so a
    # non-2xx / dropped /search/partial swaps in a retry instead of freezing.
    assert 'id="search-error-tpl"' in empty.text
    assert "htmx:responseError" in empty.text
    assert "htmx:sendError" in empty.text


def test_search_partial_renders_no_results_state(client):
    """A scope that excludes every doc renders the no-results empty state (not a 500).
    (knn has no score floor, so a gibberish query still returns top-k — emptiness comes
    from a filter that matches nothing, here kind=note with no note docs indexed.)"""
    res = client.get("/search/partial", params={"q": "current state", "kind": "note"})
    assert res.status_code == 200
    assert "no results" in res.text
