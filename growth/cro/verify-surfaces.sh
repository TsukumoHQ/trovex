#!/usr/bin/env bash
# Conversion-surface health check: curl the live money surfaces + grep for the
# markers that prove each is up and on-brand. Catches regressions from any lead's
# merge without me hand-curling each loop. Deterministic-first (20/80).
# Usage: bash growth/cro/verify-surfaces.sh
set -uo pipefail

pass=0; fail=0
ck() { # label url grep_marker(optional)
  local label="$1" url="$2" want="${3:-}"
  local code body
  code=$(curl -s -o /dev/null -w "%{http_code}" -L "$url")
  if [ "$code" != "200" ]; then printf "FAIL  %-26s %s (HTTP %s)\n" "$label" "$url" "$code"; fail=$((fail+1)); return; fi
  if [ -n "$want" ]; then
    body=$(curl -s "$url")
    if ! grep -q "$want" <<<"$body"; then printf "FAIL  %-26s %s (missing: %s)\n" "$label" "$url" "$want"; fail=$((fail+1)); return; fi
  fi
  printf "ok    %-26s %s\n" "$label" "$url"; pass=$((pass+1))
}

echo "== trovex.dev =="
ck "landing"        "https://trovex.dev/"
ck "for/claude-code" "https://trovex.dev/for/claude-code/" "qs-aha"
ck "for/quickstart.js" "https://trovex.dev/for/quickstart.js" "command_copied"
ck "newsletter API"  "https://trovex.dev/" # endpoint POST-only; landing carries the form

echo "== tsukumo.ch (lead path) =="
ck "consulting"     "https://tsukumo.ch/consulting"
ck "assessment"     "https://tsukumo.ch/assessment"
ck "wraith (violet)" "https://tsukumo.ch/wraith" "wraith-scope"

echo "-- $pass ok, $fail fail --"
[ "$fail" -eq 0 ]
