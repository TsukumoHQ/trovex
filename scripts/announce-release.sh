#!/usr/bin/env bash
# Post a release announcement to Discord, pulled out of the deleted
# .github/workflows/announce-release.yml (task 819445bf: no GitHub Actions on
# private repos). Was tag-push-triggered; now run it by hand (or from a dokan
# schedule later) right after a GitHub Release is published for the tag.
#
# Usage: TAG=v0.16.0 DISCORD_RELEASE_WEBHOOK=... DISCORD_CHANGELOG_WEBHOOK=... \
#          bash scripts/announce-release.sh
# Requires: gh (authenticated), jq, curl.
set -euo pipefail

TAG="${TAG:?set TAG=vX.Y.Z}"
REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
RELEASE_WEBHOOK="${DISCORD_RELEASE_WEBHOOK:-}"
CHANGELOG_WEBHOOK="${DISCORD_CHANGELOG_WEBHOOK:-}"

if [ -z "$RELEASE_WEBHOOK" ] && [ -z "$CHANGELOG_WEBHOOK" ]; then
  echo "No Discord webhooks set — nothing to do." >&2
  exit 0
fi

rel=$(gh api "repos/${REPO}/releases/tags/${TAG}")
if [ "$(printf '%s' "$rel" | jq -r '.draft')" = "true" ] || [ "$(printf '%s' "$rel" | jq -r '.prerelease')" = "true" ]; then
  echo "Release ${TAG} is a draft/prerelease — skipping." >&2
  exit 0
fi
body=$(printf '%s' "$rel" | jq -r '.body // ""')
[ -z "$body" ] && body="New release: ${TAG}"

url="https://github.com/${REPO}/releases/tag/${TAG}"
ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

LOGO_BASE="https://bxdpevnqdnjcehewbiyg.supabase.co/storage/v1/object/public/media/assets/brand-kit"
case "$REPO" in
  *trovex)  BRAND="trovex";  SLUG="trovex"; COLOR=1098629;  SITE="https://trovex.dev"; INSTALL="uv tool upgrade trovex" ;;
  *dokan)   BRAND="dokan";   SLUG="dokan";  COLOR=440020;   SITE="https://github.com/${REPO}"; INSTALL="dokan update" ;;
  *WRAI.TH) BRAND="wrai.th"; SLUG="wraith"; COLOR=7236594;  SITE="https://wrai.th"; INSTALL="agent-relay update" ;;
  *yoru)    BRAND="yoru";    SLUG="yoru";   COLOR=16096779; SITE="https://yoru.sh"; INSTALL="yoru update" ;;
  *)        BRAND="${REPO##*/}"; SLUG="${REPO##*/}"; COLOR=5793266; SITE="https://github.com/${REPO}"; INSTALL="see release notes" ;;
esac
LOGO="${LOGO_BASE}/${SLUG}/social-avatar/avatar-400.png"

post() { [ -z "${1:-}" ] && return 0; curl -fsS -H "Content-Type: application/json" -d "$2" "$1" >/dev/null; }

hl=$(printf '%s\n' "$body" | awk '/^##[[:space:]]*[Hh]ighlights/{g=1;next} /^##[[:space:]]/{g=0} g' \
     | grep -E '^[[:space:]]*[-*][[:space:]]' | head -3 || true)
if [ -z "$hl" ]; then
  hl=$(printf '%s\n' "$body" | grep -E '^[[:space:]]*[-*][[:space:]]' \
       | grep -viE 'chore|ci:|docs|test|build:|refactor|style' | head -3 || true)
fi
hl=$(printf '%s\n' "$hl" | sed -E 's/^[[:space:]]*[-*][[:space:]]+/• /; s/\*\*//g; s/—/-/g' | head -c 1000 || true)
[ -z "$hl" ] && hl="New release is out."
install=$(printf '```\n%s\n```' "$INSTALL")

announce=$(jq -n --arg b "$BRAND" --arg tag "$TAG" --arg url "$url" --arg desc "$hl" \
  --arg install "$install" --arg ts "$ts" --arg logo "$LOGO" --arg site "$SITE" --arg repo "$REPO" --argjson color "$COLOR" \
  '{username:$b, avatar_url:$logo, embeds:[{author:{name:$b,url:$site,icon_url:$logo}, title:("🚀  "+$tag+" released"), url:$url, description:$desc, color:$color, thumbnail:{url:$logo}, fields:[{name:"Update",value:$install,inline:false},{name:"Links",value:("[Release notes]("+$url+")  ·  ["+$b+"]("+$site+")  ·  full log → #changelog"),inline:false}], footer:{text:$repo,icon_url:$logo}, timestamp:$ts}]}')
post "$RELEASE_WEBHOOK" "$announce"

desc=$(printf '%s' "$body" | head -c 4000)
changelog=$(jq -n --arg b "$BRAND" --arg tag "$TAG" --arg url "$url" --arg desc "$desc" --arg ts "$ts" --arg logo "$LOGO" --arg repo "$REPO" --argjson color "$COLOR" \
  '{username:($b+" · changelog"), avatar_url:$logo, embeds:[{author:{name:($b+" · changelog"),icon_url:$logo}, title:("📝  Changelog — "+$tag), url:$url, description:$desc, color:$color, footer:{text:($repo+" · full diff on GitHub"),icon_url:$logo}, timestamp:$ts}]}')
post "$CHANGELOG_WEBHOOK" "$changelog"

echo "announce-release: posted ${TAG} for ${REPO}"
