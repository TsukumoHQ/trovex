# Trovex — Tracking Plan (trovex.dev)

*Owner: analytics-lead · Status: v1 · Last updated: 2026-06-15*

Measurement comes before optimization. This is the privacy-respecting tracking plan
for the landing site `trovex.dev`. It defines the event model, the property schema,
the GEO-attribution approach, and the tooling recommendation. Other leads optimize
what this plan measures; if a surface isn't instrumented here, that's a blocking gap.

North star: **qualified reach → consulting leads**. We instrument the path
`landing_view → intent (CTA / GitHub / command copy) → install → index → first query`,
and we attribute each session to the channel that sent it (including AI engines).

---

## 1. Principles

- **Privacy-respecting by default.** Cookieless, no cross-site identifiers, no
  fingerprinting. No consent banner required (no personal data stored).
- **No PII, ever.** We aggregate. We never store raw IPs, never profile an individual
  developer. Country/region come from the provider as coarse aggregates only.
- **Honest metrics.** We measure the real number or we mark it `unknown`. We never
  estimate-as-real. The landing can measure *intent to install*; it cannot measure an
  actual install (that happens on the user's machine) — that gap is stated, not faked.
- **The CLI is the user's.** Any product-side telemetry (install / index_run /
  first_query) is **opt-in only**, consent-gated, and is out of scope for the web
  landing. See `tracking-plan.md` §6 and the activation-funnel design doc.

## 2. Tooling recommendation

**Primary: Plausible Analytics** (cloud or self-hosted).

| Why | Detail |
|-----|--------|
| Cookieless / no banner | No persistent identifiers; GDPR/PECR/CCPA-friendly with no consent gate. |
| Light | ~1 KB script, no layout cost, no Core Web Vitals hit. |
| Custom events + props | `landing_view`, `cta_clicked`, … with properties — what we need for GEO + CTA breakdowns. |
| Outbound/file auto | Auto-tracks outbound clicks (GitHub) and downloads if enabled. |
| Honest data model | Aggregate-only; we cannot reconstruct an individual even if we wanted to. |

**Baseline (zero-config, can run alongside): Vercel Web Analytics.** The site already
deploys on Vercel, so `@vercel/analytics` gives pageviews + Web Vitals with one
component and no account. Limitation: custom-event properties are thinner and
GEO-source breakdown is harder, so Plausible remains the system of record for events.
Running both is fine short-term (Vercel for Web Vitals, Plausible for the funnel).

