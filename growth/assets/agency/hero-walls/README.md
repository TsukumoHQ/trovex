# tsukumo — concrete-wall hero backgrounds

Owner-loved brutalist concrete heroes for the tsukumo site. **Grayscale + textless** by
design: the lone acid `#c8ff00` comes from the type/CTA overlaid on top (one accent per view).
fullstack-lead wires the chosen one(s) into the tsukumo hero; cmo/owner pick.

6 variants (1600px wide, webp, all <110KB):

| File | Composition |
|------|-------------|
| `wall-flat-slab.webp` | flat head-on slab, raking left light |
| `wall-corner.webp` | two faces meeting at a corner, light/shadow split |
| `wall-seam.webp` | board-form seam + diagonal light shaft |
| `wall-poured.webp` | board-formed poured concrete (plank lines), grazing light |
| `wall-monolith.webp` | massive monolith block, long shadow, vast negative space |
| `wall-shaft.webp` | near-empty wall, hard trapezoid daylight shaft |

Generated: `growth/assets/_tools/gen_hero_walls.sh` (gpt-image-2 → cwebp, resumable, auto-compress
to <400KB). Regenerate or add variants by editing the prompt array. No text/people/color in source.
