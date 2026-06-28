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

from trovex import mcp_app

# Frozen contract. props = the FULL set of parameters a client may send; required = the
# subset it MUST send. Both are part of the public wire contract.
CONTRACT: dict[str, dict[str, set[str]]] = {
    "trovex": {"props": {"q", "summary"}, "required": {"q"}},
    "trovex_search": {"props": {"query", "k", "kind", "tags"}, "required": {"query"}},
    "trovex_read": {"props": {"query", "doc_id", "section", "full"}, "required": set()},
    "trovex_write": {
        "props": {"content", "kind", "doc_id", "tags", "ticket", "force", "section"},
        "required": {"content"},
    },
    "trovex_tag": {"props": {"doc_id", "add", "remove"}, "required": {"doc_id"}},
    "trovex_delete": {"props": {"doc_id"}, "required": {"doc_id"}},
}


def _tools() -> dict:
    return {t.name: t for t in mcp_app.mcp._tool_manager.list_tools()}


def _params(name: str):
    return inspect.signature(getattr(mcp_app, name)).parameters


def test_tool_set_is_exactly_the_contract():
    """Exactly these six tools — no more (an unpinned new tool), no fewer (a removed
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
