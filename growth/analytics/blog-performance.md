# Per-Blog-Post Performance Read

*Owner: analytics-lead · Status: v1 (Plausible live; GSC + citation pending) · Pairs: geo-lead + content · Runner: `blog-performance.mjs`*

The blog is the main top-of-funnel content (~30 live posts) and the GEO baseline is 0/10 —
so content/geo are investing blind. This ranks every post by what it actually does, so effort
goes to the few that drive the funnel and the dead tail gets reworked or cut. No fabricated
data: a post with no traffic reads 0.

## What it does

`blog-performance.mjs` reads the live sitemap for every `/blog/<slug>`, pulls **Plausible
pageviews + visitors per post** (last 30d), and writes a ranked table to
`reports/blog-performance-<date>.md`. Two columns are left as documented-pending until their
access lands (below).

## Run it

```bash
set -a; . ~/.config/trovex-growth/plausible.env; set +a   # out-of-git key
node growth/analytics/blog-performance.mjs                 # writes the dated report
```

**Cadence:** weekly, with the digest.

## First read — 2026-06-17 (baseline)

**30 posts · 8 with any pageviews · 19 total pageviews.** Pre-launch: tiny and mostly
crawler/verification traffic, not organic readers. Honest baseline; the ranking only becomes
meaningful after a distribution push sends real volume. Full table:
[`reports/blog-performance-2026-06-17.md`](./reports/blog-performance-2026-06-17.md).

## The three layers

| Layer | Status | Source |
|-------|--------|--------|
| **Pageviews / visitors per post** | ✅ live | Plausible Stats API (keyed) |
| **AI-cited?** | partial | a `/blog/` URL appearing in [`geo-citation-monitor`](./geo-citation-monitor.md) output; per-post needs the **post→target-query map** (geo-lead owns wording) |
| **GSC position / impressions** | ⏳ pending creds | Google Search Console Search Analytics API (dimension=page) — needs an OAuth/service-account credential + a verified `tsukumo.ch` property |
| **Sessions → lead per post** | ⏳ v2 | Plausible funnel `entry_page=/blog/X → assessment_request` — needs traffic to power |

## Asks (to cmo)

- **GSC API access** (service account + verified `tsukumo.ch`) → fills the rank column, the
  one truly-free organic-search signal. Out-of-git, same pattern as the other keys.
- **geo-lead:** a post→target-query map so the citation column is per-post, not domain-level.

## How it feeds the funnel

Top posts by pageviews (and later by GSC rank + sessions→lead) = where content/geo double
down; the zero-traffic tail = rework or cut. Pairs with the GEO citation hit-list
([`geo-citation-hitlist` memory](./ranking-citation-tracking.md)) so we make the *winning*
topics citable, not random ones. Feeds the [weekly digest](./weekly-digest-template.md).

## Honesty

- Live pageviews only; GSC/citation/conversion columns read `pending` until keyed — never
  estimated. Pre-traffic counts are labeled as crawler/verification, not organic.
- No fabricated rankings; the tail isn't "failing", it's *unmeasured until traffic*.

## Acceptance

- [x] Runner pulls every live post + real Plausible pageviews/visitors → ranked dated report.
- [x] First baseline read logged honestly (8/30, 19 pageviews, pre-traffic).
- [x] GSC + per-post citation + sessions→lead specced as pending layers with the access asks.
- [ ] Add GSC pull once credentialed; add the per-post citation map (geo-lead); funnel v2 on traffic.
