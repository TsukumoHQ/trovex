#!/usr/bin/env bash
# trovex-md-read-guard — Claude Code PreToolUse hook (read side).
#
# Nudges agents to retrieve docs via trovex_search/trovex_read instead of reading a
# .md straight off disk — those files are now duplicates of the trovex store, so
# reading them raw means stale content + no chunk-level token savings.
# .trovexignore exempts files you legitimately read raw (README, CLAUDE.md, code-
# coupled docs). Degrades to ALLOW when trovex is unreachable or jq is missing.
#
# More aggressive than the write-guard (path->query is lossy), so it's opt-in:
#   "hooks": { "PreToolUse": [ { "matcher": "Read",
#     "hooks": [ { "type": "command",
#                  "command": "/abs/path/trovex-md-read-guard.sh" } ] } ] }
set -euo pipefail

TROVEX_URL="${TROVEX_URL:-http://localhost:8765}"

allow() { exit 0; }

command -v jq >/dev/null 2>&1 || allow

input="$(cat)"
tool="$(printf '%s' "$input" | jq -r '.tool_name // empty')"
case "$tool" in Read) ;; *) allow ;; esac

file="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')"
[ -n "$file" ] || allow
case "$file" in *.md | *.mdx | *.markdown) ;; *) allow ;; esac

# Scope: this guard owns ONLY the trovex repo's SSOT .md (see trovex-md-guard.sh).
# A SKILL.md or any .md in a foreign repo is not trovex SSOT — never proxy it (TSU-79).
case "$(basename "$file")" in SKILL.md) allow ;; esac
self_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd -P || true)"
trovex_root="$(git -C "$self_dir" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "$trovex_root" ]; then
  trovex_root="$(cd "$trovex_root" 2>/dev/null && pwd -P || printf '%s' "$trovex_root")"
  file_real="$(cd "$(dirname "$file")" 2>/dev/null && pwd -P || true)/$(basename "$file")"
  case "$file_real" in
    "$trovex_root"/*) ;;   # inside the trovex repo (incl. its worktrees) → keep guarding
    *) allow ;;            # outside trovex → not our SSOT, let it read
  esac
fi

# .trovexignore — files exempt from the proxy (read raw off disk).
root="$(git -C "$(dirname "$file")" rev-parse --show-toplevel 2>/dev/null || pwd)"
ignore="$root/.trovexignore"
if [ -f "$ignore" ]; then
  rel="${file#"$root"/}"
  while IFS= read -r pat || [ -n "$pat" ]; do
    pat="${pat%$'\r'}"   # strip trailing CR — .trovexignore checks out CRLF under
                          # autocrlf, and "README.md\r" never glob-matches → the guard
                          # would wrongly proxy every keep-list read. Parity with write-guard.
    [ -z "$pat" ] && continue
    case "$pat" in \#*) continue ;; esac
    # shellcheck disable=SC2254
    case "$rel" in $pat) allow ;; esac
    # shellcheck disable=SC2254
    case "$file" in $pat) allow ;; esac
  done <"$ignore"
fi

# Graceful degradation: trovex down -> don't block reads.
curl -fsS -m 2 "$TROVEX_URL/healthz" >/dev/null 2>&1 || allow

reason="trovex centralizes docs — '$file' lives in the store. Prefer trovex_search(query=…) for a token-minimal passage, or trovex_read. To read THIS raw file anyway, add its path to .trovexignore."

jq -cn --arg r "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $r
  }
}'
exit 0
