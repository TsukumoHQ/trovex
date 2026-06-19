# GEO/SEO lane — process + veille (the repeatable machine)

**Owner:** geo-lead · **Mandate:** when a dev asks an AI engine or Google the category/comparison/branded questions, **trovex/tsukumo is the cited answer** — qualified reach that surfaces consulting leads, not vanity rank. Runs without micro-dispatch.

## Inputs → Output → Cadence

| Input | What I do | Output | Cadence |
|---|---|---|---|
| analytics citation-monitor run (per-query cited/uncited, by source) | diff vs baseline; for each uncited high-intent query, ensure the best citable answer exists | updated `growth/geo/citation-attack-map.md` + memory `geo-citation-rerun-baseline` | per monitor run (target weekly) |
| new `/answers` `/vs` `/for` page merged by content/tech-copy | run the on-page lever checklist (below) on it | PR adding any missing lever | on each content merge |
| content change to a page (de-slop, tighten, new copy) | bump `dateModified` / `CONTENT_MODIFIED` + sitemap `lastmod` | freshness PR | per change batch |
| competitor cited where we're not (e.g. repomix) | sharpen our `/vs` + earned-citation target for that query | PR + target-map update | per monitor run |
| new off-site opportunity (registry, awesome-list, listicle, thread) | add to per-query earned-citation target map | `content/geo/earned-citation-targets.md` (tsukumo) → hand launch/social | continuous |

## On-page lever checklist (the standing quality gate — every citation page)

1. **Leads with a 40–75w direct answer** (the quotable passage), visible.
2. **Speakable** `cssSelector` points at the visible answer block (`h1` + `.verdict p` / `.answer-lede` / capsule). Schema mirrors visible content — never a selector with no element.
3. **Freshness**: `datePublished` + `dateModified` in schema, mirrored by a visible "Updated" stamp. Bump on real change only (honest).
4. **Schema type** matches page: QAPage (/answers), FAQPage (/vs), HowTo (/for), Article + FAQPage + BreadcrumbList; DefinedTermSet glossary for category terms. All mirror visible text.
5. **Auto-derived surfaces** stay in sync: `llms.txt`, sitemap (lastmod on changed leaves), `/answers` + `/vs` hubs — all derive from the data arrays (ANSWERS/COMPARISONS) so they can't drift.
6. **Crawlable**: robots.txt allows GPTBot/OAI-SearchBot/PerplexityBot/ClaudeBot/Google-Extended/Applebot-Extended (verified both domains).
7. **Internal-link silos**: reciprocal `related` + cross-silo answer↔/vs links.
8. **Entity graph**: Organization `sameAs` (real profiles only — no dead links), suite→studio `parentOrganization`/`creator` → `tsukumo.ch/#org`, `founder` Person. tsukumo orgGraph is canonical; trovex mirrors a minimal `#org` node.

## Quality gates (hard rules — never ship without)

- JSON-LD **validates** (parses) AND **mirrors visible content**. Don't claim "no schema" from `web_fetch` (can't see JS-injected LD).
- **Honesty**: only real number is trovex **~60% fewer tokens/lookup**; `~10x` is positioning, not a metric. No fabricated proof/quotes/logos.
- **sameAs only to confirmed-live profiles** — a dead sameAs hurts the entity graph (lesson: hold X @tsukumohq until social confirms live).
- Voice: lowercase `tsukumo`/`trovex`, owner-voice, no banned slop, no em-dash filler.
- Off-site: **no live submits / no astroturf** — geo drafts the target map, a human fires. OSS surfaces = 1-line studio footnote max, never the agency pitch.
- No thin templated pSEO; no keyword stuffing (lowers citation rate).

## Veille loop (feeds the machine)

Standing monitoring in the GEO domain → memory + (proposed) Slack `#veille`:
1. **Citation share** — `growth/analytics/geo-citation-monitor.mjs` (analytics owns the run; widen to Perplexity + Google AIO, not just OpenAI). I interpret → which earned channel is working, which queries still cold.
2. **Competitor citations** — who's cited for our 10 queries (repomix, CLAUDE.md tooling, context-hub); when a competitor appears, sharpen the matching `/vs` + target.
3. **Surface opportunities** — new MCP registries / `awesome-*` lists / "best AI coding tools" listicles as they appear → add to the earned-citation target map.
4. **AEO/schema shifts** — engine sourcing changes (Reddit weighting, Speakable support, new schema types) → update this checklist.

Output → `geo-citation-rerun-baseline` + target map; flag actionable items in `team:leads`.

## Coordination (handoffs)

- **analytics** ← I supply the per-query baseline; they run the monitor + funnel scorecard.
- **content/tech-copy** ← I flag missing/uncited answers; they write the copy (I wire Speakable/schema/freshness).
- **launch/social** ← I hand the earned-citation target map; they fire (human).
- **social** → pings me when a social account goes live → I wire its `sameAs`.
