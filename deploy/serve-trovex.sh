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
#   deploy/serve-trovex.sh                 # fetch origin, detach at origin/main, uv sync, (re)start
#   deploy/serve-trovex.sh --no-refresh    # just restart the current checkout (no git/uv)
#   deploy/serve-trovex.sh --dry-run       # print what it would do, change nothing
#   deploy/serve-trovex.sh --install-launchd  # install the KeepAlive LaunchAgent (survive reboot)
#   deploy/serve-trovex.sh --exec          # foreground exec (launchd entrypoint — not for humans)
#
# Durable relaunch (survive a reboot without a human): run --install-launchd ONCE.
# It installs a per-user LaunchAgent (com.tsukumo.trovex-serve) with RunAtLoad +
# KeepAlive, so the server comes back on login/reboot and is restarted if it dies.
# After a `main` merge, run the plain `serve-trovex.sh` (refresh) — if the agent is
# installed it `launchctl kickstart`s the supervised process onto the fresh checkout
# instead of spawning an unsupervised nohup.
# The macOS box uses launchd; the Linux box uses deploy/trovex.service (systemd).
#
# Env overrides:
#   TROVEX_SERVE_WORKTREE   serve-worktree dir (default: ~/.config/trovex-growth/deploy-wt/trovex)
#   TROVEX_PORT             port to serve/health-check (default: 8765)
#   TROVEX_ENV_FILE         BYOK env file sourced for OPENAI_API_KEY (default: ~/.config/trovex-growth/openai.env)
set -euo pipefail

WORKTREE="${TROVEX_SERVE_WORKTREE:-$HOME/.config/trovex-growth/deploy-wt/trovex}"
PORT="${TROVEX_PORT:-8765}"
# `trovex serve` takes host/port as CLI OPTIONS whose defaults (127.0.0.1 / 8765)
# are the SAFE end-user defaults and deliberately do NOT read TROVEX_HOST/TROVEX_PORT
# — so this fleet launcher must pass them as explicit FLAGS, not env vars, to bind
# the LAN interface dokan containers need (host.docker.internal can't reach a
# 127.0.0.1 bind). Keep the env vars unset on a normal end-user box → BIND_HOST 0.0.0.0
# is the FLEET-HOST choice, safe only because the MCP transport is host-gated.
BIND_HOST="${TROVEX_HOST:-0.0.0.0}"
LOG="$HOME/.trovex-data/serve.log"
ENV_FILE="${TROVEX_ENV_FILE:-$HOME/.config/trovex-growth/openai.env}"
LABEL="com.tsukumo.trovex-serve"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
GUI="gui/$(id -u)"

# Source the BYOK key file so the embedder/rerank have OPENAI_API_KEY. CRUCIAL under
# launchd: a LaunchAgent starts with an EMPTY environment, so a key that lives only
# in an interactive shell is gone — without this the server boots keyless and the
# embedder raises "OpenAI embedder needs a key". Never echo the contents.
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

# Owner/hosted opt-in to OpenAI embeddings. The SHIPPED default is local ONNX
# (BAAI/bge-small-en-v1.5, 384 dims) so end users stay fully local with no key —
# that is the honest out-of-box behaviour. THIS instance is a deliberately-keyed
# BYOK demo box, so we pin the high-retrieval OpenAI model. Pinning also keeps the
# vector dimension at 3072, matching the already-indexed ~/.trovex-data store: if
# the default flipped to 384 on restart, knn would mismatch the existing table.
# Override TROVEX_EMBED_MODEL upstream to change. Needs OPENAI_API_KEY (sourced above).
export TROVEX_EMBED_MODEL="${TROVEX_EMBED_MODEL:-text-embedding-3-large}"

refresh=1
dry=0
exec_mode=0
install=0
for arg in "$@"; do
  case "$arg" in
    --no-refresh) refresh=0 ;;
    --dry-run) dry=1 ;;
    --exec) exec_mode=1; refresh=0 ;;
    --install-launchd) install=1 ;;
    -h | --help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg (try --help)" >&2; exit 2 ;;
  esac
done

run() { if [ "$dry" = 1 ]; then echo "DRY: $*"; else "$@"; fi; }

