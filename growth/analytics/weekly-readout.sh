#!/usr/bin/env bash
# Weekly north-star readout — ONE repeatable command (task f472cb1b).
#
# Sources every credential the readout needs (the gap that made the consulting
# pipeline read a false `n/a`: the scoreboard reads Twenty, but twenty.env was
# never loaded), refreshes GitHub suite reach, then prints the one-screen
# north-star scoreboard (reach -> consulting leads, activation funnel, GEO panel,
# 4-engine citation panel) to STDOUT.
#
# Honesty contract is inherited from the underlying scripts: a missing key/source
# degrades that panel to `n/a`, a real zero reads `0`. Nothing is fabricated.
#
# Output: STDOUT = the readout markdown (owner rule "rien en md, tout dans trovex"
# -> pipe into the trovex store). STDERR = progress + a one-line summary.
# Disk reports stay OFF by default; the scripts only write when passed --save.
#
# Usage:
#   growth/analytics/weekly-readout.sh                 # cumulative since launch floor
#   growth/analytics/weekly-readout.sh --since 2026-06-22
#   growth/analytics/weekly-readout.sh --reach         # also refresh GitHub reach first
#
# Scheduling (repeatable weekly + post to cmo) is wired separately once the
# mechanism is chosen (launchd local vs cloud routine) — this script is the unit
# that wrapper runs.
set -uo pipefail

CFG="${TROVEX_GROWTH_ENV_DIR:-$HOME/.config/trovex-growth}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load every credential file that exists (env-only, never printed/committed).
# Missing file -> that panel degrades to n/a downstream; we never fail on it.
set -a
for f in plausible supabase twenty ai-engines; do
  [ -f "$CFG/$f.env" ] && . "$CFG/$f.env"
done
set +a

# Report which credentials are present (names only, never values).
{
  echo "weekly-readout: creds ->"
  echo "  plausible: $([ -n "${PLAUSIBLE_STATS_API_KEY:-}" ] && echo live || echo 'n/a')  site=${PLAUSIBLE_SITE_ID:-unset}"
  echo "  supabase:  $([ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ] && echo live || echo 'n/a')"
  echo "  twenty:    $([ -n "${TWENTY_API_KEY:-}" ] && echo live || echo 'n/a')   (Panel A = the consulting pipeline)"
  echo "  ai-engines:$([ -n "${OPENAI_API_KEY:-}${PERPLEXITY_API_KEY:-}" ] && echo 'some' || echo 'n/a')  (citation panel run is separate/rate-limited)"
} >&2

REACH=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --reach) REACH=1 ;;
    *) ARGS+=("$a") ;;
  esac
done

# Optionally refresh GitHub suite reach (14d traffic window; GitHub only retains
# 14d, so a weekly pull IS the archive). Best-effort; never blocks the readout.
if [ "$REACH" = 1 ]; then
  echo "weekly-readout: refreshing GitHub suite reach..." >&2
  node "$HERE/github-suite-reach.mjs" >/dev/null 2>&1 || echo "weekly-readout: reach refresh n/a (gh CLI?)" >&2
fi

# The one-screen scoreboard -> STDOUT. Its own stderr carries the summary line.
node "$HERE/north-star-scoreboard.mjs" "${ARGS[@]:-}"
