# Agency site — visual direction (DRAFT for cmo/owner pick)

> **Status: DIRECTION OPTIONS, not locked.** Three named vibes + concept hero mocks to
> choose the feel. Final palette/type get locked once the agency **name** lands.
> Name-agnostic for now (placeholder wordmark in the mocks). A human picks the direction;
> nothing here is live.
>
> **Deliberately NOT the trovex look.** trovex is terminal-restraint (near-black, one green,
> Fira mono, developer-honest). The agency has its **own, bolder identity** — brutalist +
> minimalist, design-forward, award-tier (Awwwards / FWA caliber), anti-corporate-consulting.
> The two should read as different brands that clearly belong to the same people.

---

## The brief, in one line
Make a consulting/studio site that looks like it was made by people who build
**exceptional** AI products — confident, raw, expensive-feeling, zero corporate stock.

## Principles (shared across all three vibes)
1. **Type is the hero.** Oversized display set to the viewport (`clamp()` to 12–22vw),
   tight leading, set big enough to feel almost uncomfortable. Copy is short and declarative.
2. **Raw, asymmetric grid.** A visible/implied column grid that's intentionally broken —
   content hangs off the grid, not centered. Hairline rules. Numbered index labels (`01 — 04`).
3. **Negative space is a material.** Whole viewports with one headline and nothing else.
   Silence between sections. The opposite of a feature-stuffed SaaS page.
4. **One bold accent, stark base.** Two-tone base (near-black / paper) + exactly one
   confident accent. Never a gradient soup, never more than one accent in view.
5. **Motion with weight.** Heavy easing, big masked type reveals, scroll-driven horizontal
   moments, cursor-reactive details. No bounce, no confetti, no parallax-for-its-own-sake.
   Respect `prefers-reduced-motion`.
6. **Anti-slop guardrails.** No stock photography, no glowing-AI-brain, no generic gradient
   blobs, no "trusted by" logo soup, no corporate handshake energy. Real work, real words.

## Type system (direction)
- **Display:** a grotesk with attitude — Neue Haas Grotesk / Söhne / ABC Diatype / Inter-Tight
  at huge weights. Tight tracking on the giant sizes.
- **Body:** the same grotesk at a quiet weight, generous measure, high line-height.
- **Mono (labels/meta):** a technical mono (Söhne Mono / Geist Mono / Fira Code) for index
  numbers, captions, nav, and the "made-by-engineers" tells. This is the one thread that
  quietly links back to trovex.
- **Scale:** brutal jumps — there's *display* and there's *small*, almost nothing in between.

## Layout / grid
- 12-col on desktop, content deliberately spanning odd ranges (e.g. cols 2–7, 8–12).
- Hairline 1px rules as structure; index numbers in the margin.
- Full-bleed type sections alternating with near-empty "breath" sections.
- Mobile: the giant type stays giant (it's the point), stacks honestly.

## Motion principles
- Entrance: type rises out of a clip-mask, heavy ease-out, staggered by line.
- Scroll: one pinned horizontal "work" gallery; otherwise calm.
- Cursor: a single restrained custom-cursor / magnetic detail, not everywhere.
- Performance is part of the craft: ship it fast (Core Web Vitals green) or it isn't award-tier.

---

## Three named directions (pick one)

### 01 — "Concrete & Acid"  *(recommended for confidence)*
Brutalist concrete base, harsh directional light, **one acid-lime slab** as the accent.
Reads as a heavyweight studio that builds real things. Most distinctive, most anti-corporate.
- Base: concrete grey `#9a958c` / near-black `#141414` · Accent: acid lime `#c8ff00`
- Feel: raw, monolithic, print-poster. Mock: `concept-concrete-acid.png`

### 02 — "Editorial Void"
Bone-paper field, immense negative space, ink-black forms — a museum wall. Quiet luxury,
gallery confidence. Best if the brand wants restraint over aggression.
- Base: bone `#f3f1ea` / ink `#0e0e0e` · Accent: a single ink or one muted ember
- Feel: Swiss-editorial, expensive, calm. Mock: `concept-editorial-void.png`

### 03 — "Signal"
Near-black technical field, hairline blueprint grid, **one signal-red** element. The most
"engineering-luxe" — closest sibling to trovex without copying it.
- Base: charcoal `#0b0b0c` / fog `#cfcfcf` · Accent: signal red `#ff3b1d`
- Feel: precise, technical, controlled. Mock: `concept-signal.png`

---

## How each links back to trovex (without matching it)
The **mono thread** (labels, index numbers, captions) and the **one-accent discipline** are
the shared DNA. trovex = green/terminal; the agency = one of the bolder accents above. Same
people, different register: the product is humble and honest; the studio is confident and loud.

## Open decisions for cmo / owner
1. **Pick a direction** (01 / 02 / 03) — or a hybrid (e.g. 03 structure + 01 accent).
2. The **name** — locks the wordmark, final palette hex, and type license choice.
3. Tone of the headline copy (capability-led, no company name per the no-Synergix rule):
   e.g. *"Systems for teams shipping AI."* / *"We make agents behave."* / *"Engineering for the agent era."*

## Next steps once a direction is chosen
- Lock tokens (CSS variables: color, type ramp, spacing) in an agency `design-tokens` file.
- Build the real hero + one work-gallery section in code (not mocks) for a true feel test.
- Hand copy direction to content-lead for the headline/voice.
