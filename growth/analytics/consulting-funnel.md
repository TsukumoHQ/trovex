# Trovex/Tsukumo — Cross-Property Consulting-Lead Funnel + Attribution

*Owner: analytics-lead · Status: v1 · Last updated: 2026-06-16 · Spans repos: trovex, WRAI.TH, yoru, **tsukumo** (agency site, separate repo)*

The business is the **consulting agency Tsukumo** (tsukumo.ch). The AGPL OSS suite is the
funnel into it:

- **WRAI.TH** — public, multi-agent orchestration (likely the biggest top-of-funnel)
- **trovex** — context / SSOT layer (private beta)
- **yoru.sh** — observability

North star = **consulting leads**, attributed back to *which OSS property and which
channel* drove them. This defines that funnel, the attribution method, the metric, and
the readout. Implementation spans repos; the agency-site pieces are a **handoff** to
whoever builds `tsukumo` (Next.js + Vercel).

---

## 1. The funnel

```
[channel] → [OSS property: WRAI.TH / trovex / yoru] → discover the suite → tsukumo.ch → consulting inquiry → qualified → engagement
```

Canonical event taxonomy (memory `funnel-event-taxonomy`; launch #54
`content/funnel-wiring.md`; tsukumo `src/lib/analytics.ts`):

| # | Stage | Where measured | Event / signal |
|---|-------|----------------|----------------|
| 1 | Awareness (per property) | each property's own analytics | `oss_surface_view` by `geo_source`/`channel` |
| 1b | Adoption | suite repos | `oss_adopt` (install / waitlist / discord) |
| 2 | Suite → agency | property sites (suite repos) | `suite_to_agency_click` + **UTM** (`utm_source=wraith\|trovex\|yoru`, `utm_campaign=suite`) |
| 3 | Agency visit | tsukumo.ch | `tsukumo_visit` (`from_suite`, `source`) → `intent_page_view` |
| 4 | **Assessment request** | tsukumo.ch form | `assessment_request` (the conversion) |
| 5 | Qualified / proposal | CRM (manual) | `proposal_sent`; triaged as a real fit |
| 6 | Engagement | CRM (manual) | `engagement_won` — signed / scoped work (the money) |

Stage 4 (`assessment_request`) is the **primary web-measurable conversion**; stages 5–6
are manual CRM stages (high value, low volume) — the honest revenue end. Every tsukumo
event rides `source` (`suite\|referral\|content\|direct`). **North star =
`assessment_request` where `source=suite`** ("does the OSS suite produce consulting
leads?").

## 2. Attribution — three signals, because B2B journeys are long + dark

A dev meets WRAI.TH on HN, tries trovex months later, then googles the agency. Last-click
alone under-credits the OSS suite. We triangulate:

1. **UTM (links we control).** Every OSS property → tsukumo.ch link carries
   `utm_source=<property>` + medium/campaign (see §3). Reliable for the *last OSS touch*.
2. **Referrer host.** tsukumo.ch reads `document.referrer` host → `trovex.dev` /
   `wrai.th` / `yoru.sh` / AI-engine / search (same closed-map approach as
   `geo-attribution.md`). Backstop when UTM is missing.
3. **Self-reported "how did you hear about us?"** — a required closed dropdown on the
   inquiry form. **The most reliable signal for consulting** (captures the dark funnel that
   UTM/referrer miss). Options (closed): `WRAI.TH` · `trovex` · `yoru` · `search / Google` ·
   `AI assistant (ChatGPT/Perplexity/Claude)` · `HN / Reddit / Lobsters` · `X / LinkedIn` ·
   `word of mouth / referral` · `other`.

**Reported primary = self-report, with UTM/referrer as the corroborating/auto signal.** We
show all three and the disagreement, rather than trusting last-click. No cross-domain
identity stitching (privacy + complexity not worth it).

## 3. Cross-property UTM (extends `utm-convention.md`)

When an OSS property links to the agency site, tag it so tsukumo.ch knows the source:

| From | Link to tsukumo.ch | UTM |
|------|--------------------|-----|
| trovex.dev (e.g. consult band) | tsukumo.ch | `?utm_source=trovex&utm_medium=oss-suite&utm_campaign=consulting` |
| WRAI.TH site/README | tsukumo.ch | `?utm_source=wraith&utm_medium=oss-suite&utm_campaign=consulting` |
| yoru.sh | tsukumo.ch | `?utm_source=yoru&utm_medium=oss-suite&utm_campaign=consulting` |

New closed `utm_source` values: `trovex`, `wraith`, `yoru` (the properties). Add to each
property's analytics source map + the agency site's. Suite cross-links *between* OSS
properties use `utm_medium=suite-crosslink`.

## 4. The agency inquiry form (handoff spec for the tsukumo repo)

Mirror the trovex waitlist pattern (`waitlist-tracking.md`), privacy-respecting:

- On submit success → fire `assessment_request` with **source attribution only**
  (`source_property`, `channel`, `utm_*`, `referrer` host, `how_heard`) — **never** the
  name/email/company (that PII goes to the CRM/first-party store only).
- POST the inquiry with the page's derived attribution (a `getAttribution()` equivalent on
  tsukumo) **+ the `how_heard` dropdown value**, persisted next to the contact in the CRM
  so every lead is source-attributed.
