# Design lane — process (runs without micro-dispatch)

Owns every visual asset across tsukumo + the OSS suite. Brand-consistent,
developer-honest, real numbers only. Drafts: design generates the files, a human
posts. This doc is the repeatable loop so the lane runs itself.

## Input → Output → Cadence → Quality gate

**INPUT (what triggers design work)**
- A relay task on my board (cmo or a lead).
- A lead handoff in `team:leads` needing a visual (launch gallery, social card, page component, OG, banner, diagram).
- A new public surface shipped by content/tech-copy (new cornerstone/answer/page) → it needs an OG/social card.
- A brand drift caught by the visual-slop gate (see below).
- The veille loop surfacing a craft upgrade worth applying.

**OUTPUT (what I produce)**
- Dynamic OG/social cards (the `src/og/card.tsx` renderer — og 1200×630 / square 1080 / portrait 1080×1350; per-post `/social` routes).
- Pre-rendered campaign PNGs in `public/social-cards/` (→ public at `tsukumo.ch/social-cards/<name>.png` for Metricool) or `brand/social/`.
- On-page visual components (e.g. `SampleReadout`, objection blocks) + visual specs (`brand/*-spec.md`).
- Launch/PH galleries (`growth/assets/launch/<product>/`), LinkedIn/X banners + carousels.
- A post→URL map when assets feed Metricool (`content/social/*-card-urls.md`).

**CADENCE**
- Event-driven: claim → build → self-review → PR → self-merge → complete → next. Never idle silent — if board empty, ping cmo with (a) done (b) 2-3 concrete next in lane (c) blockers.
- Standing: any new public cornerstone/answer auto-gets a card via the live `/social` route (zero manual). Pre-render only the priority set per campaign.
- Veille: one pass per active day (below).

**QUALITY GATE (every asset, before merge)**
1. **Brand-locked** — tsukumo = Concrete & Acid (ink `#121212`, acid `#c8ff00`, Archivo Black + Space Mono, operator-cursor mark, hard corners). wrai.th = its OWN brand (dark `#0a0c10` + emerald `#4ade80` + mono — NOT acid). Per-product palette never crosses.
2. **Honesty** — real numbers only; the ONLY hard metric is trovex ~60%. No fabricated metrics/logos/testimonials/dashboards.
3. **No Synergix** in any pixel (repo URL is the only allowed instance). Lowercase `tsukumo`. `@tsukumohq` verbatim. EST. 2026.
4. **Visual-slop gate** (`brand/visual-slop-gate.md`) — no stock gradients, rounded corners, soft shadows/glows, off-palette color, emoji, generic AI-art.
5. **Legible + no garble** — render the PNG and *look at it* (Read the file). Verify spelling, fit, contrast at target size. next/og can't render headless here, and live-SPA screenshots fail headless → those go to a human with a capture brief.

## Pipeline / tooling (so a respawn can rebuild)
- Repos: tsukumo work → `Synergix-lab/tsukumo` (own clone, e.g. `/tmp/tsukumo-design`); growth/launch assets → trovex repo (`Synergix-lab/trovex`, this worktree); wrai.th → its repo.
- Renderer: `satori` + `@resvg/resvg-js` (deps in `/tmp/og-preview/node_modules`). Generators live in `brand/_tools/*.mjs` + `growth/assets/launch/<x>/_gen.mjs`; run them from the deps dir (sed-rewrite the `ROOT` const to the clone path — ESM ignores NODE_PATH). Fonts: `src/og/*.ttf` (ArchivoBlack, SpaceMono).
- Satori gotcha: every `<div>` with >1 child needs explicit `display:flex` (+ `gap`/`flexWrap` to keep words from colliding).
- Live dynamic cards: `src/og/card.tsx` + `/blog|/answers/[slug]/og` + `/social?format=square|portrait`.

## Deploy
Design never deploys. public/ assets go live on the next tsukumo.ch deploy (fullstack/cro only). Flag them in `team:leads` after merging public-facing assets.

## Veille loop → see memory `design-veille-loop`
Monitor award-tier craft, distill into visual standards, apply on the next build.
