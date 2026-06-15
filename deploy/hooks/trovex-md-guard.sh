#!/usr/bin/env bash
# trovex-md-guard — Claude Code PreToolUse hook.
#
# Routes Markdown writes through trovex instead of the local disk, so every agent
# (and the second dev) shares one source of truth. Blocks a Write/Edit to a
# *.md file unless its path is listed in .trovexignore, and tells the agent to use
# the trovex_write MCP tool instead.
#
# Degrades to ALLOW when trovex is unreachable or jq is missing — a trovex outage
# must never brick the agent (the store is centralized, the enforcement isn't).
#
# Install (project .claude/settings.json):
#   "hooks": { "PreToolUse": [ { "matcher": "Write|Edit|MultiEdit",
#     "hooks": [ { "type": "command",
#                  "command": "/abs/path/to/trovex-md-guard.sh" } ] } ] }
set -euo pipefail

TROVEX_URL="${TROVEX_URL:-https://trovex.prod.synergix.ch}"

allow() { exit 0; }   # emit nothing = let the write through

command -v jq >/dev/null 2>&1 || allow

input="$(cat)"
tool="$(printf '%s' "$input" | jq -r '.tool_name // empty')"
case "$tool" in Write | Edit | MultiEdit) ;; *) allow ;; esac

file="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')"
[ -n "$file" ] || allow
case "$file" in *.md | *.mdx | *.markdown) ;; *) allow ;; esac

# .trovexignore — zone franche: any matching path stays a real file on disk.
root="$(git -C "$(dirname "$file")" rev-parse --show-toplevel 2>/dev/null || pwd)"
ignore="$root/.trovexignore"
if [ -f "$ignore" ]; then
  rel="${file#"$root"/}"
  while IFS= read -r pat || [ -n "$pat" ]; do
    [ -z "$pat" ] && continue
    case "$pat" in \#*) continue ;; esac
    # shellcheck disable=SC2254  # intentional glob from the file
    case "$rel" in $pat) allow ;; esac
    # shellcheck disable=SC2254
    case "$file" in $pat) allow ;; esac
  done <"$ignore"
fi

# Graceful degradation: trovex down → don't block.
curl -fsS -m 2 "$TROVEX_URL/healthz" >/dev/null 2>&1 || allow

reason="trovex centralizes docs — don't write '$file' to disk. Use the trovex_write MCP tool (kind=\"record\" for incidents/decisions/post-mortems) so every agent and the other dev sees one source of truth. To keep THIS file on disk instead, add its path to .trovexignore."

jq -cn --arg r "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $r
  }
}'
exit 0