- `how_heard` is a closed dropdown (§2) — required, so the dark-funnel is captured.
- Honeypot + no PII in analytics/logs (same rules as the waitlist endpoint).

Provide an analytics module on tsukumo equivalent to trovex's `web/src/analytics.ts`
(closed enums, host-only referrer, no-op-safe). I'll port it when the repo lands.

## 5. The consulting-lead metric + readout

- **Consulting-lead metric** = a submitted `assessment_request` on tsukumo.ch (stage 4).
  Qualified-lead = stage 5 (CRM). Both reported; stage 4 is the leading indicator.
- **Weekly readout — leads by source property × channel:**

| Source property | Inquiries | Top channel (how_heard / utm) | → Qualified | Notes |
|-----------------|----------:|-------------------------------|------------:|-------|
| WRAI.TH | ‹› | ‹› | ‹› | biggest TOF expected |
| trovex | ‹› | ‹› | ‹› | beta cohort + awareness |
| yoru | ‹› | ‹› | ‹› | |
| direct / search / other | ‹› | ‹› | ‹› | dark funnel → lean on how_heard |

- **Rates:** property-site → tsukumo click-through; tsukumo session → `assessment_request`;
  inquiry → qualified → engagement (CRM).
- **Self-report vs auto disagreement** shown openly (e.g. "how_heard says trovex, referrer
  says direct" — the dark-funnel signal).
- This is the **top-line north-star readout**; trovex's own waitlist/awareness readouts
  (`north-star-report-template.md`, `waitlist-funnel-report.md`) feed the trovex row.

## 6. Honesty / privacy

- Inquiry PII (name/email/company) lives only in the CRM/first-party store — **never** in
  analytics. Attribution events carry source only.
- No fabricated leads/case-study numbers (cmo rule). Mark `n/a` until tsukumo.ch + a CRM
  exist; the agency repo isn't built yet, so stages 4–6 are **specced, not yet measured**.
- AI-engine/dark-social attribution is a floor; `how_heard` is the honest counterweight.
- Cross-property awareness (stages 1–2) needs WRAI.TH + yoru to carry the same analytics
  as trovex — flag as a per-property rollout (trovex is the reference impl).

## 7. Acceptance

- [x] Cross-property funnel defined (channel → property → suite → agency → inquiry → qualified → engagement).
- [x] Attribution = UTM + referrer + required `how_heard` self-report; primary = self-report, triangulated.
- [x] Cross-property UTM scheme (`utm_source=trovex|wraith|yoru`) extending the convention.
- [x] Agency inquiry-form handoff spec (PII in CRM only, attribution in analytics, honeypot).
- [x] Consulting-lead metric + weekly leads-by-property×channel readout (top-line north star).
- [ ] Build on tsukumo repo when it lands: port the analytics module + wire the form + `how_heard`.
- [ ] Per-property: WRAI.TH + yoru adopt trovex's analytics for stages 1–2.
