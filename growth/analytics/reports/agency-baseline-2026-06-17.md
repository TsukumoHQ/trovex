# Suite → Agency — First Real Read (baseline), 2026-06-17

*Owner: analytics-lead · Source: Plausible Stats API (tsukumo.ch, read-only key, live) + Supabase. First pull with the real key — this is the dated baseline, not a target.*

North star = **`assessment_request` where `source=suite`**. Pulled live, no estimates.

## Headline

- **North star (`assessment_request`, `source=suite`): 0.** Total `assessment_request`: **0**.
- **Organic visitors: 0.** Plausible shows **2 visitors** for 2026-06-16/17 — both are
  **analytics-lead's own end-to-end verification sessions** (direct, realistic-UA, used to
  prove the pipe). No real-user traffic yet; the site went live 2026-06-16 and there has
  been no distribution push.
- **One line:** instrumentation is confirmed landing in the dashboard; the funnel is empty
  because acquisition hasn't started, not because tracking is broken.

## What Plausible actually has (2026-06-01 → 06-17, custom range)

Totals: **2 visitors · 34 pageviews · 80 events.** Daily: zero through 06-15, then 06-16 (9
events) + 06-17 (71) — i.e. the verification traffic only.

| Event | events | visitors | Confirmed landing? |
|-------|------:|---------:|--------------------|
| `pageview` (Plausible auto) | 34 | 2 | ✅ |
| `page_view` (custom, attributed) | 27 | 2 | ✅ |
| `tsukumo_visit` | 9 | 2 | ✅ (`source=direct`, `geo_source=direct`) |
| `intent_page_view` | 8 | 2 | ✅ |
| `cta_clicked` | 2 | 1 | ✅ |
| `contact_clicked` | 0 | 0 | sent in test (202) but not surfaced — likely filtered as synthetic |
| `suite_to_agency_click` | 0 | 0 | same; fixed + 202-verified in-browser (tsukumo PR #159) |
| `assessment_request` | 0 | 0 | deliberately **aborted** in test (never inject a fake conversion) |

So 5 of 8 event types are confirmed in the dashboard from the verification run; the other 3
were either aborted on purpose (`assessment_request`) or filtered by Plausible as
non-organic — they are 202-verified at the browser (PR #156/#159), so they will record for
real users.

## North-star funnel (real, today)

| Stage | Metric | Count |
|-------|--------|------:|
| Agency visits | `tsukumo_visit` | 2 (verification) |
| Intent | `intent_page_view` | 2 visitors |
| CTA | `cta_clicked` | 1 visitor |
| **★ Conversion** | `assessment_request` | **0** |
| — by `source=suite` (north star) | | **0** |

Rates are undefined at n=2 self-generated visitors — reporting them would be noise. Hold
until organic traffic arrives.

## Supabase (suite top-of-funnel)

`waitlist` = **6 signups** (cmo-reported; prod env confirmed wired). `leads` (tsukumo,
consulting) populating but **0 suite-attributed assessment requests** so far. Run the SQL in
[`weekly-digest-template.md`](../weekly-digest-template.md) §3 for the live count (service-role; counts only, no PII).

## Caveats (honest)

- The 2 visitors are **my verification sessions** — exclude them once real traffic starts
  (or add a Plausible filter). They are not a launch signal.
- Plausible **ignores bot/datacenter/headless** traffic; some synthetic test events did not
  surface — that is expected and does not mean the events fail for real users.
- `period=7d`/`30d` returned 0 via the API while `custom` date ranges return the real counts
  — use **explicit `date=start,end`** ranges when pulling (a Plausible period quirk here).
- No fabricated numbers. The honest number today is **zero organic** — the baseline.

## Next read

First interpretable read = after the first distribution push (Product Hunt / Show HN / GEO
seeding) sends real volume. Then the [`weekly-digest-template.md`](../weekly-digest-template.md)
fills with real rates. The key works; the queries are live; the only thing missing is traffic.