**Rejected for now:** PostHog (session recording / autocapture is heavier than a static
landing needs and pulls toward PII); GA4 (consent banner, cookie-based, data goes to
Google — conflicts with the privacy stance). Revisit PostHog only if/when we need
product analytics on a logged-in surface (we don't have one).

Decision rule: **start with Plausible custom events on the landing.** Add Vercel WA for
Web Vitals if free. Do not add anything cookie-based.

## 3. Event model

Six core events. Names are `snake_case`, stable, and map to funnel stages.

| Event | Stage | Fires when | Key properties |
|-------|-------|-----------|----------------|
| `landing_view` | Reach | Page load (pageview) | `geo_source`, `channel`, `utm_*`, `path` |
| `cta_clicked` | Intent | Any primary/secondary CTA click | `cta_id`, `location`, `label` |
| `github_clicked` | Intent | Any link to the GitHub repo | `location` |
| `command_copied` | Intent (install proxy) | Copy button on a `uv run trovex …` command | `command`, `location` |
| `install` | Activation | **Product-side, opt-in CLI telemetry — NOT measured on the landing.** | `version`, `os_family` |
| `index_run` | Activation | **Product-side, opt-in.** First `trovex index` completes. | `doc_count_bucket` |
| `first_query` | Activation (aha) | **Product-side, opt-in.** First lookup served. | `tokens_saved_bucket` |

The landing reliably measures the **Reach + Intent** rows. `install` / `index_run` /
`first_query` are the **aha** moments but happen on the user's machine — they require
opt-in CLI telemetry (separate consent-gated channel, see §6). Until that ships, the
landing's best activation proxy is `command_copied` (copying `uv run trovex index …`)
and `github_clicked`. **We report that proxy as a proxy, never as installs.**

### 3.1 Concrete landing instrumentation map

From `web/src/App.tsx`:

| UI element | Event | Properties |
|-----------|-------|-----------|
| Nav "Get Trovex" | `cta_clicked` + `github_clicked` | `cta_id=get-trovex`, `location=nav` |
| Nav "GitHub" | `github_clicked` | `location=nav` |
| Hero "Get Trovex" | `cta_clicked` + `github_clicked` | `cta_id=get-trovex`, `location=hero` |
| Hero "See it work" | `cta_clicked` | `cta_id=see-it-work`, `location=hero` (in-page anchor) |
| Hero `Cmd` copy (`uv run trovex serve`) | `command_copied` | `command=serve`, `location=hero` |
| Bottom CTA "Get Trovex" | `cta_clicked` + `github_clicked` | `cta_id=get-trovex`, `location=cta` |
| Bottom CTA `Cmd` copy (`uv run trovex index …`) | `command_copied` | `command=index`, `location=cta` |
| Footer "GitHub" | `github_clicked` | `location=footer` |

A "Get Trovex" button is both a CTA and an outbound GitHub click — we fire both so CTA
conversion and total GitHub reach each stay clean.

## 4. Property schema

### Session/auto properties (attached to every event)

| Property | Type | Source | Notes |
|----------|------|--------|-------|
| `path` | string | `location.pathname` | Single-page today; future-proof. |
| `referrer` | string (host only) | `document.referrer` host | **Host only, never full URL** (avoids query-string PII). |
| `geo_source` | enum | derived (see §5) | `chatgpt \| perplexity \| google_aio \| gemini \| claude \| copilot \| bing \| search \| social \| direct \| unknown` |
| `channel` | enum | derived | `ai_engine \| search \| social \| referral \| direct` (coarse roll-up of `geo_source`). |
| `utm_source` / `utm_medium` / `utm_campaign` | string | query params | Lowercased; only our known set kept, else `other`. |
| `country` | string | provider aggregate | Coarse, from Plausible; we never store IPs. |
| `device` | enum | provider | `desktop \| mobile \| tablet`. |

### Event-specific properties

- `cta_id`: `get-trovex \| see-it-work`
- `location`: `nav \| hero \| compat \| tour \| faq \| cta \| footer`
- `label`: visible button text (for copy experiments)
- `command`: `serve \| index` (the proxy for which install path they took)

**Cardinality guard:** every enum is closed. Unknown values collapse to `other` /
`unknown` so we never explode property cardinality or leak a raw string that could
carry PII.

## 5. GEO / AI-engine attribution (summary)

Full design lives in `geo-attribution.md`. Summary of what the tracking plan captures:

`geo_source` is derived per session with this precedence:

1. **Explicit UTM** on links we control (`?utm_source=chatgpt`) — most reliable; we tag
   every link we seed into AI-engine answers / docs / registries.
2. **Referrer host** match — `chatgpt.com`/`chat.openai.com` → `chatgpt`,
   `perplexity.ai` → `perplexity`, `claude.ai` → `claude`, `gemini.google.com` →
   `gemini`, `copilot.microsoft.com` → `copilot`, `bing.com` → `bing`,
   `google.*` → `search` (Google AI Overviews usually inherit the plain
   `google` referrer and are **not** separable — we honestly bucket as `search`, not
   `google_aio`, unless a UTM says otherwise).
3. **Fallback** → `direct` (no referrer) or `unknown`.

**Honest limitation (stated up front):** many AI engines strip or omit the referrer, and
Google AI Overviews are not distinguishable from organic Google by referrer alone. So
AI-engine attribution is a **floor, not a census** — UTM tagging on the links we control
is the only way to raise that floor. We report `unknown`/`direct` share openly.

## 6. Product-side (CLI) telemetry — opt-in, out of scope for the landing

`install`, `index_run`, `first_query` are the real activation events but run on the
user's machine. They are deferred to an **opt-in, consent-gated** CLI telemetry design
(see activation-funnel design doc). Non-negotiables:

- Off by default. First run prints a one-line consent prompt; nothing is sent until the
  user says yes (or sets `TROVEX_TELEMETRY=1`).
- No source code, no file names, no paths, no repo identity — only coarse buckets
  (e.g. `doc_count_bucket=100-500`, `tokens_saved_bucket`).
- Anonymous install id is random per machine, rotatable, never tied to identity.
- A single documented endpoint; `TROVEX_TELEMETRY=0` hard-disables.

Until that exists, **do not claim install/activation numbers.** Use landing proxies and
GitHub stars/clones (vanity-adjacent, labeled as such).

## 7. Implementation

This plan ships with a provider-agnostic wrapper `web/src/analytics.ts`:

- A thin `track(event, props)` that calls `window.plausible(...)` if present and is a
  **no-op otherwise** — so the site has **no hard analytics dependency** and ships zero
  tracking if the script isn't loaded (privacy-first default).
- `deriveSession()` computes `geo_source` / `channel` / `utm_*` from `referrer` +
  query, host-only, closed enums.
- CTAs in `App.tsx` call `track(...)` on click. Outbound navigation is not blocked
  (events fire synchronously before default navigation).

The Plausible script tag is in `index.html`; Plausible auto-skips `localhost`, so dev
and preview don't record. It is served **first-party** — `web/vercel.json` rewrites
`/js/script.js → plausible.io/js/script.js` and `/api/event → plausible.io/api/event`
so the request is indistinguishable from our own files. This matters here: our audience
is developers, who run ad-blockers; a default third-party Plausible call loses an
estimated 5–25% of technical visitors, and the first-party proxy recovers most of them.

Shipped in this PR: `web/src/analytics.ts`, `App.tsx` event wiring (table in §3.1),
the `index.html` snippet, and the `vercel.json` proxy. `tsc -b && vite build` is green.

## 8. Definition of done

- [x] Six core events defined, mapped to funnel stages and to real UI elements.
- [x] Closed-enum property schema; host-only referrer; no PII.
- [x] GEO-source derivation defined with stated limitations.
- [x] Tooling recommended (Plausible primary, Vercel WA baseline) with rejected
      alternatives and reasons.
- [x] CLI telemetry explicitly scoped as opt-in and out of the landing.
- [x] Instrumentation built (`analytics.ts` + `App.tsx` wiring + script tag + proxy);
      build green. Merge pending review.