# --install-launchd: write the LaunchAgent plist, (re)bootstrap it, kickstart it.
# The agent runs THIS script with `--no-refresh --exec` so launchd supervises the
# real `trovex serve` process (foreground exec), not a detached nohup it can't see.
if [ "$install" = 1 ]; then
  self="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  run mkdir -p "$HOME/Library/LaunchAgents"
  if [ "$dry" = 1 ]; then
    echo "DRY: write $PLIST (RunAtLoad+KeepAlive → bash $self --no-refresh --exec)"
    echo "DRY: launchctl bootout $GUI/$LABEL; launchctl bootstrap $GUI $PLIST; launchctl kickstart -k $GUI/$LABEL"
    exit 0
  fi
  cat >"$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$self</string>
    <string>--no-refresh</string>
    <string>--exec</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin</string>
    <key>HOME</key><string>$HOME</string>
  </dict>
</dict>
</plist>
PLIST_EOF
  echo "→ installed LaunchAgent → $PLIST"
  # bootout is ASYNC — on a RE-install the label can still be loaded when bootstrap
  # runs, which fails with "Bootstrap failed: 5: Input/output error" and leaves NO
  # service (the bootout already tore down the old one). Wait until it's gone first.
  launchctl bootout "$GUI/$LABEL" 2>/dev/null || true
  for _ in $(seq 1 30); do
    launchctl print "$GUI/$LABEL" >/dev/null 2>&1 || break
    sleep 0.3
  done
  launchctl bootstrap "$GUI" "$PLIST"
  launchctl kickstart -k "$GUI/$LABEL"
  if curl -fsS --retry 25 --retry-delay 1 --retry-all-errors -m 5 \
       "http://localhost:$PORT/healthz" >/dev/null; then
    echo "✓ trovex-serve LaunchAgent live on :$PORT (RunAtLoad+KeepAlive), log → $LOG"
  else
    echo "✗ /healthz did not come up — check $LOG and 'launchctl print $GUI/$LABEL'" >&2
    exit 1
  fi
  exit 0
fi

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

# Stop whatever currently holds the port (the previous serve), if anything — UNLESS
# the launchd agent owns it and we're about to kickstart (launchctl handles the swap).
serve_env() { echo TROVEX_ALLOW_UNAUTH_WRITES=1; }
agent_loaded() { launchctl print "$GUI/$LABEL" >/dev/null 2>&1; }

stop_port_listener() {
  old_pid="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)"
  if [ -n "$old_pid" ]; then
    echo "→ stopping current :$PORT listener (pid $old_pid)"
    run kill "$old_pid"
    # Wait (bounded) for the port to actually free before we rebind, else uvicorn
    # fails to bind and exits.
    if [ "$dry" != 1 ]; then
      for _ in $(seq 1 50); do
        lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1 || break
        sleep 0.1
      done
    fi
  fi
}

# --exec: launchd's entrypoint. Foreground exec so launchd supervises the real
# server (KeepAlive watches THIS pid). No nohup, no healthcheck — launchd owns both.
if [ "$exec_mode" = 1 ]; then
  stop_port_listener
  echo "→ exec trovex serve --host $BIND_HOST --port $PORT (unauth-writes) under launchd"
  exec env TROVEX_ALLOW_UNAUTH_WRITES=1 \
    .venv/bin/trovex serve --host "$BIND_HOST" --port "$PORT"
fi

echo "→ launching trovex serve --host $BIND_HOST --port $PORT (unauth-writes)"
if [ "$dry" = 1 ]; then
  if agent_loaded; then
    echo "DRY: launchctl kickstart -k $GUI/$LABEL  (agent supervises the swap)"
  else
    echo "DRY: $(serve_env) nohup .venv/bin/trovex serve --host $BIND_HOST --port $PORT >> $LOG 2>&1 &"
  fi
elif agent_loaded; then
  # The LaunchAgent owns the process — restart it onto the fresh checkout instead of
  # spawning an unsupervised nohup that would fight KeepAlive for the port.
  echo "→ launchd agent installed → kickstart $LABEL"
  launchctl kickstart -k "$GUI/$LABEL"
  if curl -fsS --retry 25 --retry-delay 1 --retry-all-errors -m 5 \
       "http://localhost:$PORT/healthz" >/dev/null; then
    echo "✓ trovex serving on :$PORT via launchd ($(git rev-parse --short HEAD)), log → $LOG"
  else
    echo "✗ /healthz did not come up — check $LOG and 'launchctl print $GUI/$LABEL'" >&2
    exit 1
  fi
else
  stop_port_listener
  TROVEX_ALLOW_UNAUTH_WRITES=1 \
    nohup .venv/bin/trovex serve --host "$BIND_HOST" --port "$PORT" >>"$LOG" 2>&1 &
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
