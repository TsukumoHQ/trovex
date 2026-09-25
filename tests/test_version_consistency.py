"""Version-string drift guard (task 7111f05a round 2, hardened by 5c18adb7).

trovex's REAL, installed package version is git-tag-derived (hatch-vcs) and
read at runtime via importlib.metadata (cli.py's `trovex --version`) — that
one is always correct, untouched by anything here. Two OTHER surfaces carry
their own hardcoded version string that nothing keeps in sync automatically:
server.json (the MCP registry manifest, which lists ONE packages[] entry per
transport — stdio and streamable-http — of the same PyPI package) and
src/trovex/__init__.py's __version__.

Round 1 (7111f05a) anchored a test on CHANGELOG.md's top `## X.Y.Z` entry as
"the truth" and shipped it agreeing with server.json/__init__.py — but
CHANGELOG.md's own number (0.13.4) was itself wrong (PyPI was already at
0.15.0), so the test passed while being wrong about what actually needed to
ship. Round 2 (5c18adb7) drops CHANGELOG.md as the anchor for the BLOCKING
check — a hand-maintained doc that already caused one incident is not a safe
source of truth for a gate — and instead pins SELF-consistency: every
server.json packages[].version must equal server.json's own top-level
.version, and __init__.py must equal it too. This is exactly what broke in
production: publish-mcp.yml's sync step only updated packages[0], so
packages[1] silently drifted from .version and the MCP registry 400'd on a
PyPI version that never existed.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _server_json() -> dict:
    return json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))


def test_server_json_packages_version_matches_top_level():
    """AC: every packages[].version == .version. This is the exact invariant
    publish-mcp.yml's sync step must maintain — a stale packages[] entry is
    what made the MCP registry 400 on v0.15.1 (task 5c18adb7)."""
    manifest = _server_json()
    version = manifest["version"]
    assert manifest["packages"], "server.json has no packages[] entries to check"
    for i, pkg in enumerate(manifest["packages"]):
        assert pkg["version"] == version, (
            f"server.json packages[{i}].version {pkg['version']!r} != top-level version {version!r}"
        )


def test_init_py_version_matches_server_json():
    manifest = _server_json()
    version = manifest["version"]
    init_src = (REPO_ROOT / "src" / "trovex" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init_src)
    assert m, "src/trovex/__init__.py has no __version__ string"
    assert m.group(1) == version, (
        f"src/trovex/__init__.py __version__ {m.group(1)!r} != server.json version {version!r}"
    )


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not on PATH (the workflow's own tool)")
def test_publish_mcp_sync_updates_every_package_version(tmp_path):
    """AC: unit test of the sync jq itself, on a fixture, with a fake tag —
    pins the fix directly (the workflow bug was 'jq ... .packages[0].version
    = $v', silently leaving packages[1+] stale) rather than only pinning the
    committed server.json's current values."""
    fixture = {
        "version": "0.1.0",
        "packages": [
            {"registryType": "pypi", "identifier": "trovex", "version": "0.1.0"},
            {"registryType": "pypi", "identifier": "trovex", "version": "0.1.0"},
            {"registryType": "pypi", "identifier": "trovex", "version": "0.1.0"},
        ],
    }
    src = tmp_path / "server.json"
    src.write_text(json.dumps(fixture))

    jq_filter = (REPO_ROOT / ".github" / "workflows" / "publish-mcp.yml").read_text(encoding="utf-8")
    m = re.search(r"jq --arg v \"\$VERSION\" '([^']+)'", jq_filter)
    assert m, "publish-mcp.yml's sync step jq filter has changed shape — update this test's extraction"
    filter_expr = m.group(1)

    result = subprocess.run(
        ["jq", "--arg", "v", "9.9.9", filter_expr, str(src)],
        capture_output=True,
        text=True,
        check=True,
    )
    synced = json.loads(result.stdout)

    assert synced["version"] == "9.9.9"
    assert [p["version"] for p in synced["packages"]] == ["9.9.9"] * 3, (
        "the sync filter must update EVERY packages[].version, not just packages[0]"
    )
