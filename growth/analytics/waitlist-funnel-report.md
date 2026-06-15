# Trovex — Waitlist Funnel Report (signups by source)

*Owner: analytics-lead · Cadence: weekly, leads the north-star readout · Copy per week into `growth/analytics/reports/YYYY-Www-waitlist.md`.*

The operational weekly readout of the primary conversion: **waitlist signups, by source**,
plus the CTA-click→submit rate. Two data sources, both first-party:
- **Plausible** — the web funnel (`landing_view → request_access_clicked → waitlist_submitted`) by `geo_source`/`channel`/`utm_*`.
- **Waitlist store** — the stored signups, each now carrying source attribution (PR #102).

Honest rule: report the real number or `n/a`. The email is never in this report — only
counts and source.

---

## 0. Headline

- **Signups this week:** `‹n›` (vs `‹n_prev›`, `‹±%›`).
- **Top source:** ‹channel/engine› = `‹n›`.
- **CTA→submit rate:** `‹%›`. **Overall (sessions→submit):** `‹%›`.
- **One line:** ‹what moved + the lowest broken step (reach / CTA pull / form completion)›.

## 1. Signups by source

From the waitlist store (each record carries `geo_source, channel, utm_source,
utm_medium, utm_campaign, utm_content, referrer`). Roll up by `channel`, then by
`utm_source`/`geo_source` within it.

| Channel | Signups | Top source (utm_source / geo_source) | Notes |
|---------|--------:|--------------------------------------|-------|
| ai_engine | ‹› | ‹perplexity/chatgpt/claude › | floor — stripped referrers land in direct |
| search | ‹› | ‹google› | incl. Google AI Overviews (not separable) |
| social | ‹› | ‹x/reddit/hackernews/linkedin› | ‹campaign?› |
| referral / registry / newsletter | ‹› | ‹mcp-registry/newsletter› | |
| direct / unknown | ‹› | — | **floor caveat** — stripped AI/dark-social here |

- **UTM coverage:** `‹% of signups with a known utm_source›`. Low → leads aren't tagging links (`utm-convention.md`).

## 2. The web funnel (Plausible)

| Step | Metric | This wk | Last wk | Δ |
|------|--------|--------:|--------:|---|
| Reach | sessions (`landing_view`) | ‹› | ‹› | ‹› |
| CTA intent | `request_access_clicked` | ‹› | ‹› | ‹› |
| **Conversion** | `waitlist_submitted` | ‹› | ‹› | ‹› |

- **CTA→submit** = `waitlist_submitted` / `request_access_clicked` = `‹%›`.
- **Read `request_access_clicked` per `location`** (`nav`/`hero`/`waitlist`) — it fires on
  button click *and* input focus, so don't sum blindly (see `verify-live-events.md` §3).
- **Reconcile** Plausible `waitlist_submitted` vs store signups — they should be close; a
  gap means ad-blockers dropped the event (store is the source of truth for the count) or
  the provider isn't live yet.

## 3. How to pull it

- **Store (signups + source):**
  - KV (Upstash/Vercel): `SMEMBERS trovex_waitlist` → each member is JSON
    `{ts, email, geo_source, channel, utm_*, referrer}`. Drop `email`, group by `channel`/
    `utm_source`, filter `ts` to the week. (A 20-line script; never export `email`.)
  - GitHub-issue mode: filter issues labeled `waitlist`, parse the `source:` block.
- **Web funnel (Plausible):** Goals `request_access_clicked` + `waitlist_submitted`,
  break down by `geo_source`/`channel`/`utm_source`/`location`.
- **Until a provider/storage is wired:** mark `n/a` — the endpoint 503s and Plausible
  records nothing pre-deploy. Don't fabricate.

## 4. Into the north-star readout

This report's headline (signups + top source + CTA→submit) **is** §0–1 of the
north-star weekly report (`north-star-report-template.md`). Beta lifecycle past signup
(access→activation) lives in `beta-funnel-dashboard.md`. One source of truth, no
double-keeping.

## 5. Acceptance

- [x] Signups by UTM source + GEO referrer (channel rollup, floor caveat).
- [x] CTA-click→submit rate + the per-`location` read caveat.
- [x] Pull recipe for both the store (source of truth for count) and Plausible.
- [x] Honest `n/a`-until-wired; email never in the report.
- [x] Wired into the north-star readout (no double-keeping).
