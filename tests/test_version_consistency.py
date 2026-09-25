"""Version-string drift guard (task 7111f05a round 2).

trovex's REAL, installed package version is git-tag-derived (hatch-vcs) and
read at runtime via importlib.metadata (cli.py's `trovex --version`) — that
one is always correct. But two other surfaces carry their own hardcoded
version string that nothing keeps in sync automatically: server.json (the MCP
registry manifest) and src/trovex/__init__.py's __version__. Round 1 shipped
with server.json still at 0.13.1 and __init__.py still at 0.11.0 while the
release was meant to be 0.13.4 — caught by the review gate, not by any test.

CHANGELOG.md's top entry (`## X.Y.Z`) is now the intended source of truth for
"what release is this" — this test pins that server.json and __init__.py
agree with it, so the NEXT release forgetting to bump one of them fails
`make test` instead of a human catching it in review.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _changelog_top_version() -> str:
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^## (\d+\.\d+\.\d+)", text, re.MULTILINE)
    assert m, "CHANGELOG.md has no '## X.Y.Z' top entry to anchor the version check on"
    return m.group(1)


def test_server_json_version_matches_changelog():
    version = _changelog_top_version()
    manifest = json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))
    assert manifest["version"] == version, (
        f"server.json top-level version {manifest['version']!r} != CHANGELOG.md {version!r}"
    )
    for pkg in manifest["packages"]:
        assert pkg["version"] == version, (
            f"server.json packages[].version {pkg['version']!r} != CHANGELOG.md {version!r}"
        )


def test_init_py_version_matches_changelog():
    version = _changelog_top_version()
    init_src = (REPO_ROOT / "src" / "trovex" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init_src)
    assert m, "src/trovex/__init__.py has no __version__ string"
    assert m.group(1) == version, (
        f"src/trovex/__init__.py __version__ {m.group(1)!r} != CHANGELOG.md {version!r}"
    )
