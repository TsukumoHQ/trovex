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
#
# Pre-write check (no compose round-trip wasted):
#   trovex-md-guard.sh --check <path>
#   → prints "ALLOW" (exit 0) or "DENY: <reason>" (exit 1), using the SAME
#     decision as the hook so a doer can ask BEFORE composing the doc.
set -euo pipefail

TROVEX_URL="${TROVEX_URL:-http://localhost:8765}"

# --- mode ----------------------------------------------------------------------
CHECK_MODE=0
file=""
if [ "${1:-}" = "--check" ]; then
  CHECK_MODE=1
  file="${2:-}"
  [ -n "$file" ] || { echo "usage: $(basename "$0") --check <path>" >&2; exit 2; }
fi

allow() {   # emit nothing (hook) / "ALLOW" (check) = let the write through
  [ "$CHECK_MODE" = "1" ] && echo "ALLOW"
  exit 0
}

# --- hook input (stdin JSON); check mode already has $file from argv ------------
if [ "$CHECK_MODE" = "0" ]; then
  command -v jq >/dev/null 2>&1 || allow
  input="$(cat)"
  tool="$(printf '%s' "$input" | jq -r '.tool_name // empty')"
  case "$tool" in Write | Edit | MultiEdit) ;; *) allow ;; esac
  file="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')"
fi
[ -n "$file" ] || allow
case "$file" in *.md | *.mdx | *.markdown) ;; *) allow ;; esac

# --- always-allow, regardless of .trovexignore ---------------------------------
# SKILL.md is a disk persona (never SSOT). The niwa review gate REQUIRES its
# artifacts to exist on disk in the worktree — the decision doc (.niwa-decision.md),
# feature docs, and anything under a .niwa/ workdir. Those are gate scaffolding,
# NOT project SSOT, so the doc-regime must never block them: doing so hard-stopped
# doers (they had to hand-add each to .trovexignore before the gate would run —
# e179d285). Matched by basename/path here so the exemption holds even in a repo
# whose .trovexignore predates this.
case "$(basename "$file")" in
  SKILL.md) allow ;;
  .niwa-decision.md | .niwa-*.md) allow ;;
esac
case "$file" in */.niwa/* | */.niwa) allow ;; esac

# --- scope: only repos under the trovex doc-regime -----------------------------
# Identified by a .trovexignore at the EDITED FILE's git root. Keyed on the file
# (NOT this script's location) so it works wherever the hook is INSTALLED — the old
# script-location probe returned empty once copied to ~/.claude/hooks (not a git
# repo) and then over-denied scratchpad + foreign .md (cto, 2026-06-28).
root="$(git -C "$(dirname "$file")" rev-parse --show-toplevel 2>/dev/null || true)"
ignore="${root:+$root/.trovexignore}"
# Not in a git repo (e.g. scratchpad), or a repo that hasn't opted into the regime
# (no .trovexignore) → not trovex SSOT, let it through.
[ -n "$ignore" ] && [ -f "$ignore" ] || allow

# .trovexignore — zone franche: any matching path stays a real file on disk.
if [ -f "$ignore" ]; then
  rel="${file#"$root"/}"
  while IFS= read -r pat || [ -n "$pat" ]; do
    pat="${pat%$'\r'}"   # strip trailing CR — autocrlf checks out .trovexignore as CRLF,
                          # and "README.md\r" never glob-matches → the guard would wrongly
                          # DENY every keep-list write (README/CLAUDE/blog). P1 footgun.
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

reason="trovex centralizes docs — don't write '$file' to disk. Use the trovex_write MCP tool (kind=\"record\" for incidents/decisions/post-mortems) so every agent and the other dev sees one source of truth. To keep THIS file on disk instead, add its path to .trovexignore (or run 'trovex-md-guard.sh --check <path>' before composing to see this in advance)."

# check mode: report the verdict as plain text, no hook JSON.
if [ "$CHECK_MODE" = "1" ]; then
  echo "DENY: $reason"
  exit 1
fi

jq -cn --arg r "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $r
  }
}'
exit 0
