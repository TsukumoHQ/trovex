# Trovex — Beta Funnel Dashboard (signup → access → activation)

*Owner: analytics-lead · Status: v1 · Last updated: 2026-06-16*

The operational dashboard for the private beta. It tracks the full lifecycle —
**waitlist signup → access granted → activated → retained → consulting lead** — by source,
and it **leads the north-star weekly report**. Goal: see not just how many sign up, but
which sources produce *activated* beta users (and consulting conversations), so we invest
in the channels that convert, not the ones that just spike.

Privacy first: signup email + access status live in the **first-party waitlist store**;
activation is **opt-in** beta-cohort telemetry. Analytics events carry source only, never
the email.

---

## 1. The beta funnel

| # | Stage | Definition | Source of truth | Available now? |
|---|-------|-----------|-----------------|----------------|
| 1 | **Signup** | `waitlist_submitted` | waitlist store (email + attribution) + Plausible event | ✅ once form is wired |
| 2 | **Access granted** | invite sent / accepted | waitlist store `status` field | ✅ when invites start |
| 3 | **Onboarded** | first `trovex index` on the beta build | opt-in beta telemetry / self-report | ⏳ needs opt-in telemetry |
| 4 | **Activated** | first query with `saved > 0` (the aha) | opt-in beta telemetry | ⏳ needs opt-in telemetry |
| 5 | **Retained** | usage on ≥2 distinct days | opt-in beta telemetry | ⏳ |
| 6 | **Consulting lead** | beta user → consulting conversation | manual/CRM (low volume, high value) | ✅ logged by hand |

**The metric that matters most:** `access_granted → activated`. A private beta exists to
find product-market fit; the share of invited users who reach the aha is the truest signal,
and it's measurable per **source** (which channel's signups actually activate).

## 2. Source attribution (every stage sliced by source)

Each signup carries `{geo_source, channel, utm_source, utm_medium, utm_campaign,
utm_content, referrer}` persisted at submit (see `utm-convention.md` §4 +
`waitlist-tracking.md`). So every downstream stage inherits the source, and we can ask:
*"of Perplexity-sourced signups, what % activated?"* — not just *"how many signed up?"*.

For clients that stripped the UTM (AI engines / dark social), the `referrer`-host fallback
(`geo-attribution.md`) still buckets them; the `direct/unknown` share is reported openly.

## 3. The dashboard (what to render)

A weekly table, source × stage, plus the key rates. Built from the waitlist store
(stages 1–2, 6) + opt-in beta telemetry aggregate (stages 3–5). Until telemetry exists,
stages 3–5 are `n/a` and we say so.

| Source | Signups | Access granted | Activated | Retained | → Consulting |
|--------|--------:|---------------:|----------:|---------:|-------------:|
| ai_engine (chatgpt/perplexity/claude) | ‹› | ‹› | ‹n/a› | ‹n/a› | ‹› |
| search | ‹› | ‹› | ‹n/a› | ‹n/a› | ‹› |
| social (HN/Reddit/X/LinkedIn) | ‹› | ‹› | ‹n/a› | ‹n/a› | ‹› |
| referral / registry / newsletter | ‹› | ‹› | ‹n/a› | ‹n/a› | ‹› |
| direct / unknown | ‹› | ‹› | ‹n/a› | ‹n/a› | ‹› |

**Headline rates:** signup→access `‹%›`; **access→activated `‹%›` (the PMF signal)**;
activated→retained `‹%›`; signup→consulting `‹%›`. **Best source** = highest
*activated-per-signup*, not highest signups.

## 4. Data sources & how to build it

- **Stages 1–2, 6 (available now):** query the waitlist store. Minimum schema:
  `email, created_at, status (waitlisted|invited|active), invited_at, activated_at?,
  geo_source, channel, utm_source, utm_medium, utm_campaign, utm_content, referrer,
  consulting_flag`. A small script (or SQL view) rolls it up by `channel`. **The email is
  never exported into any analytics/report — only counts and source.**
- **Stages 3–5 (deferred):** opt-in beta telemetry. Because beta users are invited and
  few, a consented, coarse-bucket telemetry is the cleanest path (off by default, honor
  `DO_NOT_TRACK`, no repo/paths/source/query text — same rules as `activation-funnel.md`
  §4). Until it ships, mark `n/a`; optionally a one-question "did you run your first
  query?" in the beta onboarding email as a low-fi proxy (self-report, labeled as such).
- **Cross-check reach:** Plausible (`landing_view`, `request_access_clicked`,
  `waitlist_submitted` by `channel`) for the top of the funnel.

## 5. Relationship to the north-star report

This beta funnel **is** the body of the weekly north-star report
(`north-star-report-template.md`): the report's headline = signups + best source; this
dashboard supplies the signup→access→activation→lead detail. One source of truth, no
double-keeping.

## 6. Honesty

- Stages 3–5 are `n/a` until opt-in telemetry (or labeled self-report) exists — never
  fabricate activation.
- Report `access→activated` even when small; a private beta with few but activating users
  beats many dormant invites.
- `direct/unknown` source share shown openly; AI-engine attribution is a floor.

## 7. Acceptance

- [x] Beta lifecycle defined stage-by-stage with source of truth + availability.
- [x] Every stage sliced by source (UTM + referrer fallback); `access→activated` named as the PMF signal.
- [x] Dashboard table + headline rates; build path from waitlist store + opt-in telemetry.
- [x] Privacy: email never in analytics; activation opt-in; honest `n/a` where unmeasured.
- [x] Tied to the north-star report (no double-keeping).
- [ ] Follow-up: opt-in beta telemetry (separate task) unblocks stages 3–5.
