# trovex.dev — Technical SEO / GEO audit

*Owner: geo-lead (Discovery). Last updated: 2026-06-15.*

The audit that sits under all the GEO/AEO work: crawlability, indexation, metadata,
and the structural facts that decide whether AI engines can read the site at all.

## TL;DR

trovex.dev is a **client-side-rendered** Vite + React SPA. That is the single biggest
SEO/GEO fact about the site and it shapes every content decision below.

## Findings

### 1. CSR SPA → invisible to AI crawlers (highest impact)
AI crawlers — GPTBot, OAI-SearchBot, PerplexityBot, ClaudeBot — send one HTTP request,
parse the **raw HTML**, and move on. They do **not** execute JavaScript (analysis of
500M+ GPTBot fetches shows zero JS execution). trovex.dev ships an empty `<div id="root">`
and renders everything in the browser, so an AI engine currently sees the `<head>` meta
and **none** of the hero / features / FAQ copy.

Googlebot *can* render JS (deferred, best-effort), so Google indexation is workable, but
the AI answer engines that drive the Discovery north star see almost nothing.

**Decision (architecture):** GEO content — comparison/alternatives pages, the AEO Q&A
cluster, per-client pages — ships as **static, hand-authored semantic HTML under
`web/public/`** (e.g. `/vs/claude-md.html`, `/answers/...`), fully crawlable with zero JS,
each carrying its own `<title>`/meta and JSON-LD. The home SPA can stay CSR; its key
content should also exist in a crawlable surface (README on GitHub, the static pages, the
FAQPage JSON-LD). A later option is SSG (vite-react-ssg) or a Next migration, which
historically lifts indexation from <40% to >95% in ~60 days — tracked as a follow-up, not
needed to start shipping citable pages.

### 2. No robots.txt, sitemap.xml, or llms.txt — FIXED
None existed. AI crawler access is governed by **robots.txt** (llms.txt is advisory and
largely ignored by the major crawlers today, but IDE agents and MCP clients do read it —
and trovex's audience *is* coding agents, so it earns its place).

### 3. Thin / missing social + canonical metadata — FIXED
`index.html` had a title, description, and two OG tags. Missing: canonical, og:url,
og:image, og:site_name, twitter card tags, robots directives, theme-color. Wordmark was
capitalised "Trovex" in the title (brand is lowercase `trovex`).

### 4. Per-page metadata
A single-page CSR app can only express one set of `<head>` meta. Unique per-page
titles/descriptions require real per-route HTML — delivered by the static content pages in
finding #1, each with its own `<head>`. No router/rewrite gymnastics needed.

## Fixes shipped in this PR (`growth/geo-tech-seo`)

- `web/public/robots.txt` — allow `*` plus explicit Allow for GPTBot, OAI-SearchBot,
  ChatGPT-User, PerplexityBot, Perplexity-User, ClaudeBot, Claude-User, Claude-SearchBot,
  Google-Extended, Applebot-Extended, Googlebot, Bingbot; points to the sitemap. The
  explicit allows also opt **in** to the AI-training/answer bots that default to opt-out.
- `web/public/sitemap.xml` — homepage entry (content pages append here as they ship).
- `web/public/llms.txt` — llmstxt-spec summary of trovex for agents/IDE/MCP clients.
- `web/public/og-image.svg` — 1200×630 brand social card (dark, accent-green, the 60% stat).
- `index.html` — canonical, full Open Graph set, Twitter `summary_large_image`, robots
  directives (`max-image-preview:large`, `max-snippet:-1`), `theme-color`, lowercase
  wordmark, richer description. `lang="en"` already present.

Vite copies `public/` to the deploy root, so `/robots.txt`, `/sitemap.xml`, `/llms.txt`,
`/og-image.svg` resolve at the domain root with no config change.

## Remaining follow-ups (not in this PR)

- **Rasterize the OG card to PNG** (1200×630). The SVG renders for AI crawlers and
  SVG-capable platforms; some social platforms (notably X/Twitter, Facebook) prefer
  PNG/JPG. No rasterizer is available in this worktree (no sharp/cairosvg/playwright);
  convert in CI or by a human, then point `og:image` at the `.png`. **Low risk, cosmetic.**
- **Bing Webmaster Tools + IndexNow** — ChatGPT Search runs on Bing's index; not being in
  Bing = invisible to ChatGPT. Submitting the sitemap and wiring IndexNow is **external**
  (account + live submit) → leave for a human per autonomy-rules. Config/checklist will be
  prepped as a `human` task.
- **Schema / JSON-LD** — SoftwareApplication, Organization, WebSite, FAQPage, QAPage,
  BreadcrumbList. Separate task (`264d6e11`) / PR.
- **`⚠ Do NOT add a catch-all rewrite to `vercel.json`** routing every path to
  `index.html`. trovex has no client-side router; the static content pages must be served
  directly, and a catch-all would shadow them. (Currently `vercel.json` has no rewrites —
  keep it that way, or scope any rewrite to known SPA routes only.)
- **Core Web Vitals** — landing loads two Google Fonts (Fira Sans + Fira Code) render-
  blocking via `<link rel=stylesheet>`. `display=swap` is set (good). Consider self-hosting
  or `preload` if LCP needs it; current page is light, so this is monitor-only for now.
