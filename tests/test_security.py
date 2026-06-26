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


# ── Round 2 · Finding 1: write-auth is fail-closed by default ────────

def test_write_token_auto_generated_and_persisted(tmp_path):
    """With no env token and no opt-in, resolve_write_token() mints a persisted
    per-instance token (fail-closed), not the open-writes default."""
    settings = _make_settings(tmp_path)
    assert settings.write_token == ""           # nothing configured
    tok = settings.resolve_write_token()
    assert tok                                   # a real token was produced
    token_file = tmp_path / ".write_token"
    assert token_file.exists()
    assert token_file.read_text().strip() == tok
    # A second resolve reuses the same persisted token (stable across boots).
    assert _make_settings(tmp_path).resolve_write_token() == tok
    # 0600 perms (owner-only) where the platform supports it.
    import os
    import stat
    mode = stat.S_IMODE(os.stat(token_file).st_mode)
    if os.name == "posix":
        assert mode == 0o600


def test_writes_require_auto_token_by_default(tmp_path):
    """A default instance (no env token, no opt-in) denies an anonymous write and
    accepts it only with the auto-generated token — the new default posture."""
    (tmp_path / "project").mkdir()
    settings = _make_settings(tmp_path)
    settings.write_token = settings.resolve_write_token()  # what get_state() does
    assert settings.write_token
    _inject_state(settings)
    try:
        client = TestClient(build_app())
        # No token header → denied (fail-closed).
        assert client.post("/api/capture", json={"agent": "a", "summary": "x"}).status_code == 403
        # Correct auto-token → allowed.
        ok = client.post(
            "/api/capture",
            json={"agent": "a", "summary": "x"},
            headers={"x-trovex-write-token": settings.write_token},
        )
        assert ok.status_code == 200
    finally:
        state_mod.reset_state()


def test_allow_unauth_writes_opt_in_keeps_writes_open(tmp_path):
    """The explicit TROVEX_ALLOW_UNAUTH_WRITES escape hatch resolves to an empty
    token → writes open (only intended for localhost / trusted networks)."""
    settings = _make_settings(tmp_path, allow_unauth_writes=True)
    assert settings.resolve_write_token() == ""
    settings.write_token = settings.resolve_write_token()
    _inject_state(settings)
    try:
        client = TestClient(build_app())
        assert client.post("/api/capture", json={"agent": "a", "summary": "x"}).status_code == 200
    finally:
        state_mod.reset_state()


def test_write_token_endpoint_refuses_non_loopback(tmp_path):
    """/api/write-token only answers same-machine clients; the TestClient's
    default host ('testclient') is not loopback → refused."""
    settings = _make_settings(tmp_path)
    settings.write_token = settings.resolve_write_token()
    _inject_state(settings)
    try:
        client = TestClient(build_app())
        assert client.get("/api/write-token").status_code == 403
    finally:
        state_mod.reset_state()


# ── Round 2 · Finding 2: hook download — traversal + configurable dir ──

def test_hook_download_rejects_traversal(tmp_path):
    _inject_state(_make_settings(tmp_path))
    try:
        client = TestClient(build_app())
        # A traversal / non-allowlisted name is rejected (404), never served.
        assert client.get("/hooks/..%2f..%2fetc%2fpasswd").status_code == 404
        assert client.get("/hooks/not-a-real-hook.sh").status_code == 404
    finally:
        state_mod.reset_state()


def test_hook_dir_is_configurable(tmp_path):
    hooks = tmp_path / "myhooks"
    hooks.mkdir()
    (hooks / "trovex-boot.sh").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    settings = _make_settings(tmp_path, hooks_dir=hooks)
    _inject_state(settings)
    try:
        client = TestClient(build_app())
        r = client.get("/hooks/trovex-boot.sh")
        assert r.status_code == 200
        assert "echo hi" in r.text
    finally:
        state_mod.reset_state()


# ── Round 2 · Finding 3: qpath validation ────────────────────────────

def test_docs_partial_rejects_malformed_qpath(tmp_path):
    _inject_state(_make_settings(tmp_path))
    try:
        client = TestClient(build_app())
        # Illegal char in the path filter → 422.
        assert client.get("/docs/partial", params={"qpath": "a;b|c"}).status_code == 422
        # Over the length cap → 422.
        assert client.get("/docs/partial", params={"qpath": "a" * 300}).status_code == 422
        # A sane path filter still renders (200).
        assert client.get("/docs/partial", params={"qpath": "src/trovex"}).status_code == 200
    finally:
        state_mod.reset_state()


# ── Round 2 · Finding 4: numeric-cast safety ─────────────────────────

def test_restore_rejects_non_integer_version(tmp_path):
    settings = _make_settings(tmp_path)
    settings.write_token = settings.resolve_write_token()
    _inject_state(settings)
    hdr = {"x-trovex-write-token": settings.write_token}
    try:
        client = TestClient(build_app())
        # A non-numeric version_id is a 400, not an uncaught 500.
        r = client.post("/api/doc/whatever/restore", json={"version_id": "abc"}, headers=hdr)
        assert r.status_code == 400
        # A bool is not a valid version id either.
        r2 = client.post("/api/doc/whatever/restore", json={"version_id": True}, headers=hdr)
        assert r2.status_code == 400
    finally:
        state_mod.reset_state()


# ── Round 2 · Finding 5: query-log retention + secret redaction ──────

def test_purge_old_queries_drops_aged_rows(tmp_path):
    from trovex.usage import log_query, purge_old_queries
    store = _inject_state(_make_settings(tmp_path))
    try:
        db = store.db
        log_query(db, "recent query", 1, False, response_tokens_est=1, elapsed_ms=1)
        # Backdate one row well past the retention window.
        old_ts = __import__("time").time() - 200 * 86400
        db.execute("UPDATE mcp_queries SET ts = ? WHERE query = ?", (old_ts, "recent query"))
        db.commit()
        assert db.execute("SELECT COUNT(*) AS c FROM mcp_queries").fetchone()["c"] == 1
        removed = purge_old_queries(db, 90)
        assert removed == 1
        assert db.execute("SELECT COUNT(*) AS c FROM mcp_queries").fetchone()["c"] == 0
        # Retention disabled (<= 0) keeps everything.
        log_query(db, "keep me", 1, False, response_tokens_est=1, elapsed_ms=1)
        assert purge_old_queries(db, 0) == 0
        assert db.execute("SELECT COUNT(*) AS c FROM mcp_queries").fetchone()["c"] == 1
    finally:
        state_mod.reset_state()


def test_query_secret_redaction():
    from trovex.usage import redact_secrets
    assert redact_secrets("email me at alice@example.com please") == \
        "email me at [redacted] please"
    assert "[redacted]" in redact_secrets("use sk-abcdefghijklmnopqrstuvwx for the call")
    assert "[redacted]" in redact_secrets("api_key=supersecretvalue123")
    # An ordinary query is left intact.
    assert redact_secrets("how do we roll back a deploy?") == "how do we roll back a deploy?"
