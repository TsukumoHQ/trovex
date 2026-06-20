---
name: tsukumo-blog-widgets
description: >
  The menu of editorial widgets/blocks available in the tsukumo blog (Payload), so a writer
  picks from a known set instead of guessing. Covers each block's slug, fields, when to use it,
  and the exact spec to invoke — callout, chart, comparison table, CTA — plus FAQ and the
  table-of-contents (handled outside blocks). Use when writing or editing a tsukumo blog article
  (cornerstone, earned-evidence study, pillar post) and choosing how to present something:
  inserting a callout/chart/comparison/CTA, adding an FAQ, or asking "which widgets does the
  tsukumo blog have". For the CI-Léman (Carnet) blog use carnet-blog-mcp instead — different set.
metadata:
  type: reference
---

# tsukumo blog — widget catalog

The tsukumo blog (Payload, content stored as Lexical/Blocks jsonb; blocks defined in
`src/lib/blog/blocks.ts`, rendered by `src/components/blog/widgets.tsx`, registered in the
`blog/[slug]/page.tsx` converters) has **four insertable blocks** plus **FAQ** and a **TOC**
that are handled outside the block system. It is a trimmed subset of the CI-Léman Carnet set —
no `essentiel`, `stat`, `gallery`, `pullQuote`, `sources`, `keyMetric`, or `bienEmbed`. Don't
reach for those; they aren't wired.

**Honesty rule (owner P0, every block):** only the real **~60% fewer tokens per lookup** is a
claimable number. A `chart` or any data block MUST carry real data + a cited `source` — never
invent figures. anti-slop gate on all copy before publish.

## The four blocks

### callout
A boxed aside for a caveat, a warning, or the one line you want to land.
- **Fields:** `variant` (`note` | `warning` | `key-insight`), `heading?` (text), `text` (required).
- **When:** the honesty nuance an earned-evidence post needs ("the study didn't say *no* context,
  it said *naive* context"); a caveat; the single takeaway. Use `key-insight` sparingly — one per
  post or it stops meaning anything.

### chart
A bar or line chart, rendered as crawlable SVG (AEO-readable).
- **Fields:** `title?`, `type` (`bar` | `line`), `unit?` (e.g. `%`, `$`, `ms`), `source?` (cite it,
  shown under the chart), `data[]` of `{label, value}` (min 2 rows).
- **When:** show the number instead of asserting it — the token-cost math, a study's figures.
  **Real data only**, always set `source`. Put the chart *in* the section it explains, not in an
  isolated block.

### comparison
A side-by-side table with a highlighted row-label column.
- **Fields:** `title?`, `columns[]` of `{header}` (min 2; column 1 = the row label), `rows[]` of
  `{cells[]{value}}`.
- **When:** dump vs retrieve vs answer; CLAUDE.md vs trovex; naive-context vs canonical. Honest
  framing — name what the other option is genuinely good at; never a strawman.

### cta
The end-of-post call to action.
- **Fields:** `heading?`, `label` (required, default `Book an assessment`), `href` (required,
  default `/assessment`), `note?`.
- **When:** once, near the end. **⚠ P0 0b61b80f:** the default `label`/`href` route to
  **consulting** (`/assessment`). That's fine on the **company** blog (tsukumo.ch). In a
  **founder-voice / personal** context, do NOT push `/assessment` — point the CTA at the tool
  (`trovex.dev`, "star it", the GitHub repo) instead. Two doors, two voices.

## Not blocks (but available)

- **FAQ** — authored in the post's `seo.faq` field (not inserted in the body). Renders as an
  accordion **and** emits `FAQPage` JSON-LD (the schema is the visible content — AEO). Use 3–5
  real questions a reader would actually ask.
- **Table of contents** — auto-extracted from the `h2`/`h3` headings (`extractToc`). Not authored;
  just write good question-shaped headings and it builds itself.

## Adding a NEW widget

It's a 3-step code change (no DB schema push — content is jsonb), so it's a fullstack task, not a
content one:
1. Define the Block in `src/lib/blog/blocks.ts`.
2. Add the renderer in `src/components/blog/widgets.tsx`.
3. Register it in the `blog/[slug]/page.tsx` Lexical converters.

**Wishlist (ranked, spec'd):** the high-value blocks worth adding next live in trovex store doc
`d738fc2d` — top two are **citation / source-card** (the structured primary-source block the
earned-evidence engine needs to be citable + un-fakeable) and a **methodology box** ("how we
measured / how to reproduce"). Hand the build to fullstack; update this catalog as they land.
