# Product Hunt gallery (DRAFT assets)

Five gallery slides built to launch-lead's PH kit (`growth/launch/product-hunt.md` §4).
**DRAFT — a human schedules and launches.** 1270×760 (PH gallery size). Brand green
`#22c55e`, lowercase `trovex`, real ~60% only.

Authored as SVG and rasterized with `resvg` + Fira fonts (pixel-sharp text, exact brand
color — image models garble both). Sources in `growth/assets/_src/ph-*.svg`.

| File | Slide | Role |
|------|-------|------|
| `ph-1-hook.png` | 1 — the hook | before/after split: agent rereads 6 .md (~720) vs trovex one `path:line` + canonical/fresh (~280). "one current doc, not a repo reread." |
| `ph-2-receipt.png` | 2 — the proof | the savings view: would-have-read vs actual, ~60% fewer |
| `ph-3-how.png` | 3 — how it works | `index your repo` → `agent asks trovex(q)` → `gets one doc + freshness` |
| `ph-4-ssot.png` | 4 — SSOT | agents + teammate read/write one trovex store; "one source of truth" |
| `ph-5-local.png` | 5 — trust close | local-first · SQLite + on-device embeddings · no cloud/keys · AGPL core / MIT CLI |

## Honesty gate
- Real ~60% + reconciled 720→280 only. No fabricated metrics, no Synergix, lowercase trovex.
- **Slide 2 is labeled "representative run" / "illustrative of the mechanism."** Per the PH kit's
  asset-honesty gate, before launch swap it for a screenshot of the **savings view on a real run**
  (the tool ships that view). The card matches the dashboard labels so the swap is drop-in.
- Optional Slide 0 (PH kit): a ≤30s real screen capture (`index` → query → one-doc → savings view)
  beats a motion graphic — capture from the actual product, not generated here.
