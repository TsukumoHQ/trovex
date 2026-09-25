"""onboarding.gather/build (task 7111f05a — the module `trovex import`/`trovex
onboard` needed but that was never committed, so `from . import onboarding`
raised ImportError on every real install).
"""

from __future__ import annotations

import os
import subprocess
import time

import pytest

from trovex import onboarding


def _write(root, rel, text, *, mtime=None):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def test_gather_finds_markdown_ignores_dirs_and_binaries(tmp_path):
    root = tmp_path / "repo"
    _write(root, "a.md", "# A\n\nbody")
    _write(root, "sub/b.md", "# B\n\nbody")
    _write(root, "notes.txt", "not markdown")
    _write(root, "node_modules/junk.md", "# ignored\n\nbody")
    (root / "empty.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "empty.md").write_text("", encoding="utf-8")

    paths = onboarding.gather(root, {"node_modules"}, max_bytes=1_000_000)
    rels = sorted(str(p.relative_to(root)) for p in paths)
    assert rels == ["a.md", "sub/b.md"]  # notes.txt (wrong ext), node_modules (ignored), empty.md (0 bytes) excluded


def test_gather_respects_max_bytes(tmp_path):
    root = tmp_path / "repo"
    _write(root, "big.md", "x" * 100)
    paths = onboarding.gather(root, set(), max_bytes=50)
    assert paths == []


def test_build_extracts_title_and_falls_back_to_mtime(tmp_path):
    root = tmp_path / "repo"
    p = _write(root, "a.md", "# My Title\n\nbody text", mtime=1_700_000_000)

    f = onboarding.build(p, root, "mylabel")

    assert f is not None
    assert f.rel == "a.md"
    assert f.title == "My Title"
    assert f.content == "# My Title\n\nbody text"
    assert f.date_source == "mtime"
    assert f.mtime == pytest.approx(1_700_000_000, abs=1)


def test_build_returns_none_for_empty_file(tmp_path):
    root = tmp_path / "repo"
    p = _write(root, "empty.md", "   \n\n  ")
    assert onboarding.build(p, root, "label") is None


def test_build_frontmatter_date_wins_over_mtime(tmp_path):
    root = tmp_path / "repo"
    p = _write(
        root,
        "a.md",
        '---\ndate: "2020-01-15"\n---\n# A\n\nbody',
        mtime=1_700_000_000,
    )
    f = onboarding.build(p, root, "label")
    assert f.date_source == "frontmatter"
    expected = time.mktime(time.strptime("2020-01-15", "%Y-%m-%d"))
    # allow either local or UTC interpretation drift, but must clearly be 2020 not mtime's 2023-ish
    assert abs(f.mtime - expected) < 24 * 3600 + 1


def test_build_git_first_commit_date_wins_over_frontmatter_and_mtime(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=False)
    if not (root / ".git").exists():
        pytest.skip("git not available in this environment")
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)

    p = _write(root, "a.md", '---\ndate: "2020-01-15"\n---\n# A\n\nbody', mtime=1_700_000_000)
    env = dict(os.environ, GIT_AUTHOR_DATE="2019-06-01T00:00:00", GIT_COMMITTER_DATE="2019-06-01T00:00:00")
    subprocess.run(["git", "add", "a.md"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add a.md"], cwd=root, check=True, env=env)

    f = onboarding.build(p, root, "label")
    assert f.date_source == "git"
    # 2019-06-01, not 2020 (frontmatter) or 2023-ish (mtime).
    assert time.gmtime(f.mtime).tm_year == 2019


def test_build_ext_id_stable_across_rebuilds(tmp_path):
    root = tmp_path / "repo"
    p = _write(root, "a.md", "# A\n\nbody v1")
    id1 = onboarding.build(p, root, "label").ext_id
    _write(root, "a.md", "# A\n\nbody v2 (edited)")
    id2 = onboarding.build(p, root, "label").ext_id
    assert id1 == id2, "re-importing the same path must update in place, not duplicate"


def test_build_tags_from_folder_path(tmp_path):
    root = tmp_path / "repo"
    p = _write(root, "Team Updates/2026 Q1.md", "# Q1\n\nbody")
    f = onboarding.build(p, root, "mysrc")
    assert f.tags[0] == "mysrc"
    assert "team-updates" in f.tags
