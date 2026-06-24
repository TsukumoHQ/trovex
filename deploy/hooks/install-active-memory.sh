#!/usr/bin/env bash
# install-active-memory.sh — wire one agent into trovex Active Memory.
#
# Fetches the recall + free-capture hooks to ~/.claude/hooks/trovex/ and prints
# the exact settings.json snippet to merge. Print-only by design — it never
# edits your settings.json (don't auto-clobber a fleet of configs). Idempotent.
#
#   TROVEX_AGENT=<your-agent-name> bash <(curl -fsS http://127.0.0.1:8765/hooks/install-active-memory.sh)
#
# Recall: SessionStart (boot pack) + UserPromptSubmit (task-scoped). Capture:
# PostCompact (free summary → owner/<agent>+kind=record). SessionEnd distil =
# step 4 (later). All hooks no-op silently if trovex is down.
set -euo pipefail

TROVEX="${TROVEX_URL:-http://127.0.0.1:8765}"
AGENT="${TROVEX_AGENT:-}"
[ -n "$AGENT" ] || { echo "ERROR: set TROVEX_AGENT=<your agent name> first." >&2; exit 1; }

DEST="$HOME/.claude/hooks/trovex"
mkdir -p "$DEST"
for h in trovex-boot.sh trovex-prompt.sh trovex-postcompact.sh; do
  if curl -fsS -m 5 "$TROVEX/hooks/$h" -o "$DEST/$h"; then
    chmod +x "$DEST/$h"
    echo "fetched $h"
  else
    echo "WARN: could not fetch $h (is trovex up at $TROVEX?)" >&2
  fi
done

cat <<JSON

── Done. Two steps to finish ───────────────────────────────────────────────
1. Export your agent identity (your shell / agent env):
     export TROVEX_AGENT="$AGENT"

2. Merge into ~/.claude/settings.json under "hooks" (keep any existing hooks):
{
  "hooks": {
    "SessionStart":     [{ "hooks": [{ "type": "command", "command": "$DEST/trovex-boot.sh" }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "$DEST/trovex-prompt.sh" }] }],
    "PostCompact":      [{ "hooks": [{ "type": "command", "command": "$DEST/trovex-postcompact.sh" }] }]
  }
}
────────────────────────────────────────────────────────────────────────────
Recall surfaces docs tagged owner/$AGENT + kind=record. Write your state there
(trovex_write kind=record tags=["owner/$AGENT","type/current-state"]) — or let
PostCompact capture it for you. Verify: curl "$TROVEX/api/boot?agent=$AGENT"
JSON
