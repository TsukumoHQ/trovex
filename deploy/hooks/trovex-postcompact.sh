#!/usr/bin/env bash
# trovex-postcompact.sh — Claude Code PostCompact hook (Active Memory step 3).
# Captures the compaction summary trovex gets for FREE (no LLM) into the agent's
# current-state record, so the next /api/boot recalls fresh state instead of a
# stale resume. No-op silently if trovex is down — never block the agent.
set -euo pipefail
command -v jq >/dev/null 2>&1 || exit 0
TROVEX="${TROVEX_URL:-http://127.0.0.1:8765}"
AGENT="${TROVEX_AGENT:-$(basename "$PWD")}"
IN="$(cat)"
SUM="$(jq -r '.compact_summary // empty' <<<"$IN")"
[ -n "$SUM" ] || exit 0
jq -cn --arg a "$AGENT" --arg s "$SUM" '{agent:$a, summary:$s, reason:"postcompact"}' \
 | curl -fsS -m 4 -X POST "$TROVEX/api/capture" \
        -H 'Content-Type: application/json' \
        ${TROVEX_WRITE_TOKEN:+-H "x-trovex-write-token: $TROVEX_WRITE_TOKEN"} \
        -d @- >/dev/null 2>&1 || true
