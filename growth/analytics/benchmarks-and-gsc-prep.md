# Funnel Benchmark Targets + GSC Wiring Prep

*Owner: analytics-lead · Two parts: (1) what "good" looks like when traffic lands, (2) the GSC integration ready to switch on. No fabricated data — the benchmarks are EXTERNAL industry ranges, clearly labeled, to be replaced by our own once we have a clean window.*

---

## 1. Benchmark targets (calibration, not promises)

> **These are external, directional industry ranges — NOT our measured numbers and NOT
> guarantees.** They exist so a launch read isn't judged in a vacuum. **Replace each with our
> own observed rate after ~4 clean weeks** (`weekly-digest-runner.mjs`, hygiene applied). B2B
> *consulting* is low-volume / high-value: expect **lower conversion % but far higher value
> per lead** than self-serve SaaS — one qualified assessment can be a five-figure engagement.

Mapped to our live events (see `funnel-event-taxonomy`):

| Stage | Our metric | External range (directional) | Notes |
|-------|-----------|------------------------------|-------|
| Visit → intent | `intent_page_view` / `tsukumo_visit` | **~10–25%** | share who reach a consideration page; content-site typical |
| Intent → CTA | (`cta_clicked`+`contact_clicked`) / `intent_page_view` | **~5–15%** | |
| **Visit → inquiry** | `assessment_request` / `tsukumo_visit` | **~0.5–2%** | B2B website form-conversion median ~1–3%; high-ticket consulting trends to the low end |
| Inquiry → qualified | qualified (hot+warm) / `assessment_request` | **~20–40%** | lead→SQL; our `lead-scoring` bands decide it |
| Tool → result | `tool_completed` / `tool_view` | **~30–60%** | quiz/interactive completion |
| Tool → CTA | `tool_cta_clicked` / `tool_completed` | **~15–40%** | |
| Visitor → newsletter | `newsletter_signup` / `tsukumo_visit` | **~1–3%** | top-of-funnel capture |
| GEO citation share | cited / queries (`geo-citation-monitor`) | **no standard** | ours is 0/10 today; the target is *trend up*, not an absolute |

**How to use:** on a launch read, flag any stage **well below** its band as the leak to fix
(hand it to the owner per `launch-day-runbook.md`); a stage at or above band = working, invest
there. Don't treat the bands as targets to hit at n=10 — they're for a meaningful N. The
**north star stays absolute**: `assessment_request` where `source=suite` (count, then rate).

**Sourcing honesty:** the ranges above are typical B2B marketing/SaaS conversion bands from
general industry reporting — directional context only. We do not have a consulting-specific
measured benchmark, and we will not present one as if measured. Our own numbers supersede
these the moment we have them.

## 2. GSC wiring — ready to switch on

The one truly-free organic-search signal (per-page impressions, clicks, avg position) that
`blog-performance.mjs` is missing. Pull script is built: **`gsc-pull.mjs`** — runs the moment
the property is verified + a key exists. One-time setup:

1. **Verify the property:** add `https://tsukumo.ch` in Google Search Console (DNS TXT record,
   or reuse the existing Google site-verification token if one is already on the domain).
2. **Service account:** in Google Cloud, create a service account, **enable the "Search
   Console API"**, and download its JSON key.
3. **Grant access:** Search Console → Settings → Users and permissions → add the service
   account's `client_email` as a **Restricted** user (read is enough).
4. **Store the key out-of-git:** `~/.config/trovex-growth/gsc.json` (`chmod 600`). Never commit,
   never `NEXT_PUBLIC`, never log.

Then:

```bash
GSC_SA_JSON=~/.config/trovex-growth/gsc.json node growth/analytics/gsc-pull.mjs
# → per-/blog/ page: impressions | clicks | ctr | avg position (last 28d)
```

`gsc-pull.mjs` does the service-account JWT → access-token → Search Analytics `query`
(dimensions=`[page]`) flow with **no external deps** (node crypto). Its output fills the **GSC
column** in `blog-performance.md`; wire the two together once the key lands (a follow-up).

**Owner action to unblock:** steps 1–3 (verify + service account + grant). Drop the key at the
path in step 4 and ping me — I'll run it + fold rank into the blog-performance read.

## 3. Acceptance

- [x] Funnel benchmark bands per stage, mapped to our events, **labeled external/directional**, replace-with-own stated. No fabricated data.
- [x] North star stays absolute (suite-sourced assessment_request); bands are calibration, not targets-at-low-N.
- [x] GSC pull script built (`gsc-pull.mjs`, no deps, key out-of-git) + exact verify/SA/grant steps.
- [ ] Owner: verify property + service account + drop key → I run it + wire into blog-performance.
