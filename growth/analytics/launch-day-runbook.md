# Launch-Day Measurement Runbook (first 48h)

*Owner: analytics-lead · Use when a distribution push (Product Hunt / Show HN / GEO seed) goes live. Goal: act on day-1 signal in hours, not discover it a week later. Everything here reuses what's already built.*

Baselines are all **0** (pre-launch was crawler+verification noise — see `traffic-hygiene.md`),
so **any non-zero after launch = real.** Don't overreact to n=1; do react to a stage that
stays at 0 while the one above it climbs.

## T-0 (hour before launch)

- [ ] **Hygiene on:** every team member has run `localStorage.plausible_ignore="true"` on
      tsukumo.ch (`traffic-hygiene.md` §2). Confirm Plausible "Bot filtering" = ON.
- [ ] **Lock the launch date** = `LAUNCH` (YYYY-MM-DD). Every read below uses `--since=$LAUNCH`
      so the window is clean (excludes the noisy pre-launch baseline).
- [ ] **Links tagged:** confirm the launch links carry UTM (`utm-convention.md`) — PH =
      `utm_source=producthunt`, HN = the source slug — else the channel decays to `direct`.

## T0 → +48h — watch in funnel order (leading → lagging)

Run the three runners (keys: `set -a; . ~/.config/trovex-growth/{plausible,supabase}.env; set +a`):

```bash
node growth/analytics/weekly-digest-runner.mjs --since $LAUNCH   # funnel + qualified + new surfaces
node growth/analytics/blog-performance.mjs                       # which posts pull (set window in-script)
node growth/analytics/geo-citation-monitor.mjs                  # AI citation share (re-run daily)
```

Watch these fire, in order — each is the gate for the next:

| # | First signal | Source | Means |
|--:|--------------|--------|-------|
| 1 | First **real visitor** (not direct/noise) | digest GEO table | the push is landing; which channel |
| 2 | First **intent_page_view** | digest funnel | visitors go past the hero |
| 3 | First **cta_clicked / tool_completed** | digest funnel / tool | intent → action |
| 4 | First **assessment_request** | digest ★ | THE conversion (north star if `source=suite`) |
| 5 | First **qualified lead** (hot/warm) | digest headline | the *right* lead, not just any |
| 6 | First **AI citation** of the suite | citation monitor | GEO bet starting to pay |
| + | **newsletter_signup / tool funnel** | digest new-surfaces | community/top-of-funnel capture |

## Same-day action — flag the lowest-converting stage

Compute the step rates from the digest and **name the leak**, then hand the owner:

- **Reach but no intent** (visits ↑, `intent_page_view` flat) → hero/positioning → **cro + content**.
- **Intent but no CTA** (`intent_page_view` ↑, `cta_clicked` flat) → CTA clarity/placement → **cro** (run an ICE experiment).
- **CTA but no assessment** (`cta_clicked` ↑, `assessment_request` 0) → form friction or the assessment page → **cro + fullstack** (check `/api/contact` 200).
- **Assessments but not suite-sourced** (`source≠suite`) → the OSS→agency funnel isn't carrying UTM → **geo/social** (tag suite links).
- **Assessments but low qualified%** (`cold` dominates) → wrong audience → **content/geo** retarget; re-check the `lead-scoring` rubric.
- **Traffic but 0 citations** → the GEO hit-list (`geo-citation-hitlist` memory) is the content backlog → **geo + content**.

One message to cmo/owner per day for the first 2 days: *the leak + who owns it + the one number that moved it.*

## Cadence

Daily for the first week (the funnel is small + fast-moving), then back to the weekly
`weekly-digest-runner.mjs`. Keep `--since=$LAUNCH` until a full clean week exists, then roll to 7d windows.

## Honesty

- Any number that looks too good → verify before reporting (check it isn't a bot/our own traffic).
- n=1 is a signal something *works*, not a rate — report counts early, rates once N is meaningful.
- No fabricated wins; a stage at 0 is reported at 0 with the owner named to fix it.
