#!/usr/bin/env bash
# trovex-prompt.sh — Claude Code UserPromptSubmit hook (Active Memory step 2).
# Recall scoped to the actual task text: passes the prompt as q=, so retrieval
# targets THIS task instead of a generic boot query. Better targeting than
# SessionStart's generic pack. Silent no-op if trovex is down or nothing scoped.
set -euo pipefail
command -v jq >/dev/null 2>&1 || exit 0
TROVEX="${TROVEX_URL:-http://127.0.0.1:8765}"
AGENT="${TROVEX_AGENT:-$(basename "$PWD")}"
PROMPT="$(jq -r '.prompt // empty' <<<"$(cat)")"
[ -n "$PROMPT" ] || exit 0
Q="$(jq -rn --arg p "$PROMPT" '$p|@uri')"
render="$(curl -fsS -m 2 "$TROVEX/api/boot?agent=$AGENT&k=3&q=$Q" 2>/dev/null \
          | jq -r '.render // empty')" || exit 0
[ -z "$render" ] && exit 0
jq -cn --arg c "$render" \
  '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}'
