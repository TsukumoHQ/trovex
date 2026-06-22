#!/usr/bin/env bash
# render.sh — deterministic wrapper for the satori card generators (20/80 rule,
# memory 20-80-deterministic-first). The mechanical 80% of every render — symlink
# the deps the worktree lacks, load the Supabase creds, run the gen, clean up the
# symlink even on failure — is the same dance every cycle. Script it once; the agent
# keeps its tokens for the irreducible 20% (the spec, the copy, the taste call).
#
# Usage:
#   growth/assets/_tools/render.sh gen_carousel.mjs growth/social/carousels/<slug>.json
#   growth/assets/_tools/render.sh gen_carousel.mjs --no-upload --out /tmp/r growth/social/carousels/<slug>.json
#   growth/assets/_tools/render.sh gen_blog_cover.mjs <slug>
#   growth/assets/_tools/render.sh gen_answer_cards.mjs
#
# Deps source = the fullstack-lead worktree's web/node_modules (satori + resvg live
# there; never commit a node_modules into this worktree). Creds load is best-effort:
# gens that upload need supabase.env present; --no-upload runs without it.
set -euo pipefail

ROOT="${DESIGN_WORKTREE:-$HOME/Projects/trovex/.worktrees/design-lead}"
DEPS="${RENDER_DEPS:-$HOME/Projects/trovex/.worktrees/fullstack-lead/web/node_modules}"
CREDS="$HOME/.config/trovex-growth/supabase.env"

[ $# -ge 1 ] || { echo "usage: render.sh <gen.mjs> [args...]" >&2; exit 2; }
GEN="$1"; shift
[ -d "$DEPS" ] || { echo "deps not found: $DEPS (set RENDER_DEPS)" >&2; exit 1; }
[ -f "$ROOT/growth/assets/_tools/$GEN" ] || { echo "no such gen: $GEN" >&2; exit 1; }

cd "$ROOT"

# preflight: carousel specs go through the deterministic copy lint first (de-em-dash,
# public-beta phrasing, no Synergix). A bad spec fails BEFORE it renders + uploads.
if [ "$GEN" = "gen_carousel.mjs" ]; then
  specs=(); for a in "$@"; do [ "${a##*.}" = "json" ] && specs+=("$a"); done
  [ ${#specs[@]} -gt 0 ] && node "growth/assets/_tools/lint_spec.mjs" "${specs[@]}"
fi

ln -sfn "$DEPS" ./node_modules
trap 'rm -f ./node_modules' EXIT

# best-effort creds (upload paths need them; --no-upload does not)
if [ -f "$CREDS" ]; then set -a; . "$CREDS"; set +a; fi

node "growth/assets/_tools/$GEN" "$@"
