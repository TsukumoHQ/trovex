# Agency site — concept mocks (DRAFT, pick one)

Hero concept mocks for the agency/studio site direction. **Name-agnostic** (placeholder
wordmark); type is **indicative** (Fira stand-in for a grotesk) — final type/palette lock
with the name. Distinct from the trovex terminal brand by design. See
`growth/agency/design-direction.md` for the full direction + palettes.

| File | Direction | Base · accent |
|------|-----------|---------------|
| `concept-concrete-acid.png` | 01 — Concrete & Acid (recommended) | concrete/near-black · acid lime `#c8ff00` |
| `concept-editorial-void.png` | 02 — Editorial Void | bone paper/ink · ember `#ff5a1f` |
| `concept-signal.png` | 03 — Signal | charcoal/fog · signal red `#ff3b1d` |

Pipeline: gpt-image-2 textless brutalist backdrop → crisp SVG type overlay → resvg.
Sources in `growth/assets/_src/agency/` (`bg-*.png`, `mock-*.svg`, `gen_agency_mocks.py`).

---

## LOCKED — Tsukumo (direction 01 "Concrete & Acid")
Name + direction locked (memory `agency-identity`). Tokens: `growth/agency/design-tokens.css`.

| File | Use |
|------|-----|
| `tsukumo-wordmark.png` (+ `_src/agency/tsukumo-wordmark.svg`) | lowercase `tsukumo` wordmark — Archivo heavy + acid-lime mark, bone on ink |
| `tsukumo-hero.png` (+ `_src/agency/tsukumo-hero.svg`) | branded hero concept: "run AI in production." + positioning, for the coded build |

Type: **Archivo** (display, Google Fonts — shippable until a licensed grotesk) + **Space Mono** (labels).
Palette: ink `#121212` · bone `#f3f1ea` · concrete `#9a958c` · acid `#c8ff00`. No fabricated numbers
(positioning is qualitative — "run AI in production, not demos"; real metrics flagged to cmo when available).
Coded hero → built in `Synergix-lab/tsukumo` when the repo lands.

---

## Tsukumo asset set (#9f694f2c — cmo ports into Synergix-lab/tsukumo)
Acid/brutalist (memory `tsukumo-tokens`). Sources in `_src/agency/`.

| File | Use |
|------|-----|
| `tsukumo-og.png` (1200×630) | OG/social card — "run AI in production." + positioning |
| `bg-hero-concrete.png` | textless concrete hero background (hard light) to overlay coded type |
| `case-studio.png` / `case-fund.png` / `case-cil.png` (1200×750) | work-gallery / case-study cards |

**Honesty:** qualitative only, **no fabricated numbers**. Case-card copy is **DRAFT** — content-lead
owns the final approved one-liners (studio = WRAI.TH/trovex/yoru OSS; fund = anonymized/NDA; CI-Léman).
Swap copy in the SVG sources (`gen_tsukumo_cases.py`) and re-render. `tsukumo` lowercase, no Synergix on surfaces.
