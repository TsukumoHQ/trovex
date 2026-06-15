# Trovex — Activation Funnel + Install→Repeat Measurement

*Owner: analytics-lead · Status: v1 · Last updated: 2026-06-15*

How we measure whether a visitor becomes an activated, repeat user — and where the
funnel leaks. North star: **qualified reach → consulting leads**; activation is the hinge
in the middle (`landing → install → index → first query → repeat`). 2026 is
retention-first: a leaky bucket makes reach worthless, so we measure the bucket before we
pour more in.

Privacy rule up front: the landing is measured with cookieless web analytics; everything
past `install` runs on the **user's machine** and is **opt-in only**. Trovex already
computes the activation data locally — we are choosing what (if anything) a user may
*optionally* share, not adding surveillance.

---

## 1. The funnel

| # | Stage | Definition | Where it's measured | Honest? |
|---|-------|-----------|---------------------|---------|
| 0 | `landing_view` | Page load on trovex.dev | Web (Plausible), with `geo_source` | Real |
| 1 | Intent | CTA / GitHub click / `command_copied` | Web (Plausible) | Real **proxy** for install intent |
| 2 | `install` | trovex installed + runnable on the machine | Local only | Not web-visible; opt-in to aggregate |
| 3 | `index_run` | First `trovex index` completes | Local — first row in `index_runs` | Real, local |
| 4 | `first_query` | First lookup served via MCP | Local — first row in `mcp_queries` | Real, local |
| 5 | **aha** | First query returns a real **tokens-saved** number > 0 | Local — `savings.py` `SavingsRow.saved` | Real, local |
| 6 | `repeat` | Queries on ≥2 distinct days (or sessions) | Local — `mcp_queries.ts` spread | Real, local |
| 7 | Lead | "working with a team? let's talk" → contact | Web/outbound | Real (low volume) |

**Key honesty point:** the web can only see stages 0–1 (+7). Stages 2–6 happen locally.
So **we never report installs/activations from the landing** — we report the Intent
*proxy* (`command_copied`, `github_clicked`) and, separately, *opt-in* local aggregates.
Conflating the two would be a fabricated activation number.

## 2. What Trovex already measures locally (no new code needed)

The CLI/MCP server already logs the activation signal on the user's machine:

- `index_runs` — `ts, duration_sec, added, updated, unchanged, removed` per index. First
  row = stage 3.
- `mcp_queries` — `ts, user, query, n_results` per lookup. First row = stage 4; the
  `ts` spread across days = stage 6 (repeat). `insights.py` already derives
  `top_queries` / `failed_queries` / `repeated_queries`.
- `savings.py` `SavingsRow` — `queries, would_have_read, actual_read, saved, ratio`.
  `saved > 0` = stage 5 (aha). This is the number the dashboard already shows.

So for a **single user**, the whole activation funnel is computable today, locally, from
real data. `trovex stats` + the savings dashboard already surface most of it.

### 2.1 The aha must be loud (cro-lead aligned)

The aha (stage 5) is currently behind the dashboard. Recommendation (hand to cro-lead /
product): **auto-print the savings line right after the first query**, e.g.

```
trovex: served 1 canonical doc · ~280 tokens (saved ~1,240 vs reading 3 files)
```

Time-to-aha drops from "go find the dashboard" to "first query." This is a product
change, not analytics — flagged, not owned here.

## 3. Install→repeat (retention) definition

- **Activated install** = reached stage 5 (first query with `saved > 0`).
- **Repeat user** = ≥2 query-days in `mcp_queries` (a query on a later distinct calendar
  day, local tz). Day-grain, not session-grain, because a CLI has no login/session.
- **W1 retention** = activated installs that have a query-day in days 1–7 after first
  query. **W2** = days 8–14. Reported as a curve, not a single number.
- **Repeat ratio** (proxy when we lack cross-user data) = from one user's own local data:
  query-days ÷ days-since-install. Directional only.

## 4. Cross-user aggregation = opt-in telemetry (off by default)

To know *what share of installs* reach each stage across users, we need an aggregate.
This is the only part that leaves the machine, and it is **opt-in only** (see
tracking-plan.md §6). Design:

- **Off by default.** First run prints a one-line consent prompt; nothing sent until the
  user opts in (or sets `TROVEX_TELEMETRY=1`). `TROVEX_TELEMETRY=0` and `DO_NOT_TRACK=1`
  hard-disable. Honor both.
- **Events = funnel stage reached, once each:** `installed`, `first_index`,
  `first_query`, `activated` (saved>0), `repeat` (2nd query-day).
- **Properties = coarse buckets only.** `doc_count_bucket` (`<50 | 50-500 | 500-5k | 5k+`),
  `tokens_saved_bucket`, `os_family`, `trovex_version`. **Never** the query text, the
  user header, file paths, repo identity, or doc contents — `mcp_queries.query` and
  `user` stay strictly local.
- **Identity** = a random, rotatable install id (so we can de-dupe stages without knowing
  who). Not tied to anything.
- **One documented endpoint.** Minimal payload. No IP stored server-side.

Until this ships, cross-user activation is **unmeasured** and we say so. GitHub
stars/clones are the only cross-user reach signal and are labeled vanity-adjacent.

## 5. Activation-metric method (for when data exists)

Don't hand-pick the activation metric — derive it (PostHog method): define 5–10 candidate
event-groups (e.g. *{first_query}*, *{first_query, saved>0}*, *{≥3 queries in week 1}*,
*{index + 5 queries}*), and once opt-in data exists, test which group best correlates with
W2+ retention. The winning group becomes the official "activated" definition. Hypothesis
to test first: **`saved>0` on first query** is the activation event (the visible aha).

Pre-launch we have no data, so this is staged, not run now — flagged so we run it the week
after telemetry + traffic exist, never retrofitted to look good.

## 6. North-star dashboard (reach → leads)

One view, three layers, each labeled by data quality:

1. **Reach** (web, real): `landing_view` by `geo_source`/`channel`; GitHub stars/clones
   (vanity-adjacent).
2. **Intent** (web, real proxy): `cta_clicked`, `github_clicked`, `command_copied` rates.
3. **Activation** (local, opt-in aggregate): stage-3→6 conversion + W1/W2 retention curve.
   Marked "opt-in sample, not census."
4. **Leads** (outbound, real, low-volume): consulting contacts.

The single number on top = **qualified-reach→lead rate**: of sessions from a real channel
(AI-engine/search/community), how many become a consulting contact. Optimize the
*lowest* stage, not the top.

## 7. Acceptance

- [x] Funnel defined stage-by-stage with the data source and honesty status of each.
- [x] Maps to real local schema (`index_runs`, `mcp_queries`, `savings.py`) already present.
- [x] Install→repeat retention defined (query-day grain, W1/W2 curve).
- [x] Cross-user aggregation scoped as opt-in, coarse-bucket, no query text / no PII.
- [x] Activation-metric derivation method staged for post-data.
- [x] North-star dashboard layered reach→leads with data-quality labels.
- [ ] Follow-ups (not this doc): build opt-in telemetry (separate task); product auto-prints
      the aha savings line (cro-lead/product); wire the dashboard once provider confirmed.
