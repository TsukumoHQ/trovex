#!/usr/bin/env bash
# Generate 6 grayscale brutalist concrete-wall hero backgrounds (tsukumo).
# gpt-image-2 PNG -> cwebp (<400KB). Textless; the lone acid comes from type overlay.
# Resumable: skips a PNG that already exists. Key from env (never printed).
# Output: growth/assets/agency/hero-walls/*.webp
set -uo pipefail
cd "$(dirname "$0")/../../.."   # repo root
set -a; . ~/.config/trovex-growth/openai.env; set +a
OUT=growth/assets/agency/hero-walls
TMP=/tmp/hero-walls; mkdir -p "$OUT" "$TMP"

BASE="Raw brutalist exposed-concrete wall, architectural, GRAYSCALE / fully desaturated (no color at all), fine cement grain, form-tie holes. Hard raking directional light and deep crisp shadow. Lots of empty negative space for large text overlay. Monolithic, expensive, anti-corporate, editorial. Flat matte, no gloss. Absolutely NO text, NO letters, NO numbers, NO logos, NO UI, NO people, NO furniture, NO 3D-render clichés, NO color casts."

declare -a P=(
 "flat-slab|A single flat head-on concrete slab wall, light raking from the left edge, deep shadow pooling right."
 "corner|Two concrete walls meeting at a sharp vertical corner, one face bright, the other in deep shadow."
 "seam|A large concrete wall with one stark vertical board-form seam, a hard shaft of light crossing diagonally."
 "poured|Board-formed poured concrete with horizontal plank-texture lines, low grazing light raising the texture."
 "monolith|A massive concrete monolith block against an empty concrete floor, single hard light, long shadow, vast negative space."
 "shaft|An almost-empty concrete wall with one hard-edged trapezoid shaft of daylight falling across it, rest in shadow."
)

for entry in "${P[@]}"; do
  slug="${entry%%|*}"; desc="${entry#*|}"
  echo "== $slug =="
  if [ ! -f "$TMP/$slug.png" ]; then
    python3 growth/assets/_tools/gen_image.py "$desc $BASE" "$TMP/$slug.png" 1536x1024 || { echo "  gen FAILED $slug"; continue; }
  else
    echo "  (png cached)"
  fi
  # PNG -> grayscale webp, capped width, quality for <400KB
  cwebp -quiet -q 70 -resize 1600 0 "$TMP/$slug.png" -o "$OUT/wall-$slug.webp" || { echo "  cwebp FAILED $slug"; continue; }
  kb=$(( $(stat -f%z "$OUT/wall-$slug.webp") / 1024 ))
  # if still >400KB, step quality down
  q=62
  while [ "$kb" -gt 400 ] && [ "$q" -ge 40 ]; do
    cwebp -quiet -q "$q" -resize 1600 0 "$TMP/$slug.png" -o "$OUT/wall-$slug.webp"
    kb=$(( $(stat -f%z "$OUT/wall-$slug.webp") / 1024 )); q=$(( q - 8 ))
  done
  echo "  wall-$slug.webp ${kb}KB"
done
echo "ALL DONE"; ls -la "$OUT"/*.webp 2>/dev/null | awk '{print $5, $NF}'
