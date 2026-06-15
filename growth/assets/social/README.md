# Savings-receipt card visuals (DRAFT assets)

Shareable "savings receipt" cards — the dark-social atom. Drop into a post, a Discord/Slack
channel, or a DM; each reads with zero context. **DRAFT — a human posts.** Pairs with the copy
spec in `growth/social/savings-receipt-variants.md` and the cro-lead receipt spec
(`growth/cro/savings-receipt.md`).

## Canonical set (crisp SVG → PNG, brand green `#22c55e`, lowercase `trovex`)

Authored as vector and rasterized with `resvg` + Fira fonts, so text is pixel-sharp at any size
and the accent is exactly the brand green. Sources in `growth/assets/_src/*.svg`; regenerate with
`growth/assets/_tools/render_svg.sh`.

| File | Use | Card |
|------|-----|------|
| `receipt-mechanism.png` | story / carousel (variant C) | BEFORE rereads several .md `~720` vs AFTER one canonical section `~280` → `~60% fewer tokens` |
| `receipt-oneline.png` | minimal hero / reply image (variant B) | "my coding agents stopped rereading the repo." + `~60% fewer tokens` |
| `receipt-measure.png` | activation CTA (variant D) | "want your own receipt?" + the `trovex index`/`search` commands — measure your own |

All 1080×1080 (square = best reshare on X / LinkedIn / Slack / Discord).

## Honesty
- Only the real ~60% figure and the reconciled 720→280 example. No fabricated metrics.
- No Synergix. Lowercase `trovex`. Developer-honest, no hype.
- Representative illustrations, not a specific customer's receipt. For a real post, prefer a
  screenshot of the user's own savings dashboard when available (see the variants spec).

## Note on accent color
An earlier gpt-image-1 pass (#38) rendered these cards with a **gold/tan accent instead of brand
green `#22c55e`** — image models ignore an exact hex. Those cards were removed (cmo-approved) in
favor of the crisp green set above. Lesson: never let an image model render the brand color or text;
composite both as SVG and rasterize with `resvg`. See memory `imagegen-brand-color-rule`.
