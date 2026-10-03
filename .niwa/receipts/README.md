# L4 — /graph "the codebase's brain" — receipts

Task 266ebd6e. Captured with headless Chrome-for-Testing against a real `trovex serve`
(port 8799) over a copy of the live fleet index (4929 nodes / 438 edges). The server
served the built SPA from `web/dist-graph` at `/graph/` for every shot below — so these
double as the proof the `/graph` mount serves the built SPA (AC 2).

## Screenshots (real trovex index) — AC 2 & AC 3

- **01-full-status.jpg** — full graph, status lens. Louvain communities cluster and are
  labelled (real doc titles); typed doc_links drawn as lineage arrows (supersedes = violet,
  verdict-of = green); unlinked docs are small "corpus dust" so the wired knowledge core
  reads first. Pictogram node shapes encode kind (circle=doc, square=code, triangle=ticket,
  diamond=decision).
- **02-heat.jpg** — the SAME layout after switching the lens from **status -> agent heat**
  (an instant reducer repaint, no relayout). Glow/size by real agent reads (served results
  over 7d, max 197); never-read docs dimmed.
- **03-panel.jpg** — a node clicked, side panel open: the doc rendered (same markdown
  renderer as the Jinja page), out-links + in-links (backlinks) with their relation as
  context, and the one-click **open in trovex_read** that copies the exact MCP call.

## Perf — AC 4

- **04-perf-5k.jpg** — `/graph/?synthetic=5000` (5,000 nodes / ~20,000 edges, the stated
  budget). A perf HUD reads sustained **113 fps**, **worst frame 44 ms**, while an automated
  camera orbit drives continuous WebGL redraws. (Observed across runs: 107-120 fps, worst
  frame 15-72 ms, always interactive.) ForceAtlas2 ran in a worker; the 2D WebGL sigma.js
  renderer holds the budget comfortably on an M-series MacBook.

## anti-ai-slop-web — AC 5

**PASS.** One accent (trovex green `#22c55e`) + brand greyscale/status tokens from
`web/src/index.css`; no indigo/violet gradient; Fira Sans / Fira Code pairing; a full-bleed
app with one focal point (the graph) and asymmetric overlays, not the 3-card/9-section
specimen; pictogram node shapes are data, not emoji icons; honest, product-grounded copy;
a real cmd-K shortcut (not a decorative hint); native `<button>`s, ARIA `tablist`,
`:focus-visible` rings, `prefers-reduced-motion` honored; hand-written CSS on tokens (no
Tailwind default-look). No fabricated numbers/testimonials.

## Render-lib rationale (PR)

**sigma.js v3 + graphology** (2D WebGL). Node reducers give an instant lens repaint with
no relayout; FA2 runs in a worker (60 fps main thread); Louvain gives the communities we
cluster + label; `@sigma/node-image` `NodePictogramProgram` (drawingMode `color`) cleanly
splits **shape = node kind** (a stable SVG glyph) from **colour = the active lens**. Beats
cosmos/cosmograph (no per-node shapes/labels, reads as a particle cloud) and
react-force-graph three.js 3D (flashy but unreadable/un-screenshot-worthy). Hand SVG / a
basic CDN force layout were ruled out by the founder bar.

## Deploy note (per cto-tsukumo ack)

`/graph` mounts only when `web/dist-graph` exists (404-safe otherwise, exactly like
`/receipt`). The deploy pipeline must run **`npm run build:graph`** (emits `web/dist-graph`,
gitignored like `dist-receipt`) so prod serves `/graph`. The **drift** lens stays all-zero
until L5 (`docs.drift` / `doc_refs`) merges to dev; the endpoint already reads the column
optionally, so no further change is needed when it lands.
