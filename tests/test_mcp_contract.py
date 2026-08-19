"""MCP tool-surface contract.

Pins the wire I/O of every trovex_* MCP tool so a refactor, a dependency bump, or a
careless signature edit can't SILENTLY rename a tool, drop/rename a parameter, make an
optional parameter required, or change the text-output contract — any of which breaks
live MCP clients and the registry listing.

FastMCP derives the `inputSchema` that clients consume directly from each tool's
function signature, so a signature change here IS a wire change. This test makes that
change loud: if it fails, update the frozen CONTRACT *and* treat it as a client-facing
migration (note it / bump the server version), don't just re-baseline.
"""

from __future__ import annotations

import inspect

import pytest

from trovex import mcp_app

# Frozen contract. props = the FULL set of parameters a client may send; required = the
# subset it MUST send. Both are part of the public wire contract.
CONTRACT: dict[str, dict[str, set[str]]] = {
    # `source` (added with per-project scoping) is optional everywhere it appears:
    # an existing client that never sends it keeps searching the whole store.
    #
    # CCAR G1 alias migration: `trovex` uses `q`, the other tools use `query`. To
    # stop agents misfiring on the mismatch each now ACCEPTS the other name as an
    # alias, so `q`/`query` moved from required→optional (a tool returns a typed
    # `missing_query` error when neither is given). Backward-compatible: a client
    # that always sent the original name is unaffected.
    "trovex": {"props": {"q", "summary", "source", "query"}, "required": set()},
    "trovex_search": {"props": {"query", "k", "kind", "tags", "source", "q"}, "required": set()},
    # trovex_read gained `versions`/`version_id` (both optional) for the non-clobber
    # history: list prior snapshots or read one. Additive — existing readers unaffected.
    # It then gained `tier` (optional) for the graduated-access ladder
    # (card→passage→full); default stays passage and `full=true` still maps to the
    # full rung, so existing readers are unaffected.
    "trovex_read": {
        "props": {"query", "doc_id", "section", "full", "q", "tier", "versions", "version_id"},
        "required": set(),
    },
    "trovex_write": {
        "props": {"content", "kind", "doc_id", "tags", "ticket", "force", "section"},
        "required": {"content"},
    },
    "trovex_tag": {"props": {"doc_id", "add", "remove"}, "required": {"doc_id"}},
    "trovex_delete": {"props": {"doc_id"}, "required": {"doc_id"}},
    # Roll a doc back to a prior version (the undo for a bad overwrite); write-gated.
    "trovex_restore": {"props": {"doc_id", "version_id"}, "required": {"doc_id", "version_id"}},
    # Recover a DELETED doc from its tombstone (the undo for delete); write-gated.
    "trovex_undelete": {"props": {"doc_id"}, "required": {"doc_id"}},
}


def _tools() -> dict:
    return {t.name: t for t in mcp_app.mcp._tool_manager.list_tools()}


def _params(name: str):
    return inspect.signature(getattr(mcp_app, name)).parameters


def test_tool_set_is_exactly_the_contract():
    """Exactly these tools — no more (an unpinned new tool), no fewer (a removed
    tool every client still calls)."""
    assert set(_tools()) == set(CONTRACT)


def test_each_tool_params_and_required_pinned():
    tools = _tools()
    for name, spec in CONTRACT.items():
        params = tools[name].parameters
        props = set(params.get("properties", {}))
        required = set(params.get("required", []))
        assert props == spec["props"], f"{name} params drifted: {props} != {spec['props']}"
        assert required == spec["required"], (
            f"{name} required drifted: {required} != {spec['required']} "
            "(making an optional arg required breaks existing callers)"
        )


def test_every_tool_has_a_description():
    """The registry + client tool-pickers render the description; an empty one is a
    silent UX regression."""
    for name, t in _tools().items():
        assert (t.description or "").strip(), f"{name} lost its description"


def test_every_tool_returns_text():
    """The wire contract is unstructured text — all six return str. A structured-output
    change would break every current client."""
    for name in CONTRACT:
        assert _params(name) is not None  # tool fn is importable from the module
        ann = inspect.signature(getattr(mcp_app, name)).return_annotation
        assert ann is str, f"{name} return type changed to {ann!r} (was str)"


