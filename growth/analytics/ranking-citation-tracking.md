# Trovex — SEO Ranking + AI-Citation Tracking

*Owner: analytics-lead · Status: v1 · Last updated: 2026-06-16 · Coordinate with: geo-lead*

The awareness lever is non-gated (unlike the waitlist), and GEO/AEO compounds regardless
of beta timing. This plan tracks two things for the comparison/answer/tool pages:

1. **SEO rank** — which queries surface trovex in Google, at what position.
2. **AI citation** — which AI engines (ChatGPT, Perplexity, Google AI Overviews, Claude)
   *cite* trovex.dev when asked the target query.

It feeds the **awareness readout** at the top of the north-star funnel
(citations/rankings → sessions by `geo_source` → waitlist).

Honesty up front: Google rank is measurable for real (Search Console). **AI citation has
no official rank API and engines are non-deterministic** — we track it by **sampled
prompt-audits** and report observed snapshots, never as a guaranteed position.

---

## 1. The page × query map (what we're tracking)

Each GEO page targets one real query/competitor. Track each as a row.

**Comparison (`/vs/`) — competitor queries:** `claude-md`, `repomix`, `context-hub`,
`cursor-memory`, `mem0`, `vector-db-rag` (e.g. "trovex vs repomix", "repomix
alternative", "CLAUDE.md vs …").

**Answers (`/answers/`) — intent queries:** `stop-agent-rereading-docs`,
`reduce-agent-token-costs`, `shared-source-of-truth-multiple-agents`,
`canonical-context-for-agents`, `bigger-context-window-rereading` (the slug ≈ the query).

**Tool (`/for/`) — "context for <tool>" queries:** `claude-code`, `cursor`, `cline`,
`windsurf`.

geo-lead owns the target-query wording per page; analytics-lead owns the tracking.

## 2. Layer A — SEO rank (real, free)

**Tool: Google Search Console** (verify `trovex.dev` — DNS or the existing Vercel
deploy). Once verified it gives, per query and per page, **real** impressions, clicks,
average position, CTR. No sampling.

Weekly pull (Performance report), one row per tracked page:

| Page | Top query | Impressions | Clicks | Avg position | CTR |
|------|-----------|------------:|-------:|-------------:|----:|
| /vs/repomix | repomix alternative | ‹› | ‹› | ‹› | ‹› |
| /answers/reduce-agent-token-costs | reduce agent token costs | ‹› | ‹› | ‹› | ‹› |
| … | | | | | |

Also submit `sitemap.xml` in GSC and watch coverage (indexed vs excluded) — a page that
isn't indexed can't rank. `llms.txt` is already shipped for AI-crawler guidance.

## 3. Layer B — AI citation (sampled, honest)

No engine exposes a citation-rank API, and answers vary by session/region/personalization.
So we **sample**: run each page's target query in each engine on a cadence and record
whether trovex is **cited** (linked/named), and roughly where.

**Matrix (weekly, one tab per engine):**

| Query (page) | ChatGPT | Perplexity | Google AIO | Claude | Notes |
|--------------|:-------:|:----------:|:----------:|:------:|-------|
| "stop my agent rereading docs" (/answers/stop-agent-rereading-docs) | cited? pos | cited? pos | cited? | cited? | which competitors cited too |

- **Record:** `cited` (yes/no) + approximate position/prominence + competitors also cited.
- **Cadence:** weekly manual pass to start (cheap, ~20 queries × 4 engines). If it earns
  budget, automate with an API (Perplexity API; SerpAPI/Serpstack for Google AIO presence)
  — **optional, not assumed**; note cost before buying.
- **Determinism caveat:** log the date + that it's a snapshot. Two runs can differ. Report
  trend (cited in N of last M checks), not a single reading as truth.
- **Reproducibility:** keep the exact prompt per query in the sheet so checks are comparable.

## 4. Connect to on-site signal

An AI engine that cites trovex sends a click → already attributed by `geo_source` /
`channel` (`geo-attribution.md`): a rise in `ai_engine` sessions for a page is the
*downstream* proof that a citation is live, even when the engine stripped the referrer
(floor caveat applies). When geo-lead seeds a link we control into an answer, tag it
(`utm-convention.md`, `utm_medium=ai_answer`). So three signals triangulate:

1. **Citation audit** (Layer B) — is the engine citing us?
2. **`ai_engine` sessions** (Plausible `geo_source`) — is it sending clicks?
3. **GSC** (Layer A) — classic rank for the same query.

## 5. Awareness readout (feeds north-star)

Weekly, per page: `GSC avg position` · `impressions` · `AI-cited in N/4 engines` ·
`ai_engine sessions` → and the funnel continues `→ request_access_clicked →
waitlist_submitted`. The point: prove which **queries/pages** actually drive aware,
converting traffic, so geo-lead invests there — not in pages that rank but never convert.

## 6. Honesty / privacy

- GSC = real. AI-citation = sampled snapshots; report "cited in N of last M checks", never
  a fabricated rank. Engines are non-deterministic — say so.
- No user data; this is external monitoring of our own pages.
- No fabricated proof; if a page isn't indexed or isn't cited, report that plainly.

## 7. Acceptance

- [x] Page × query map for all `/vs/`, `/answers/`, `/for/` pages.
- [x] Layer A: GSC real-rank pull (impressions/clicks/position/CTR + sitemap coverage).
- [x] Layer B: AI-citation sampled matrix (4 engines), determinism + reproducibility caveats, optional automation flagged with cost.
- [x] Triangulation with `ai_engine` sessions (`geo_source`) + UTM for seeded links.
- [x] Feeds the awareness readout / north-star; honest, no fabricated ranks.
- [ ] Operator/geo-lead: verify `trovex.dev` in GSC; geo-lead confirms the target query per page.
