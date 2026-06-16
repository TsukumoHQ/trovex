# Retention & Cohort Spec — warm lead → assessment over time

*Owner: analytics-lead · Status: v1 (spec) · Coordinate: fullstack (data/join), social (nurture content + UTM) · Pairs with the post-capture nurture draft (tsukumo `content/social/lead-nurture-capture.md`).*

Most consulting leads don't convert on first touch. A dev joins the trovex waitlist, reads a
nurture email two weeks later, then books an assessment. Last-touch alone misses that lag and
under-credits the nurture. This specs how to measure **warm-lead → `assessment_request` over
time** — by cohort, with nurture-step attribution — without profiling anyone.

North star unchanged: `assessment_request` where `source=suite`. This adds the **time axis**.

---

## 1. Cohort definition

A cohort = **everyone captured in the same ISO week, split by capture source**:

| Capture source | Anchor event / row | Runs nurture? |
|----------------|--------------------|---------------|
| trovex waitlist | `waitlist` row (`created_at`, source attribution) | yes — cross-property warm-up |
| tsukumo contact | `leads` row from `/api/contact` | yes — lighter warm-up |
| careers applicant | `applications` row | **no** — excluded (hiring ≠ consulting; tone-deaf) |

The anchor is the **capture timestamp**, already stored. Cohort key = `(iso_week(created_at), source)`.

## 2. The two metrics

**(a) Cohort conversion curve — capture → assessment, by weeks-since-capture.**
For each cohort, the cumulative share that has fired `assessment_request` by week W0, W1, W2…
This is the retention/activation curve for warm leads: does nurture move the curve up and
left vs the no-nurture baseline?

| Cohort (week × source) | n captured | → assessment by W0 | W1 | W2 | W4 | median lag (days) |
|------------------------|-----------:|-------------------:|---:|---:|---:|------------------:|
| 2026-W26 · trovex-waitlist | ‹› | ‹› | ‹› | ‹› | ‹› | ‹› |
| 2026-W26 · tsukumo-contact | ‹› | ‹› | ‹› | ‹› | ‹› | ‹› |

**(b) Nurture-step attribution — which email drove the return.**
A nurture click lands on tsukumo with `utm_campaign=lead-nurture` + `utm_content=nurture-e<N>`
(§4). Break `assessment_request` down by `utm_content` to see which email in the sequence
precedes conversions — so social can cut the dead steps and double the working ones.

| nurture step (`utm_content`) | assessment_request | clicks→assessment rate |
|------------------------------|-------------------:|-----------------------:|
| `nurture-e1` … `nurture-e5` | ‹› | ‹› |

## 3. Data model + the join (PII stays server-side)

- **Capture → assessment lag** needs to link a captured lead to its later assessment. Both
  rows carry the volunteered **email** in Supabase, so the join is one server-side query
  (`waitlist`/`leads` capture row ↔ later `leads` row with the assessment). **Only the
  aggregate cohort counts leave the database — never the email, never a row.**
- **Nurture-step attribution** needs no join: it's a Plausible breakdown of
  `assessment_request` by `utm_content` (the nurture link carried it).

```sql
-- (a) cohort capture→assessment lag (server-side; export counts only, never emails)
with captures as (
  select lower(email) as em, date_trunc('week', created_at) as cohort_week,
         'trovex-waitlist' as source, created_at as captured_at
  from waitlist
  union all
  select lower(email), date_trunc('week', created_at), 'tsukumo-contact', created_at
  from leads where project='tsukumo' and source = 'contact'
),
assessments as (         -- a leads row IS the assessment submission (/api/contact)
  select lower(email) as em, min(created_at) as assessed_at
  from leads where project='tsukumo'
  group by lower(email)
)
select c.cohort_week, c.source,
       count(*) as n_captured,
       count(a.em) as n_assessed,
       round(avg(extract(epoch from (a.assessed_at - c.captured_at))/86400)
             filter (where a.assessed_at >= c.captured_at)) as median_lag_days
from captures c
left join assessments a on a.em = c.em and a.assessed_at >= c.captured_at
group by c.cohort_week, c.source
having count(*) >= 5      -- k-anonymity: suppress cohorts smaller than 5
order by c.cohort_week desc;
```

