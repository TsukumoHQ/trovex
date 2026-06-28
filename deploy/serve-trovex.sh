#!/usr/bin/env bash
# serve-trovex — refresh + (re)launch the fleet's live :8765 trovex server from a
# DEDICATED serve-worktree pinned to origin/main, so the live server never drifts
# onto a stale dev branch again (root cause of the TSU-76/77 staleness).
#
# This is the macOS FLEET-HOST launcher (the Linux box uses deploy/trovex.service).
# It pins the two env vars the fleet needs and that a hand-run refresh keeps
# forgetting:
#   • TROVEX_ALLOW_UNAUTH_WRITES=1 — fleet MCP clients send only X-TROVEX-User, no
#     write token; without this, main's write-token gate blocks every trovex_write.
#     Safe here: the MCP transport is already host-gated (DNS-rebind allowed_hosts =
#     localhost + host.docker.internal), so unauth writes stay host-local.
#   • TROVEX_HOST=0.0.0.0 — dokan CONTAINERS write via host.docker.internal:8765,
#     which does NOT resolve to loopback; a 127.0.0.1 bind would break them. (The
#     127.0.0.1 default from #671 is correct for end users, wrong for this host.)
#
# Usage:
#   deploy/serve-trovex.sh                 # fetch origin, detach at origin/main, uv sync, restart
#   deploy/serve-trovex.sh --no-refresh    # just restart the current checkout (no git/uv)
#   deploy/serve-trovex.sh --dry-run       # print what it would do, change nothing
#
# Env overrides:
#   TROVEX_SERVE_WORKTREE   serve-worktree dir (default: ~/.config/trovex-growth/deploy-wt/trovex)
#   TROVEX_PORT             port to serve/health-check (default: 8765)
set -euo pipefail

WORKTREE="${TROVEX_SERVE_WORKTREE:-$HOME/.config/trovex-growth/deploy-wt/trovex}"
PORT="${TROVEX_PORT:-8765}"
LOG="$HOME/.trovex-data/serve.log"

refresh=1
dry=0
for arg in "$@"; do
  case "$arg" in
    --no-refresh) refresh=0 ;;
    --dry-run) dry=1 ;;
    -h | --help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg (try --help)" >&2; exit 2 ;;
  esac
done

run() { if [ "$dry" = 1 ]; then echo "DRY: $*"; else "$@"; fi; }

# A git worktree's .git is a FILE (gitdir pointer), not a dir — probe with git itself.
git -C "$WORKTREE" rev-parse --git-dir >/dev/null 2>&1 ||
  { echo "serve-worktree not a git repo: $WORKTREE" >&2; exit 1; }
cd "$WORKTREE"

if [ "$refresh" = 1 ]; then
  echo "→ refreshing $WORKTREE to origin/main"
  run git fetch origin --quiet
  run git checkout --detach origin/main --quiet
  run git -c advice.detachedHead=false reset --hard origin/main --quiet
  echo "→ uv sync"
  run uv sync --quiet
fi

# Stop whatever currently holds the port (the previous serve), if anything.
old_pid="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)"
if [ -n "$old_pid" ]; then
  echo "→ stopping current :$PORT listener (pid $old_pid)"
  run kill "$old_pid"
fi

echo "→ launching trovex serve (host 0.0.0.0, unauth-writes, port $PORT)"
if [ "$dry" = 1 ]; then
  echo "DRY: TROVEX_ALLOW_UNAUTH_WRITES=1 TROVEX_HOST=0.0.0.0 TROVEX_PORT=$PORT nohup .venv/bin/trovex serve >> $LOG 2>&1 &"
else
  TROVEX_ALLOW_UNAUTH_WRITES=1 TROVEX_HOST=0.0.0.0 TROVEX_PORT="$PORT" \
    nohup .venv/bin/trovex serve >>"$LOG" 2>&1 &
  disown
  new_pid=$!
  # Wait for /healthz, bounded — embedder warm-up can take a few seconds.
  if curl -fsS --retry 20 --retry-delay 1 --retry-all-errors -m 5 \
       "http://localhost:$PORT/healthz" >/dev/null; then
    echo "✓ trovex serving on :$PORT (pid $new_pid @ $(git rev-parse --short HEAD)), log → $LOG"
  else
    echo "✗ /healthz did not come up — check $LOG" >&2
    exit 1
  fi
fi
