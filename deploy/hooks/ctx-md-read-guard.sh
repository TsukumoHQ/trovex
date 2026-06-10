#!/usr/bin/env bash
# ctx-md-read-guard — Claude Code PreToolUse hook (read side).
#
# Nudges agents to retrieve docs via ctx_search/ctx_read instead of reading a
# .md straight off disk — those files are now duplicates of the ctx store, so
# reading them raw means stale content + no chunk-level token savings.
# .ctxignore exempts files you legitimately read raw (README, CLAUDE.md, code-
# coupled docs). Degrades to ALLOW when ctx is unreachable or jq is missing.
#
# More aggressive than the write-guard (path->query is lossy), so it's opt-in:
#   "hooks": { "PreToolUse": [ { "matcher": "Read",
#     "hooks": [ { "type": "command",
#                  "command": "/abs/path/ctx-md-read-guard.sh" } ] } ] }
set -euo pipefail

CTX_URL="${CTX_URL:-https://ctx.prod.synergix.ch}"

allow() { exit 0; }

command -v jq >/dev/null 2>&1 || allow

input="$(cat)"
tool="$(printf '%s' "$input" | jq -r '.tool_name // empty')"
case "$tool" in Read) ;; *) allow ;; esac

file="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')"
[ -n "$file" ] || allow
case "$file" in *.md | *.mdx | *.markdown) ;; *) allow ;; esac

# .ctxignore — files exempt from the proxy (read raw off disk).
root="$(git -C "$(dirname "$file")" rev-parse --show-toplevel 2>/dev/null || pwd)"
ignore="$root/.ctxignore"
if [ -f "$ignore" ]; then
  rel="${file#"$root"/}"
  while IFS= read -r pat || [ -n "$pat" ]; do
    [ -z "$pat" ] && continue
    case "$pat" in \#*) continue ;; esac
    # shellcheck disable=SC2254
    case "$rel" in $pat) allow ;; esac
    # shellcheck disable=SC2254
    case "$file" in $pat) allow ;; esac
  done <"$ignore"
fi

# Graceful degradation: ctx down -> don't block reads.
curl -fsS -m 2 "$CTX_URL/healthz" >/dev/null 2>&1 || allow

reason="ctx centralizes docs — '$file' lives in the store. Prefer ctx_search(query=…) for a token-minimal passage, or ctx_read. To read THIS raw file anyway, add its path to .ctxignore."

jq -cn --arg r "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $r
  }
}'
exit 0
