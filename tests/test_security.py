"""Security-hardening regression tests (registry-scan fixes).

Each test pins one finding so the hardening can't silently regress:
  - LIKE-escape: a bare `%`/`_` filters literally, not match-all (store + helper).
  - /api/reindex is write-gated (token required when one is configured).
  - the indexer skips a .md symlink whose real target escapes the source root,
    and honours .trovexignore.
  - the search endpoints rate-limit (429) and validate kind/tags (422).

Hermetic: deterministic BagEmbedder, tmp data dir, TestClient without lifespan.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient

from trovex import state as state_mod
from trovex.config import Settings
from trovex.db import like_escape
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


def _make_settings(tmp_path, **over):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",  # dim 384, matches BagEmbedder
        sources_config_path=tmp_path / "no-such-sources.yaml",
        project_root=tmp_path / "project",
        **over,
    )


def _inject_state(settings):
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)
    searcher = Searcher(settings, embedder=embedder)
    indexer = Indexer(settings, embedder=embedder)
    state_mod._state = AppState(
        settings=settings, embedder=embedder,
        searcher=searcher, indexer=indexer, store=store,
    )
    return store


# ── Finding 3: LIKE injection / escaping ─────────────────────────────

def test_like_escape_escapes_specials():
    assert like_escape("a%b") == r"a\%b"
    assert like_escape("a_b") == r"a\_b"
    assert like_escape("a\\b") == "a\\\\b"
    assert like_escape("100%_x") == r"100\%\_x"


def test_store_browse_filter_treats_percent_literally(tmp_path):
    """count_docs(q='%') must NOT match every doc — only docs literally containing
    '%'. Without ESCAPE the wildcard would match the whole store."""
    store = _inject_state(_make_settings(tmp_path))
    try:
        store.put("# Plain doc\n\nno special chars here", kind="note")
        store.put("# Another\n\nstill nothing", kind="note")
        store.put("# Discount\n\nsave 50% today", kind="note")

        assert store.count_docs() == 3
        # '%' as a wildcard would return 3; escaped, it matches only the literal one.
        assert store.count_docs(q="%") == 1
        only = store.list_docs(q="%")
        assert [d.title for d in only] == ["Discount"]
        # '_' likewise must be literal, not "any single char".
        assert store.count_docs(q="_") == 0
    finally:
        state_mod.reset_state()


# ── Finding 2: /api/reindex auth ─────────────────────────────────────

def test_reindex_requires_write_token(tmp_path):
    (tmp_path / "project").mkdir()
    settings = _make_settings(tmp_path, write_token="s3cret")
    _inject_state(settings)
    try:
        client = TestClient(build_app())
        # No token → rejected, same as the other write endpoints.
        assert client.post("/api/reindex").status_code == 403
        # Correct token → allowed.
        ok = client.post("/api/reindex", headers={"x-trovex-write-token": "s3cret"})
        assert ok.status_code == 200
        assert "added" in ok.json()
    finally:
        state_mod.reset_state()


# ── Finding 5: symlink / path-traversal in the indexer ───────────────

def test_indexer_skips_symlink_escaping_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "real.md").write_text("# real\n\nin-root doc", encoding="utf-8")

    # A secret outside the root, reached by a symlink that lives inside it.
    outside = tmp_path / "outside-secret.md"
    outside.write_text("# secret\n\nshould never be indexed", encoding="utf-8")
    link = root / "escape.md"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")

    settings = _make_settings(tmp_path)
    indexer = Indexer(settings, embedder=BagEmbedder())
    found = {p.name for p in indexer.scan(root)}
    assert "real.md" in found
    assert "escape.md" not in found  # canonical target escapes root → skipped


def test_indexer_honors_trovexignore(tmp_path):
    root = tmp_path / "project"
    (root / "docs").mkdir(parents=True)
    (root / "keep.md").write_text("# keep", encoding="utf-8")
    (root / "SECRET.md").write_text("# secret", encoding="utf-8")
    (root / "docs" / "nested.md").write_text("# nested", encoding="utf-8")
    (root / ".trovexignore").write_text("SECRET.md\ndocs/*\n", encoding="utf-8")

    settings = _make_settings(tmp_path)
    indexer = Indexer(settings, embedder=BagEmbedder())
    found = {p.relative_to(root).as_posix() for p in indexer.scan(root)}
    assert "keep.md" in found
    assert "SECRET.md" not in found
    assert "docs/nested.md" not in found


# ── Finding 4: rate limiting ─────────────────────────────────────────

def test_search_rate_limit_returns_429(tmp_path):
    settings = _make_settings(tmp_path, rate_limit_search="2/minute")
    _inject_state(settings)
    try:
        client = TestClient(build_app())
        r1 = client.get("/api/search", params={"q": "anything"})
        r2 = client.get("/api/search", params={"q": "anything"})
        r3 = client.get("/api/search", params={"q": "anything"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert r3.json()["error"] == "rate limit exceeded"
    finally:
        state_mod.reset_state()


def test_write_rate_limit_returns_429(tmp_path):
    settings = _make_settings(tmp_path, rate_limit_write="1/minute")
    _inject_state(settings)
    try:
        client = TestClient(build_app())
        # No token configured → auth passes; the limiter is what trips.
        first = client.post("/api/capture", json={"agent": "a", "summary": "x"})
        second = client.post("/api/capture", json={"agent": "a", "summary": "x"})
        assert first.status_code == 200
        assert second.status_code == 429
    finally:
        state_mod.reset_state()


# ── Finding 6: input validation on kind / tags ───────────────────────

def test_api_search_rejects_malformed_kind_and_tags(tmp_path):
    _inject_state(_make_settings(tmp_path))
    try:
        client = TestClient(build_app())
        # kind with an illegal char → 422 (Query pattern).
        assert client.get("/api/search", params={"q": "x", "kind": "a;b"}).status_code == 422
        # a malformed tag → 422.
        assert client.get("/api/search", params={"q": "x", "tags": "ok,bad tag!"}).status_code == 422
        # too many tags → 422.
        toomany = ",".join(f"t{i}" for i in range(11))
        assert client.get("/api/search", params={"q": "x", "tags": toomany}).status_code == 422
        # a valid request still works.
        assert client.get("/api/search", params={"q": "x", "kind": "record"}).status_code == 200
    finally:
        state_mod.reset_state()


# ── Finding 7: malformed JSON body → 400, not 500 ────────────────────

def test_malformed_json_body_is_400(tmp_path):
    _inject_state(_make_settings(tmp_path))
    try:
        client = TestClient(build_app())
        r = client.post(
            "/api/capture",
            content="{not json",
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 400
        assert r.json()["error"] == "invalid JSON body"
    finally:
        state_mod.reset_state()
