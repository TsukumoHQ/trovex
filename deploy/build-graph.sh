#!/usr/bin/env bash
# build-graph — build the PRIVATE knowledge-graph SPA ("the codebase's brain")
# into web/dist-graph so `trovex serve` mounts it at /graph.
#
# WHY THIS EXISTS: src/trovex/server.py mounts /graph ONLY when web/dist-graph/
# exists (same build-less-tolerant contract as /receipt). The deploy paths
# (deploy/serve-trovex.sh refresh, deploy/trovex.service) refresh the Python
# server but never built the web SPA, so prod /graph never mounted. This is the
# single canonical build step both deploy paths call.
#
# Contract:
#   • No web/ dir or no npm on the box → skip cleanly (exit 0). /graph stays a
#     404, exactly as a build-less tree already tolerates — the server still boots.
#   • npm present but the build fails → exit non-zero (a real, detectable error).
#     Callers invoke this best-effort (serve-trovex.sh warns, trovex.service uses
#     ExecStartPre=- ) so a web hiccup never blocks the Python server coming up.
#
# Usage: deploy/build-graph.sh   (idempotent; safe to run on every refresh)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$ROOT/web"

if [ ! -d "$WEB" ]; then
  echo "→ build-graph: no web/ dir at $WEB — skipping /graph build"
  exit 0
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "→ build-graph: npm not found — skipping /graph build (/graph will 404 until built)"
  exit 0
fi

cd "$WEB"

# Prefer a reproducible install from the lockfile; fall back to `npm install` if a
# box somehow lacks package-lock.json. Needs devDeps (tsc/vite/graphology) — the
# graph build is dev-dependency-driven, so never pass --omit=dev here.
echo "→ build-graph: installing web deps"
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi

echo "→ build-graph: npm run build:graph → web/dist-graph"
npm run build:graph

if [ ! -f "$WEB/dist-graph/index.html" ]; then
  echo "✗ build-graph: web/dist-graph/index.html missing after build" >&2
  exit 1
fi
echo "✓ build-graph: web/dist-graph/index.html built — /graph will mount"
