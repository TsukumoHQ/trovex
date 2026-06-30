#!/usr/bin/env bash
# trovex-boot.sh — Claude Code SessionStart hook (Active Memory step 2).
# Injects the agent's own recent records as ~80 tokens of pointers, so a fresh
# session resumes instead of re-deriving. Re-fires on source=compact too, which
# is the post-compaction re-surface point. Degrades to a silent no-op if trovex
# is down — a trovex outage must NEVER block the agent.
set -euo pipefail
command -v jq >/dev/null 2>&1 || exit 0
TROVEX="${TROVEX_URL:-http://127.0.0.1:8765}"
AGENT="${TROVEX_AGENT:-$(basename "$PWD")}"   # or map cwd / git-remote → agent
render="$(curl -fsS -m 2 "$TROVEX/api/boot?agent=$AGENT" 2>/dev/null \
          | jq -r '.render // empty')" || exit 0
[ -z "$render" ] && exit 0                      # nothing scoped → inject nothing
jq -cn --arg c "$render" \
  '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$c}}'
