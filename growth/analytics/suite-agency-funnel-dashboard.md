# Suite → Agency Funnel Dashboard + First Attribution Read

*Owner: analytics-lead · Status: v1 · Last updated: 2026-06-16 · Spans: trovex, WRAI.TH, yoru, **tsukumo** (agency, separate repo)*

The **buildable** dashboard for the OSS-suite → consulting funnel. Where
[`consulting-funnel.md`](./consulting-funnel.md) defines the funnel + attribution *method*,
this doc is the operator's panel: every tile mapped to a **live Plausible custom event**,
the **exact query** to pull it, and the honest **first read** of current data.

Tsukumo analytics is **live** (`src/lib/analytics.ts`, verified in tsukumo PR #130).
Events flow to Plausible (`data-domain=tsukumo.ch`). This dashboard reads them.

North star = **`assessment_request` where `source=suite`** — "does the OSS suite produce
consulting leads?"

---

## 0. Prerequisite (one-time, blocks the live read)

Plausible's Stats API needs (a) an **API key** (read-only) and (b) the **custom properties
allow-listed** in site settings so they're queryable by breakdown:

```
source · geo_source · channel · from_suite · page · location · from_tool · how_heard ·
utm_source · utm_medium · utm_campaign · utm_content
```

Until the key exists, the panels below are **specced and verified-firing, but unread**
(§6). Provision a read-only key in Plausible → tsukumo.ch → Settings → API Keys, store it
in the analytics runner env (never in git), and the §3 queries return numbers as-is.

---

## 1. Funnel tiles (top to bottom = the journey)

Each tile = one Plausible custom event from the live taxonomy. Period default = **30d**
(B2B journeys are long); also show **7d** for momentum.

| # | Tile | Event | What it answers |
|---|------|-------|-----------------|
| 1 | **Suite reach** | `oss_surface_view` (suite repos) | how many met an OSS property — by `geo_source` |
| 2 | **Adoption** | `oss_adopt` | installs / waitlist / discord joins |
| 3 | **Suite → agency click** | `suite_to_agency_click` | crossed from a property toward tsukumo |
| 4 | **Agency visits** | `tsukumo_visit` | landed on tsukumo.ch — split `from_suite` true/false |
| 5 | **Intent** | `intent_page_view` | viewed an intent page — by `page` |
| 6 | **CTA / contact** | `cta_clicked` + `contact_clicked` | clicked toward the inquiry |
| 7 | **★ Assessment request** | `assessment_request` | **THE conversion** — by `source`, `how_heard` |
| 8 | Qualified / won | CRM (manual) | `proposal_sent`, `engagement_won` — the money |

Tiles 1–3 only fill once the **suite repos** (trovex/WRAI.TH/yoru) port the analytics
module and fire suite-side events — trovex is the reference impl; WRAI.TH + yoru are a
per-property rollout (tracked in `consulting-funnel.md` §7). Tiles 4–7 are **live on
tsukumo now**. Tile 8 is manual CRM (low volume, high value).

## 2. The three headline numbers (render big)

1. **North star — suite-sourced assessment requests (30d):**
   `assessment_request` filtered `source==suite`. The one number that proves the model.
2. **Total assessment requests (30d):** all `source`. Leading revenue indicator.
3. **Suite → agency conversion:** `assessment_request` ÷ `tsukumo_visit` (all sources),
   and the suite-only variant (`source==suite` numerator and denominator). Honest rate,
   not a vanity count.

## 3. Exact Plausible Stats API queries (v1)

Base: `GET https://plausible.io/api/v1/stats/{endpoint}` · header
`Authorization: Bearer $PLAUSIBLE_API_KEY` · `site_id=tsukumo.ch`.

```bash
# (1) North star — suite-sourced assessment requests, 30d
/aggregate?site_id=tsukumo.ch&period=30d&metrics=events\
&filters=event:name==assessment_request;event:props:source==suite

# (2) Assessment requests broken down by source (suite|referral|content|direct)
/breakdown?site_id=tsukumo.ch&period=30d&property=event:props:source\
&filters=event:name==assessment_request&metrics=events

# (3) Assessment requests by self-report (the dark-funnel truth)
/breakdown?site_id=tsukumo.ch&period=30d&property=event:props:how_heard\
&filters=event:name==assessment_request&metrics=events

# (4) GEO / LLM-referrer panel — agency visits by AI engine + suite + channel
/breakdown?site_id=tsukumo.ch&period=30d&property=event:props:geo_source\
&filters=event:name==tsukumo_visit&metrics=events,visitors
/breakdown?site_id=tsukumo.ch&period=30d&property=event:props:channel\
&filters=event:name==tsukumo_visit&metrics=events,visitors

# (5) Funnel volumes (run per event, same period) → compute step rates client-side
/aggregate?site_id=tsukumo.ch&period=30d&metrics=events&filters=event:name==tsukumo_visit
/aggregate?site_id=tsukumo.ch&period=30d&metrics=events&filters=event:name==intent_page_view
/aggregate?site_id=tsukumo.ch&period=30d&metrics=events&filters=event:name==cta_clicked
/aggregate?site_id=tsukumo.ch&period=30d&metrics=events&filters=event:name==assessment_request

# (6) Intent pages by label (which intent surface pulls)
/breakdown?site_id=tsukumo.ch&period=30d&property=event:props:page\
&filters=event:name==intent_page_view&metrics=events
```

A thin runner (Node/Python script or SQL-on-export) loops these, writes a dated row, and
renders §4 + §5. No PII is ever in the response — events carry closed-enum source only.

## 4. GEO / LLM-referrer attribution panel

The point of GEO: prove that AI engines (ChatGPT/Perplexity/Claude/Gemini/Copilot) and the
OSS suite — not just Google — drive qualified agency visits. From query (4):

| geo_source | channel | Visits (`tsukumo_visit`) | → Assessment requests | Notes |
|------------|---------|--------:|--------:|-------|
| chatgpt / perplexity / claude / gemini / copilot | `ai_engine` | ‹› | ‹› | the GEO bet |
| trovex / wraith / yoru | `oss_suite` | ‹› | ‹› | **the north-star source** |
| search / bing | `search` | ‹› | ‹› | incl. Google AI Overviews (not separable by referrer) |
| social / producthunt | `social` | ‹› | ‹› | HN/Reddit/X/LinkedIn/PH |
| referral | `referral` | ‹› | ‹› | other inbound |
| direct / unknown | `direct` | ‹› | ‹› | dark funnel → lean on `how_heard` |

**Caveat (honesty):** AI engines strip referrers and rarely pass UTM, so `direct/unknown`
is inflated and `ai_engine` is a **floor**, not the true number. The `how_heard` self-report
(query 3) is the counterweight — show both and the disagreement, never trust last-click.

## 5. Leads-by-source readout (the weekly north-star body)

| Source property | Assessment requests | Top `how_heard` | → Qualified (CRM) | → Won |
|-----------------|--------------------:|-----------------|------------------:|------:|
| WRAI.TH | ‹› | ‹› | ‹› | ‹› |
| trovex | ‹› | ‹› | ‹› | ‹› |
| yoru | ‹› | ‹› | ‹› | ‹› |
| content (ai_engine/search/social) | ‹› | ‹› | ‹› | ‹› |
| direct / referral | ‹› | ‹› | ‹› | ‹› |

Feeds the weekly north-star report (`north-star-report-template.md`) — one source of truth,
no double-keeping. **Best source = highest qualified-per-visit, not highest raw visits.**

## 6. First attribution read — live data, 2026-06-16

**Honest status: insufficient data — no read yet.** Two reasons, both stated plainly:

1. **No Plausible Stats API key available** to me (no public/shared dashboard either:
   `plausible.io/share/tsukumo.ch` → 404; the API returns *"Missing API key"*). I will not
   estimate or fabricate counts. The §3 queries are ready to run the moment a read-only key
   is provisioned (§0).
2. **The site is freshly live.** Tsukumo analytics shipped recently and tsukumo PR #130
   (the QA pass) deployed today; the suite-side tiles (1–3) need WRAI.TH/yoru to port the
   module first. So even with a key, the current window is **pre-meaningful-traffic** —
   expected counts are ~0 to single digits and not yet interpretable.

**Therefore the first real read = the baseline capture.** Once the key lands: run §3, record
the dated zero/low baseline verbatim, and re-read weekly. Do not call a launch "flat" off a
pre-traffic window. First interpretable read expected after the first distribution push
(Product Hunt / Show HN / GEO seeding) sends real volume.

**What IS verified now (tsukumo PR #130, live QA):** every tile-4–7 event fires correctly
and is PII-clean — so when traffic arrives, the dashboard reads true. Instrumentation is
not the blocker; the API key + traffic are.

## 7. Honesty / privacy

- Events carry **closed-enum source only**; name/email/company/message live solely in the
  Supabase `leads` store (`assessment_request` carries `source` + `how_heard`, never PII).
- `ai_engine` attribution is a **floor**; `how_heard` is the honest counterweight; the
  `direct/unknown` share is shown openly.
- No fabricated leads/rates. Tiles read `n/a` until measured — never invented.
- **Open dependency:** `assessment_request` + lead capture both require tsukumo
  `/api/contact` to return 200 (prod `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` set). If
  unset, the form 503s and tile 7 stays 0 regardless of traffic. Flagged to cmo/fullstack
  (see tsukumo PR #130).

## 8. Acceptance

- [x] Every funnel tile mapped to a live taxonomy event + the exact Plausible query.
- [x] Three headline numbers defined (north star, total, suite→agency rate).
- [x] GEO/LLM-referrer attribution panel with the AI-engine-floor caveat.
- [x] Leads-by-source readout feeding the weekly north-star report (no double-keeping).
- [x] First live read attempted; **honestly reported as insufficient/no-key**, baseline-capture plan given — no fabricated numbers.
- [ ] Operator: provision a read-only Plausible API key (§0) → unblocks the read.
- [ ] Per-property: WRAI.TH + yoru port the analytics module → fills tiles 1–3.
