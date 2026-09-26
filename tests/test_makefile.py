"""`make test` must provision dev deps itself: the review gate runs verify_cmd
verbatim in a bare worktree, where `uv run pytest` otherwise fails on import
(task 7984d9e3: 'make test exit 2 in 13s' in the reviewer tree)."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _dry_run(target: str) -> list[str]:
    out = subprocess.run(
        ["make", "-n", target], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def test_make_test_syncs_dev_deps_before_lint_and_pytest():
    cmds = _dry_run("test")
    assert cmds[0] == "uv sync --all-extras --all-groups --frozen"
    assert cmds.index("uv run ruff check .") < cmds.index("uv run pytest")
