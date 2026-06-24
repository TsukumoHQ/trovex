#!/usr/bin/env bash
# trovex-sessionend.sh — Claude Code SessionEnd hook (Active Memory step 4).
# GUARANTEED final capture: SessionEnd fires on kill/crash/logout (Stop does
# NOT). Ships the transcript; the server LLM-distils it (merged with the agent's
# prior state) into owner/<agent>'s current-state record — the fallback for
# sessions that never compacted (no free PostCompact summary).
#
# BYOK: needs TROVEX_OPENAI_KEY for the distil; no key → server no-ops the
# distil. No-op silently if trovex is down. Keep it fast (SessionEnd budget is
# tight; raise via CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS if needed).
set -euo pipefail
command -v jq >/dev/null 2>&1 || exit 0
TROVEX="${TROVEX_URL:-http://127.0.0.1:8765}"
AGENT="${TROVEX_AGENT:-$(basename "$PWD")}"
IN="$(cat)"
TPATH="$(jq -r '.transcript_path // empty' <<<"$IN")"
[ -n "$TPATH" ] && [ -f "$TPATH" ] || exit 0
jq -Rs --arg a "$AGENT" '{agent:$a, transcript:., reason:"sessionend"}' < "$TPATH" \
 | curl -fsS -m 15 -X POST "$TROVEX/api/capture" \
        -H 'Content-Type: application/json' \
        ${TROVEX_OPENAI_KEY:+-H "x-trovex-openai-key: $TROVEX_OPENAI_KEY"} \
        ${TROVEX_WRITE_TOKEN:+-H "x-trovex-write-token: $TROVEX_WRITE_TOKEN"} \
        -d @- >/dev/null 2>&1 || true
