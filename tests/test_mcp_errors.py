"""Typed tool errors + param aliases (CCAR G1 / Domain 2.1+2.2).

trovex used to surface raw pydantic ValidationErrors and trap callers on the
q-vs-query / tags-must-be-a-list mismatch. Now:
- genuine errors return a typed {code, category, isRetryable, hint} JSON object,
- `q`/`query` are interchangeable across the tools,
- `tags` (and tag add/remove) accept a comma string as well as a list.

Hermetic: bag embedder, no model download.
"""

from __future__ import annotations

import hashlib
import json
import re

import numpy as np
import pytest

from trovex import mcp_app
from trovex import state as state_mod
from trovex.config import Settings
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


def _mk_state(tmp_path, *, write_token: str = ""):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
        write_token=write_token,
    )
    emb = BagEmbedder()
    store = SqliteStore(settings, embedder=emb)
    store.put("# Auth flow\n\njwt token signature validation", tags=["owner/alpha"])
    state_mod._state = AppState(
        settings=settings,
        embedder=emb,
        searcher=Searcher(settings, embedder=emb),
        indexer=None,
        store=store,
    )
    return state_mod._state


@pytest.fixture
def state(tmp_path):
    _mk_state(tmp_path)
    try:
        yield state_mod._state
    finally:
        state_mod.reset_state()


def _as_error(out: str) -> dict | None:
    """Parse a typed-error envelope, or None if `out` is a normal result."""
    try:
        payload = json.loads(out)
    except (ValueError, TypeError):
        return None
    return payload.get("error") if isinstance(payload, dict) else None


# ── typed error shape ────────────────────────────────────────────────────


def test_err_helper_shape():
    err = _as_error(mcp_app._err("x", "validation", "do y", retryable=True))
    assert err == {"code": "x", "category": "validation", "isRetryable": True, "hint": "do y"}


def test_unknown_source_is_typed_validation_error(state):
    err = _as_error(mcp_app.trovex_search(query="jwt", source="nope"))
    assert err and err["code"] == "unknown_source"
    assert err["category"] == "validation" and err["isRetryable"] is False
    assert "nope" in err["hint"]  # names the bad id + the valid ones


def test_unauthorized_is_typed_permission_error(tmp_path):
    _mk_state(tmp_path, write_token="s3cret")  # a set token with no header → denied
    try:
        err = _as_error(mcp_app.trovex_write("# new doc\n\nbody"))
        assert err and err["code"] == "unauthorized"
        assert err["category"] == "permission" and err["isRetryable"] is False
    finally:
        state_mod.reset_state()


def test_missing_query_is_typed_on_each_tool(state):
    for out in (mcp_app.trovex(), mcp_app.trovex_search()):
        err = _as_error(out)
        assert err and err["code"] == "missing_query" and err["category"] == "validation"
    read_err = _as_error(mcp_app.trovex_read())
    assert read_err and read_err["code"] == "missing_input"


def test_section_write_errors_are_typed(state):
    # section patch without doc_id
    err = _as_error(mcp_app.trovex_write("body", section="Nope"))
    assert err and err["code"] == "missing_doc_id"
    # section patch on a real doc but a missing heading
    doc_id = mcp_app.trovex_write("# Real\n\n## Alpha\n\naaa")
    assert _as_error(doc_id) is None  # a successful write returns a bare id
    miss = _as_error(mcp_app.trovex_write("new", doc_id=doc_id, section="Ghost"))
    assert miss and miss["code"] == "section_not_found"


# ── q / query alias ──────────────────────────────────────────────────────


def test_q_is_an_alias_for_query(state):
    """The observed live trap: trovex_search used to reject `q`. Now it's accepted."""
    assert _as_error(mcp_app.trovex_search(q="jwt token")) is None
    assert _as_error(mcp_app.trovex_read(q="jwt token")) is None
    # and the reverse: the `trovex` tool (which uses q) accepts `query`.
    assert _as_error(mcp_app.trovex(query="jwt token")) is None


# ── tags accept a comma string ───────────────────────────────────────────


def test_tags_schema_accepts_string_or_list(state):
    """FastMCP derives the wire schema from the annotation; `tags` must accept a
    bare string, not only an array (the live trap was string→pydantic reject)."""
    tools = {t.name: t for t in mcp_app.mcp._tool_manager.list_tools()}
    tags_schema = json.dumps(tools["trovex_write"].parameters["properties"]["tags"])
    assert '"string"' in tags_schema and '"array"' in tags_schema


def test_tags_comma_string_is_applied(state):
    doc_id = mcp_app.trovex_write("# Tagged\n\nbody", tags="owner/beta,type/report")
    assert _as_error(doc_id) is None
    stored = set(state.store.get(doc_id).tags)
    assert {"owner/beta", "type/report"} <= stored
