from __future__ import annotations

import subprocess
from pathlib import Path

from trovex.config import LEGACY_DATA_DIR, Settings, default_data_dir


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_default_data_dir_is_per_git_worktree(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "user.email", "dev@example.com", cwd=repo)
    _git("config", "user.name", "Dev", cwd=repo)
    (repo / "README.md").write_text("# root\n", encoding="utf-8")
    _git("add", "README.md", cwd=repo)
    _git("commit", "-q", "-m", "init", cwd=repo)

    wt = tmp_path / "repo-feature"
    _git("worktree", "add", "-q", str(wt), "-b", "feature", cwd=repo)

    monkeypatch.chdir(repo)
    repo_dir = default_data_dir()
    repo_settings = Settings()

    monkeypatch.chdir(wt)
    wt_dir = default_data_dir()
    wt_settings = Settings()

    assert repo_dir != wt_dir
    assert repo_dir.parent == LEGACY_DATA_DIR / "worktrees"
    assert wt_dir.parent == LEGACY_DATA_DIR / "worktrees"
    assert repo_settings.sources_config_path == repo_settings.data_dir / "sources.yaml"
    assert wt_settings.sources_config_path == wt_settings.data_dir / "sources.yaml"


def test_data_dir_env_override_moves_default_sources_config(tmp_path, monkeypatch):
    custom = tmp_path / "custom-index"
    monkeypatch.setenv("TROVEX_DATA_DIR", str(custom))
    monkeypatch.delenv("TROVEX_SOURCES_CONFIG_PATH", raising=False)

    settings = Settings()

    assert settings.data_dir == custom
    assert settings.sources_config_path == custom / "sources.yaml"
