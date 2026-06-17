# Suite → Agency — Weekly Metrics Digest (template)

> **Automated:** `weekly-digest-runner.mjs` now auto-assembles this from live Plausible +
> Supabase into `reports/agency-digest-<date>.md` (run weekly; `--since <launch-date>` for a
> clean post-launch window). This template stays as the reference shape + the manual/CRM
> fields the runner can't pull (qualified→won, experiment reads).


*Owner: analytics-lead · Cadence: weekly (Mon, covering prev Mon–Sun) · Copy per week into `growth/analytics/reports/agency-YYYY-Www.md`.*

The recurring read of the **consulting** funnel — the revenue end. Pulls **two live sources**:
Plausible custom events (verified transmitting on prod, tsukumo PR #156/#159) and the
Supabase `leads` table (`/api/contact` writes; prod env confirmed wired). The dashboard
panels + exact queries live in [`suite-agency-funnel-dashboard.md`](./suite-agency-funnel-dashboard.md);
this is the fill-in-the-blanks weekly artifact that dashboard feeds.

> Fill every `‹…›`. One screen. If a stage is unmeasurable this week, write `n/a — <why>`,
> never a guess. North star = **`assessment_request` where `source=suite`**.

---

## 0. Headline (one number + one sentence)

- **Suite-sourced assessment requests this week:** `‹n›` (vs `‹n_prev›`, `‹±%›`) — the north star.
- **All assessment requests:** `‹n›` (suite `‹n›` · content `‹n›` · referral `‹n›` · direct `‹n›`).
- **Top suite property:** ‹trovex/wraith/yoru› drove `‹n›` (via `how_heard` / referrer).
- **One sentence:** ‹what moved & why — e.g. "WRAI.TH HN post → +X tsukumo visits, X% reached the form; bottleneck is visit→cta, not reach."›
- **Lowest broken stage → next move:** ‹stage› → ‹owner + action / experiment #›.

## 1. The funnel (week over week)

Plausible events (all verified live + PII-clean). Stages 5–6 = manual CRM. Compute rates client-side from the §3 dashboard queries.

| Stage | Event | This wk | Last wk | Δ | Quality |
|-------|-------|--------:|--------:|---|---------|
| Suite reach | `oss_surface_view` (suite repos) | ‹n/a›* | ‹n/a› | — | *pending suite-side port (trovex/wraith/yoru)* |
| Suite→agency click | `suite_to_agency_click` | ‹› | ‹› | ‹› | real |
| Agency visit | `tsukumo_visit` (split `from_suite`) | ‹› | ‹› | ‹› | real |
| Intent | `intent_page_view` (by `page`) | ‹› | ‹› | ‹› | real |
| CTA / contact | `cta_clicked` + `contact_clicked` | ‹› | ‹› | ‹› | real |
| **★ Conversion** | `assessment_request` (by `source`) | ‹› | ‹› | ‹› | real |
| Qualified | proposal-worthy (CRM) | ‹› | ‹› | ‹› | manual |
| Won | `engagement_won` (CRM) | ‹› | ‹› | ‹› | manual |

**Rates that matter:** `tsukumo_visit`→`assessment_request` = `‹%›`; suite-only variant
(`source=suite` both sides) = `‹%›` (**the north-star rate**); `assessment_request`→qualified (CRM) = `‹%›`.

## 2. Attribution — Plausible vs self-report (show the disagreement)

| source (Plausible `event:props:source`) | assessment_request | Top `how_heard` | Notes |
|-----------------------------------------|-------------------:|-----------------|-------|
| **suite** (oss_suite) | ‹› | ‹› | the north-star slice |
| content (ai_engine/search/social) | ‹› | ‹› | GEO bet |
| referral | ‹› | ‹› | |
| direct / unknown | ‹› | ‹› | dark funnel → lean on `how_heard` |

- **AI-engine = floor** (referrers stripped); `direct/unknown` share = `‹%›`, shown openly.
- **Disagreement:** ‹e.g. "how_heard=trovex but referrer=direct on N leads — dark-funnel suite credit"›.

## 3. Supabase `leads` read (the durable record)

The CRM-side count, independent of Plausible (catches leads even if a client blocked the script). PII (name/email/message) is **never** copied into this digest — counts + closed-enum source only.

```sql
-- North star: suite-sourced consulting leads this week
select count(*) as suite_leads
from leads
where project = 'tsukumo'
  and created_at >= date_trunc('week', now()) - interval '7 days'
  and created_at <  date_trunc('week', now())
  and (channel = 'oss_suite' or how_heard in ('wraith','trovex','yoru'));

-- All leads by attribution (source mix)
select channel, how_heard, count(*)
from leads
where project = 'tsukumo' and created_at >= now() - interval '7 days'
group by channel, how_heard order by count(*) desc;

-- Qualified leads by band (ICP-fit; see lead-scoring.md). Qualified = hot + warm.
select coalesce(lead_band,'unscored') as band, count(*),
       count(*) filter (where channel='oss_suite' or lower(how_heard) in ('wraith','trovex','yoru')) as suite
from leads
where project='tsukumo' and created_at >= now() - interval '7 days'
group by 1;

-- Waitlist signups (top-of-funnel proxy, cross-property)
select project, count(*) from waitlist
where created_at >= now() - interval '7 days' group by project;
```

| Supabase metric | This wk | Last wk | Δ |
|-----------------|--------:|--------:|---|
| `leads` (tsukumo, all) | ‹› | ‹› | ‹› |
| **qualified leads (hot+warm)** | ‹› | ‹› | ‹› |
| — of which suite-attributed (north star) | ‹› | ‹› | ‹› |
| `waitlist` signups (all projects) | ‹› | ‹› | ‹› |

**Suite→qualified rate** = qualified suite leads ÷ suite `tsukumo_visit` = `‹%›`. The
quality metric — raw lead count can rise while qualified stays flat; report both. Bands per
[`lead-scoring.md`](./lead-scoring.md) (hot ≥55, warm ≥30; aggregate only, never per-lead).

> Careers `applications` are a **separate** funnel (hiring ≠ consulting) — track elsewhere, don't mix into the north star.

## 4. Experiments in flight

From [`experiments-batch-1.md`](./experiments-batch-1.md). One metric each; thin traffic → directional.

| # | Test | Status | Metric | Read |
|---|------|--------|--------|------|
| E1 | request-access CTA copy | ‹running/queued› | `request_access_clicked`/`landing_view` | ‹directional / "underpowered, hold"› |
| E2 | consult-band → tsukumo | ‹› | `tsukumo_clicked`/`landing_view` | ‹› |
| E3 | comparison pages × ai_engine | ‹observational› | CTA rate within `channel=ai_engine` | ‹per-page ranking → geo-lead› |

## 5. Data-quality / caveats (always fill)

- **Plausible read:** the §3 dashboard queries need a **read-only Stats API key** (still not provisioned — blocks automated pulls). Until then, pull from the Plausible **dashboard UI**. Events themselves are verified transmitting (202) on prod.
- **Suite reach (stage 1)** = `n/a` until WRAI.TH + yoru port the analytics module + fire suite-side events.
- **AI-engine attribution is a floor;** `direct/unknown` = `‹%›`.
- **Plausible ignores bot/headless traffic** — verification used a realistic UA; real-user counts are what the dashboard shows.
- Anything too-good → verify before reporting. No fabricated proof; `n/a` where unmeasured.

## 6. Decision log (≤3 lines)

- **This week's call:** ‹what changes, who owns it›.
- **Asks to cmo / leads:** ‹e.g. "provision read-only Plausible key", "cro: start E1 window B"›.

---

### How to pull (operator note)

- **Plausible:** run the §3 queries in [`suite-agency-funnel-dashboard.md`](./suite-agency-funnel-dashboard.md) (Stats API + key), or the dashboard UI → filter by custom event, break down by `source`/`geo_source`/`channel`/`how_heard` props (allow-list those custom properties in site settings).
- **Supabase:** the SQL in §3 (service-role / SQL editor). Counts only — never export PII into the digest.
- **CRM (stages 7–8):** manual, low-volume; log qualified/won by hand.
