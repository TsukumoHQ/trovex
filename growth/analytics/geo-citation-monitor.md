# GEO Citation-Share Monitor

*Owner: analytics-lead · Status: v1 (live, OpenAI engine) · Coordinate: geo-lead (query backlog) · Runner: `geo-citation-monitor.mjs`*

AI engines strip referrers, so Plausible can only see GEO traffic as a `direct/unknown`
floor (confirmed in the [baseline read](./reports/agency-baseline-2026-06-17.md)). This is
the other half: probe the ICP's real questions through an AI-search engine, read the actual
citations, and record whether the suite (trovex / tsukumo / wrai.th / yoru.sh) is cited.
That turns the GEO bet into a **measurable weekly metric** — what top-1% AEO operators do:
measure citation share at the source, not guess from stripped referrers.

## What it does

`geo-citation-monitor.mjs` runs each query in [`ranking-citation-tracking.md`](./ranking-citation-tracking.md)'s
map through the **OpenAI Responses API + `web_search`** (a real AI-search surface,
≈ ChatGPT-with-search), parses the `url_citation` annotations, and writes a dated table to
`reports/geo-citations-<date>.md`: per query — did we get cited, our cited URL(s), which
competitors were cited, total citations — plus the headline **suite citation share**.

## Run it

```bash
set -a; . ~/.config/trovex-growth/openai.env; set +a   # OPENAI_API_KEY — out-of-git, never commit
node growth/analytics/geo-citation-monitor.mjs          # writes the dated report
node growth/analytics/geo-citation-monitor.mjs --dry     # print only
```

**Cadence:** weekly (pair with the weekly digest). The key is read from the environment
only; the report holds domains + counts, never a secret.

## First read — 2026-06-16 (baseline)

**Suite citation share: 0/10 (0%).** trovex/tsukumo were **not cited** for any of the 10 ICP
queries — including the *branded* "what is trovex" query (the engine doesn't surface our own
site for our own name yet). Competitors do appear (e.g. repomix on the alternatives query).
This is the honest GEO starting line: invisible. Every category row is a target for geo-lead.
Full table: [`reports/geo-citations-2026-06-16.md`](./reports/geo-citations-2026-06-16.md).

## Two cohorts — standing + offensive (added 2026-06-19)

The panel now probes **two cohorts** in one run:

- **Standing (10):** the original suite-category queries. Kept stable so the **weekly trend
  stays comparable** — don't churn this set.
- **Offensive (12):** the citation **write-list** the team is actively building answers for
  (source: memory [[citation-uncited-queries]] / `content/geo/query-gap-backlog.md`, geo-lead,
  intent×winnability scored). This is the **post-deploy verification overlay**: probe the exact
  buyer questions tech-copy/geo are targeting so "did the new page earn a citation?" is a
  measured number, not a guess. A row here flipping ✅ is the proof a page landed.

**Pre-deploy baseline — 2026-06-19: standing 0/10, offensive 0/12 (0/22 overall).** Offensive
is 0 *by definition* until the answer pages deploy and the engine indexes them — that's the
honest starting line, not a miss. Verification = re-run after each batch deploys; do **not**
block writing on it. Full table:
[`reports/geo-citations-2026-06-19.md`](./reports/geo-citations-2026-06-19.md).

## Honesty + limits

- **Sampled snapshot, not a rank.** AI answers vary by run/region/personalization. One run is
  noisy — **the weekly trend is the signal**, not any single number. Logged exactly as
  returned; nothing fabricated.
- **One engine so far.** OpenAI `web_search` is live. **Perplexity + Google AI Overviews are
  TODO** — each needs its own key (Perplexity has a citation-returning API; Google AIO has no
  API → would need a SERP provider). Add them to widen the panel; flagged to cmo.
- **Branded ≠ category.** Branded queries test whether the engine knows us; unbranded
  "category" queries are the real prize (a buyer asking generically). Track them apart.

## How it feeds the funnel

Citation share sits at the **top of the suite→agency funnel** — it's the leading indicator
for GEO-sourced reach that later shows up (partly, floored) as `geo_source=ai_engine` visits
in the [dashboard](./suite-agency-funnel-dashboard.md). Hand the not-cited category rows to
geo-lead as the answer/comparison pages to strengthen; re-run weekly to see the share move.

## Acceptance

- [x] Runner probes the ICP query set through a real AI-search engine, parses real citations.
- [x] Computes suite citation share + per-query competitor capture; dated report output.
- [x] First real read logged honestly (0/10) — no fabrication; keys out-of-git (env only).
- [x] Cadence + how-to-run + dashboard/geo-lead handoff.
- [x] Offensive cohort wired (12 write-list queries) as the post-deploy verification overlay.
- [ ] Add Perplexity + Google AIO engines (need keys) — widens the panel.
