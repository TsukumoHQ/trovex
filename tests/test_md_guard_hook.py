"""trovex-md-guard / -read-guard PreToolUse hooks — scope + .trovexignore.

Pins the TSU-79 fix: the guards own ONLY the trovex repo's SSOT markdown. A
SKILL.md (disk persona, never SSOT) or any .md living in a DIFFERENT repo must
NOT be blocked; real trovex SSOT .md stays guarded; .trovexignore still exempts.

The deny branch needs trovex reachable, so a stub /healthz server stands in.
Skips cleanly if bash or jq is missing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_WRITE_GUARD = _REPO / "deploy" / "hooks" / "trovex-md-guard.sh"
_READ_GUARD = _REPO / "deploy" / "hooks" / "trovex-md-read-guard.sh"

pytestmark = pytest.mark.skipif(
    not (shutil.which("bash") and shutil.which("jq")),
    reason="bash + jq required for the hook scripts",
)


class _OkHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (http.server API)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_args):  # silence the test log
        pass


@pytest.fixture
def trovex_up():
    """A live stub answering /healthz 200, so the deny branch is reachable."""
    srv = HTTPServer(("127.0.0.1", 0), _OkHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()


def _run(script: Path, tool: str, file_path: str, trovex_url: str) -> dict:
    payload = json.dumps({"tool_name": tool, "tool_input": {"file_path": file_path}})
    out = subprocess.run(
        ["bash", str(script)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "TROVEX_URL": trovex_url},
        check=True,
    )
    return {"stdout": out.stdout.strip()}


def _is_deny(result: dict) -> bool:
    if not result["stdout"]:
        return False
    parsed = json.loads(result["stdout"])
    return parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


# --- the bug: foreign-repo / SKILL.md edits must NOT be blocked -----------------


def test_write_guard_allows_skill_md_in_foreign_repo(tmp_path, trovex_up):
    foreign = tmp_path / "SKILL.md"
    foreign.write_text("# a skill persona\n")
    assert not _is_deny(_run(_WRITE_GUARD, "Write", str(foreign), trovex_up))


def test_write_guard_allows_plain_md_outside_trovex(tmp_path, trovex_up):
    foreign = tmp_path / "notes.md"
    foreign.write_text("# foreign doc\n")
    assert not _is_deny(_run(_WRITE_GUARD, "Edit", str(foreign), trovex_up))


def test_read_guard_allows_skill_md_in_foreign_repo(tmp_path, trovex_up):
    foreign = tmp_path / "SKILL.md"
    foreign.write_text("# a skill persona\n")
    assert not _is_deny(_run(_READ_GUARD, "Read", str(foreign), trovex_up))


# --- still guarded: real trovex SSOT markdown ----------------------------------


def test_write_guard_denies_trovex_ssot_md(trovex_up):
    # A .md under the trovex repo root, not on the .trovexignore keep-list → deny.
    target = str(_REPO / "__guard_probe__.md")
    assert _is_deny(_run(_WRITE_GUARD, "Write", target, trovex_up))


def test_write_guard_honors_trovexignore_keeplist(trovex_up):
    # README.md is on the keep-list → allowed even inside the trovex repo.
    target = str(_REPO / "README.md")
    assert not _is_deny(_run(_WRITE_GUARD, "Write", target, trovex_up))


def test_write_guard_allows_repo_without_trovexignore(tmp_path, trovex_up):
    # A git repo that hasn't opted into the doc-regime (no .trovexignore) → allow.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    doc = tmp_path / "notes.md"
    doc.write_text("# not a trovex repo\n")
    assert not _is_deny(_run(_WRITE_GUARD, "Write", str(doc), trovex_up))


def test_write_guard_install_location_independent(tmp_path, trovex_up):
    # Regression (cto 2026-06-28): when the hook is INSTALLED to ~/.claude/hooks (not a
    # git repo), the old script-location probe returned empty and over-denied scratchpad
    # + foreign .md. Run a copy of the hook from a non-repo dir against a non-git .md →
    # must still ALLOW. The scope is keyed on the edited file's repo, not the script's.
    installed = tmp_path / "hooks" / "trovex-md-guard.sh"
    installed.parent.mkdir()
    shutil.copy(_WRITE_GUARD, installed)
    scratch = tmp_path / "scratchpad" / "probe.md"
    scratch.parent.mkdir()
    scratch.write_text("# scratch\n")
    assert not _is_deny(_run(installed, "Write", str(scratch), trovex_up))