```
# (b) nurture-step attribution (Plausible Stats API)
/breakdown?site_id=tsukumo.ch&period=custom&date=START,END&property=event:props:utm_content\
&filters=event:name==assessment_request;event:props:utm_campaign==lead-nurture&metrics=events
```

## 4. UTM for nurture (confirmed slug — answers the draft's open question)

Nurture emails are first-party re-engagement, so the step/sequence rides on
`utm_campaign` + `utm_content` (no closed-enum `utm_source` change needed):

| Capture source | Nurture link to tsukumo | UTM |
|----------------|-------------------------|-----|
| trovex waitlist (cross-property) | `/engagements` | `utm_source=trovex&utm_medium=oss-suite&utm_campaign=lead-nurture&utm_content=nurture-e<N>` |
| tsukumo contact | `/engagements` | `utm_medium=email&utm_campaign=lead-nurture&utm_content=nurture-e<N>` |

- `utm_campaign=lead-nurture` (the sequence), `utm_content=nurture-e<N>` (the step). Both are
  free-form — already captured by Plausible + persisted on the resulting `leads` row; **no
  `analytics.ts` change required.** Keep `utm_source=trovex` on the waitlist sequence so suite
  attribution survives (`source=suite`); the tsukumo-contact sequence has no acquisition
  source, so it reads `direct`/`email` (fine — it's a re-engagement, not new acquisition).
- This supersedes the draft's tentative `utm_campaign=consulting` for nurture — use
  `lead-nurture` so nurture is separable from cold consulting clicks.

## 5. Privacy + honesty

- **No open-pixel tracking.** Measure nurture engagement by the **click-through UTM landing**
  (a `tsukumo_visit` carrying `utm_content=nurture-e<N>`), not email opens — opens need a
  tracking pixel and are PII-adjacent. Honor unsubscribes (owner-gated sending).
- **Aggregate only.** The capture→assessment email join is server-side; only cohort counts
  leave the DB. **k-anonymity: suppress any cohort < 5** (`having count(*) >= 5`).
- **Email-mismatch undercount:** a lead who signs up and later assesses with a *different*
  email won't join → the curve is a floor, not exact. State it; don't inflate.
- **No fabricated cohorts.** Nurture is a DRAFT, owner-gated — until it sends, every cell is
  `n/a — nurture not live`. Don't model expected lift as real.

## 6. Coordination

- **fullstack** — confirm `waitlist`/`leads` carry `created_at` + the `source` discriminator
  (they do), and that the §3 cohort SQL runs against the central Supabase (read-only/service).
  No new event needed; the UTM does the nurture attribution.
- **social** — own the nurture sequence + apply the §4 UTM (`utm_campaign=lead-nurture`,
  `utm_content=nurture-e<N>`) on every link; keep careers out of it.
- **analytics-lead** — read the cohort curve + nurture-step table into the weekly digest once
  sending starts; cut/keep nurture steps off the data.

## 7. Acceptance

- [x] Cohort = capture week × source; careers excluded.
- [x] Two metrics: capture→assessment curve over weeks-since-capture + nurture-step attribution.
- [x] Data model + the server-side email join (counts only) + the Plausible breakdown.
- [x] Nurture UTM slug confirmed (`lead-nurture` / `nurture-e<N>`) — answers the draft, no enum change.
- [x] Privacy: click-through not open-pixels, aggregate, k-anon ≥5, undercount stated.
- [x] Coordination split (fullstack/social/analytics) + feeds the weekly digest.
- [ ] Activates when nurture sending is owner-approved (currently DRAFT).
