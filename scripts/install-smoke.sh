#!/usr/bin/env bash
# Cold-install activation gate (TSU-220), pulled out of the deleted
# .github/workflows/core.yml `install-smoke` job (task 819445bf: no GitHub
# Actions on private repos). Proves a COLD install works from the built wheel
# (not the editable tree): assets ship, the console script runs, and
# `trovex setup` lands the skill + hooks + settings on a fresh
# CLAUDE_CONFIG_DIR, idempotently.
#
# Run manually before tagging a release: bash scripts/install-smoke.sh
set -euo pipefail
cd "$(dirname "$0")/.."

venv=$(mktemp -d)/venv
cfg=$(mktemp -d)/cc
trap 'rm -rf "$(dirname "$venv")" "$(dirname "$cfg")"' EXIT

echo "== build wheel =="
rm -f dist/*.whl
uv build --wheel -o dist

echo "== install wheel into a clean venv =="
# pyproject requires-python >=3.11 -- plain `python3 -m venv` uses whatever
# python3 is first on PATH (e.g. the macOS system 3.9), which fails the pip
# install with a confusing ResolutionImpossible/no-matching-distribution
# error instead of a clear version message. uv provisions/uses a real 3.11.
uv venv --python 3.11 --seed --quiet "$venv"
"$venv/bin/pip" install --quiet dist/*.whl

echo "== trovex setup on a fresh CLAUDE_CONFIG_DIR (no mcp) =="
CLAUDE_CONFIG_DIR="$cfg" "$venv/bin/trovex" setup --no-mcp
test -f "$cfg/skills/trovex/SKILL.md"
test -x "$cfg/hooks/trovex/trovex-boot.sh"
test -x "$cfg/hooks/trovex/trovex-prompt.sh"
test -x "$cfg/hooks/trovex/trovex-postcompact.sh"
CLAUDE_CONFIG_DIR="$cfg" python3 - <<'PY'
import json, os
d = json.load(open(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "settings.json")))
ev = d["hooks"]
for k in ("SessionStart", "UserPromptSubmit", "PostCompact"):
    assert k in ev, f"missing hook event {k}"
    cmds = [h["command"] for e in ev[k] for h in e["hooks"]]
    assert any("trovex" in c for c in cmds), f"no trovex hook for {k}"
print("settings.json OK")
PY

echo "== idempotent re-run (must exit 0, no duplication) =="
CLAUDE_CONFIG_DIR="$cfg" "$venv/bin/trovex" setup --no-mcp
CLAUDE_CONFIG_DIR="$cfg" python3 - <<'PY'
import json, os
d = json.load(open(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "settings.json")))
for k in ("SessionStart", "UserPromptSubmit", "PostCompact"):
    assert len(d["hooks"][k]) == 1, f"duplicated {k} on re-run"
print("idempotent OK")
PY

echo "install-smoke: PASS"