def test_client_facing_defaults_pinned():
    """Defaults a client relies on when it omits an optional arg — a flipped default is
    a behaviour change clients can't see in the schema."""
    assert _params("trovex")["summary"].default is False
    assert _params("trovex_search")["k"].default == 5
    assert _params("trovex_search")["kind"].default == ""
    assert _params("trovex_read")["full"].default is False
    assert _params("trovex_write")["force"].default is False


def test_server_info_reports_trovex_version():
    """serverInfo.version must be trovex's own version, not the `mcp` SDK's — FastMCP
    has no `version` kwarg, so this only holds because mcp_app sets it explicitly on
    the low-level server (see _version_string() + the assignment after FastMCP())."""
    import importlib.metadata

    assert mcp_app.mcp._mcp_server.version == mcp_app._version_string()
    assert mcp_app.mcp._mcp_server.version != importlib.metadata.version("mcp")


# ── per-project scoping ──────────────────────────────────────────────────


class _FakeRequest:
    def __init__(self, params: dict):
        self.query_params = params


@pytest.fixture
def two_projects(tmp_path):
    """App state whose sources.yaml declares two known projects, so the resolver
    validates against those and never the developer's real ~/.trovex-data one."""
    import yaml

    from trovex import state as state_mod
    from trovex.config import Settings
    from trovex.state import AppState

    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        yaml.safe_dump(
            {
                "sources": [
                    {"id": "alpha", "label": "alpha", "root": str(tmp_path / "a")},
                    {"id": "beta", "label": "beta", "root": str(tmp_path / "b")},
                ]
            }
        )
    )
    settings = Settings(data_dir=tmp_path, sources_config_path=cfg)
    state_mod._state = AppState(
        settings=settings, embedder=None, searcher=None, indexer=None, store=None
    )
    try:
        yield settings
    finally:
        state_mod.reset_state()


def _scope(monkeypatch, *, pinned: str | None, explicit: str = ""):
    """Resolve a scope with the MCP request pinned to `?source=<pinned>`."""
    monkeypatch.setattr(mcp_app, "_pinned_source", lambda: pinned or "")
    return mcp_app._resolve_source(explicit)


def test_scope_defaults_to_whole_store(monkeypatch, two_projects):
    """Nothing pinned, nothing passed → unchanged behaviour. This is what keeps
    an existing user-global .mcp.json working exactly as before."""
    assert _scope(monkeypatch, pinned=None) is None


def test_scope_uses_the_url_pin(monkeypatch, two_projects):
    """A project pins ?source=<id> in its .mcp.json and every call inherits it —
    the daemon is shared and cannot see the client's cwd."""
    assert _scope(monkeypatch, pinned="alpha") == "alpha"


def test_explicit_argument_overrides_the_pin(monkeypatch, two_projects):
    """An agent can reach into another project on purpose."""
    assert _scope(monkeypatch, pinned="alpha", explicit="beta") == "beta"


def test_owned_store_is_a_valid_scope(monkeypatch, two_projects):
    """'trovex' never appears in sources.yaml (it's reserved) but owns every
    written doc, so it must still be scopable."""
    assert _scope(monkeypatch, pinned="trovex") == "trovex"


def test_star_means_all_sources(monkeypatch, two_projects):
    """The escape hatch: search everything even from a pinned connection."""
    assert _scope(monkeypatch, pinned="alpha", explicit="*") is None
    assert _scope(monkeypatch, pinned="*") is None


def test_unknown_source_raises(monkeypatch, two_projects):
    """A typo must not silently filter every result away."""
    with pytest.raises(ValueError, match="unknown source"):
        _scope(monkeypatch, pinned="typo-project")


def test_pinned_source_reads_the_request_query_param(monkeypatch):
    """_pinned_source pulls ?source= off the live MCP request."""

    class _Ctx:
        request_context = type("RC", (), {"request": _FakeRequest({"source": " wraith "})})()

    monkeypatch.setattr(mcp_app.mcp, "get_context", lambda: _Ctx())
    assert mcp_app._pinned_source() == "wraith"


def test_pinned_source_is_empty_outside_a_request(monkeypatch):
    """stdio transport / no active request → no pin, not a crash."""

    def _boom():
        raise LookupError("no active request")

    monkeypatch.setattr(mcp_app.mcp, "get_context", _boom)
    assert mcp_app._pinned_source() == ""
