# trovex.dev internal-link silo

*Owner: geo-lead (Discovery). Last updated: 2026-06-16.*

A deliberate internal-link structure so search and AI engines see clear topical
clusters and pass authority between related pages. All content pages are static
HTML under `web/public/` (the React home is client-rendered; the content silo is not).

## Clusters (hubs + leaves)

```
/  (home, React) · /beta/ (private-beta access page)
├─ /vs/        Comparisons hub  → 11 leaves
│   ├─ /vs/claude-md/   /vs/repomix/        /vs/context-hub/
│   ├─ /vs/mem0/        /vs/cursor-memory/  /vs/vector-db-rag/
│   └─ /vs/continue/    /vs/aider/  /vs/cody/  /vs/pieces/  /vs/claude-projects/
├─ /answers/   AEO answers hub  → 9 leaves
│   ├─ /answers/stop-agent-rereading-docs/   /answers/reduce-agent-token-costs/
│   ├─ /answers/canonical-context-for-agents/ /answers/bigger-context-window-rereading/
│   ├─ /answers/shared-source-of-truth-multiple-agents/ /answers/why-agents-pick-stale-docs/
│   └─ /answers/agent-cost-rereading-files/ /answers/source-of-truth-multi-agent-repos/
│       /answers/mcp-server-for-repo-docs/
└─ /for/       Setup hub        → 4 leaves
    ├─ /for/claude-code/  /for/cursor/  /for/windsurf/  /for/cline/
```

28 static pages total (3 hubs + 24 leaves + `/beta/`), all in `sitemap.xml`.

## How the silo is wired

- **Guards.** `npm run build` runs `check-brand.mjs` (no "Synergix" on public surfaces)
  and `check-sitemap.mjs` (every static page is in `sitemap.xml`, no dead `<loc>`), so the
  silo and brand can't drift on a deploy.
- **Backbone (every page → every hub).** A uniform top-bar nav on all static pages
  links the three hubs: **Compare** (`/vs/`), **Answers** (`/answers/`), **Setup** (`/for/`).
  The home footer links the same three (plus Product/GitHub). So any page reaches any hub
  in one hop, and every hub gets inbound links from the whole site.
- **Hub → leaf.** Each hub lists its leaves with descriptive anchor text (and an `ItemList`
  JSON-LD) — the canonical hub→leaf distribution.
- **Leaf ↔ leaf, within and across clusters.** Each leaf has a "Related / More comparisons"
  block linking siblings, plus contextual cross-cluster links chosen for topical relevance:
  - comparison leaves link to the most relevant answer(s) and, where natural, the matching
    setup page (e.g. `/vs/cursor-memory/` → `/for/cursor/`);
  - answer leaves link to the most relevant comparison(s);
  - setup leaves link to `/vs/claude-md/` and sibling setup pages.
- **Breadcrumbs.** Every leaf carries `BreadcrumbList` JSON-LD (home → hub → leaf), mirrored
  by a visible breadcrumb — reinforcing the hierarchy for crawlers.
- **Anchor text** is descriptive and varied (not "click here"), matching each target's topic.

All 21 distinct internal links resolve to live pages (checked in CI-style by a link scan;
no broken links — broken internal links would leak the silo's authority).

## Pending

- **/blog**: the editorial cluster (`growth/blog/*.md`) is not yet rendered as web routes,
  so it is **not** linked into the silo — linking to non-existent `/blog/*` URLs would create
  broken links. When content-lead/eng ship a `/blog` route, wire it in symmetrically: a
  `/blog/` hub in the top-bar nav, blog posts ↔ the most relevant comparison and answer pages,
  and breadcrumbs. Until then the silo spans `/vs/`, `/answers/`, `/for/`, and home.
