# Tsukumo — brand & design system

> **tsukumo** (付喪神) — in Japanese folklore, tools that reach a great age gain a spirit.
> Our read: dev tools become **agentic operators**. The studio that makes them behave.
> Primary brand = the agency **tsukumo**. The OSS suite (trovex · wrai.th · yoru) is the
> proof and the funnel — it borrows this system but keeps its own product voice.
>
> Direction: **01 Concrete & Acid** — brutalist + minimalist, award-tier, anti-corporate.
> This is the source of truth. Tokens: [`../design-tokens.css`](../design-tokens.css).

---

## 1. Wordmark
- Always lowercase: **`tsukumo`**. Never "Tsukumo", never all-caps, never a tagline lockup baked in.
- Set in **Archivo, weight 800**, tracking `-0.02em`.
- The mark: a solid **acid-lime square** preceding the word (the "spirit" spark). Square height ≈ cap height.
- **Clear-space:** keep a margin of one full square (the mark's size) on all sides. Nothing inside it.
- **Min size:** 96px wide on screen / 20mm in print. Below that, drop to the square mark alone.
- Files: `growth/assets/agency/tsukumo-wordmark.png` (+ `_src/agency/tsukumo-wordmark.svg`).

## 2. Color
| Token | Hex | Role |
|-------|-----|------|
| ink | `#121212` | primary background / dark base |
| ink-2 | `#1b1a18` | raised surface, ghost numerals |
| concrete | `#9a958c` | muted UI, photographic texture (the hero material) |
| concrete-dark | `#6b665e` | deeper concrete / shadow |
| bone | `#f3f1ea` | primary text on ink, paper surfaces |
| bone-dim | `#b8b3a8` | secondary text on ink |
| **acid** | **`#c8ff00`** | THE accent — one per view, never decorative soup |
| acid-ink | `#0e1100` | text on acid fills |
| hairline | `rgba(243,241,234,0.14)` | rules, dividers |

**Rule:** two-tone base (ink + bone) + **exactly one** acid accent in view. Acid marks the one
thing that matters (a key word, a CTA, an index). Never gradients-as-decoration.

## 3. Typography
- **Display — Archivo** (Google Fonts; license a sharper grotesk later if wanted). Weights 800–900,
  tracking `-0.03em`, leading `0.92`. Set **huge** — `clamp(3.5rem, 14vw, 13rem)` for heroes.
- **Mono — Space Mono** for labels, nav, captions, index numbers, code. This is the "built-by-engineers"
  tell and the thread that links to trovex.
- **Brutal scale** — there is *display* and there is *small*, little in between.

| Step | Token | Use |
|------|-------|-----|
| hero | `clamp(3.5rem,14vw,13rem)` | one-line statements |
| h1 | `clamp(2.5rem,8vw,6rem)` | section heads |
| h2 | `clamp(1.75rem,4vw,3rem)` | sub-heads |
| body | `clamp(1rem,1.2vw,1.25rem)` | prose (kept short) |
| label | `0.8125rem` mono | index, captions, nav |

## 4. Layout & grid
- 12 columns; content spans **odd ranges** (2–7, 8–12) — hang off the grid, don't center.
- Hairline rules as structure. **Index numbers** in the margin (`01 — 04`).
- **Negative space is a material** — whole viewports with one headline. Alternate full-bleed type with breath.
- Brutalist defaults: **hard corners** (`radius: 0`), no drop-shadow decoration.

## 5. Motion
- Heavy ease-out `cubic-bezier(0.16, 1, 0.3, 1)`, ~0.7s. Type rises from clip-masks, staggered by line.
- One pinned horizontal "work" gallery; otherwise calm. One restrained cursor detail.
- Always honor `prefers-reduced-motion`. Performance is part of the craft (Core Web Vitals green).

## 6. Voice on visuals
Builder-credible, dev-respecting, confident. "run AI in production." / "augment, never replace."
**Never** generic-AI-agency, replace-your-devs hype, stock photography, glowing-brain, logo soup.

## 7. Do / don't
- ✅ One acid accent per view · oversized type · raw asymmetric grid · mono labels · real words.
- ✅ Concrete texture + hard directional light for imagery.
- ❌ More than one accent in view · centered safe layouts · gradients/blobs · rounded friendly corners ·
  **fabricated numbers/logos/testimonials** · the company name "Synergix" on any public surface.

## 8. Suite relationship (reference)
| Brand | Surface | Look |
|-------|---------|------|
| **tsukumo** | agency site, decks | this system — concrete + acid, Archivo/Space Mono |
| trovex | OSS product (beta) | terminal-restraint: `#0a0e17` bg, green `#22c55e`, Fira Sans/Code, lowercase. Honest/humble. |
| wrai.th | orchestration (OSS) | suite member; inherits restraint, own mark TBD |
| yoru | observability (OSS) | suite member; inherits restraint, own mark TBD |

Shared DNA across all: **lowercase wordmarks, mono thread, one-accent discipline, no fabricated proof.**
Different register: products are humble and honest; the studio is confident and loud.

## 9. Asset inventory
- Tokens: `growth/agency/design-tokens.css`
- Wordmark: `growth/assets/agency/tsukumo-wordmark.png` · `_src/agency/tsukumo-wordmark.svg`
- Hero concept: `growth/assets/agency/tsukumo-hero.png`
- Hero background (textless): `growth/assets/agency/bg-hero-concrete.png`
- OG/social: `growth/assets/agency/tsukumo-og.png`
- Case cards: `growth/assets/agency/case-{studio,fund,cil}.png`
- Direction options (incl. 02/03 for reference): `growth/agency/design-direction.md`
- Deck master: `growth/agency/brand/tsukumo-master.pptx`
- This bible (printable): `growth/agency/brand/brand-system.html`

_Generators (reproducible): `growth/assets/_tools/gen_agency_mocks.py`, `gen_tsukumo_cases.py`,
`gen_tsukumo_deck.py`._
