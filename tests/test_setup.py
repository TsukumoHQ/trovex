"""trovex setup — activation install: skill + hooks + settings merge.

Drives run_setup() against a throwaway CLAUDE_CONFIG_DIR (mcp disabled so no
`claude` CLI is touched) and asserts the activation gate: the skill lands where
Claude Code resolves it, the hooks land executable, settings.json registers them,
and re-running is idempotent + non-destructive.
"""

import json
import stat

import pytest

from trovex.setup_cmd import HOOK_EVENTS, run_setup


@pytest.fixture
def claude_dir(tmp_path, monkeypatch):
    d = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(d))
    return d


def _read_settings(claude_dir):
    return json.loads((claude_dir / "settings.json").read_text())


def test_setup_lands_skill_hooks_and_settings(claude_dir):
    rc = run_setup(mcp=False)
    assert rc == 0

    skill = claude_dir / "skills" / "trovex" / "SKILL.md"
    assert skill.is_file()
    assert "name: trovex" in skill.read_text()

    for fname in HOOK_EVENTS.values():
        h = claude_dir / "hooks" / "trovex" / fname
        assert h.is_file()
        assert h.stat().st_mode & stat.S_IXUSR  # executable

    settings = _read_settings(claude_dir)
    for event in HOOK_EVENTS:
        cmds = [
            hk["command"]
            for entry in settings["hooks"][event]
            for hk in entry["hooks"]
        ]
        assert any("trovex" in c for c in cmds)


def test_setup_is_idempotent(claude_dir):
    run_setup(mcp=False)
    run_setup(mcp=False)
    settings = _read_settings(claude_dir)
    # exactly one trovex entry per event — no duplication on re-run
    for event in HOOK_EVENTS:
        assert len(settings["hooks"][event]) == 1


def test_setup_preserves_existing_settings(claude_dir):
    claude_dir.mkdir(parents=True)
    existing = {
        "model": "opus",
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": "/my/own/hook.sh"}]}]
        },
    }
    (claude_dir / "settings.json").write_text(json.dumps(existing))

    run_setup(mcp=False)
    settings = _read_settings(claude_dir)

    assert settings["model"] == "opus"  # untouched
    start = settings["hooks"]["SessionStart"]
    cmds = [hk["command"] for entry in start for hk in entry["hooks"]]
    assert "/my/own/hook.sh" in cmds  # user hook preserved
    assert any("trovex-boot.sh" in c for c in cmds)  # ours appended


def test_setup_does_not_clobber_invalid_json(claude_dir):
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text("{ not valid json ")
    rc = run_setup(mcp=False)
    assert rc == 0  # never crashes
    # left as-is rather than overwritten
    assert (claude_dir / "settings.json").read_text() == "{ not valid json "


def test_setup_no_hooks_flag(claude_dir):
    run_setup(hooks=False, mcp=False)
    assert (claude_dir / "skills" / "trovex" / "SKILL.md").is_file()
    assert not (claude_dir / "hooks" / "trovex").exists()
    assert not (claude_dir / "settings.json").exists()
