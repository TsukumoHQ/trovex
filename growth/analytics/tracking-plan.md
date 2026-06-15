# Trovex — Tracking Plan (trovex.dev)

*Owner: analytics-lead · Status: v2 · Last updated: 2026-06-16*

Measurement comes before optimization. This is the privacy-respecting tracking plan for
trovex.dev — now covering the live surfaces: the home SPA, the **consulting CTA**, and the
**`/vs/` comparison pages**. It defines the event model, the property schema, GEO
attribution, and the tooling recommendation. Other leads optimize what this plan
measures; an uninstrumented surface is a blocking gap.

North star: **qualified reach → consulting leads**. We instrument
`landing_view → intent (CTA / GitHub / command copy / compare) → consult → install →
index → first query`, and attribute every session to the channel that sent it
(including AI engines).

> v2 note: rebuilt against current `main` after the landing shipped a consulting band
> (PR #18), comparison pages (PR #32), and the CLI savings auto-print (PR #11).
> Supersedes the v1 instrumentation PR.

---

## 1. Principles

- **Privacy-respecting by default.** Cookieless, no cross-site identifiers, no
  fingerprinting. No consent banner required (no personal data stored).
- **No PII, ever.** Aggregate only. No raw IPs, no profiling. Country/device come from
  the provider as coarse aggregates.
- **Honest metrics.** Measure the real number or mark it `unknown`. The landing measures
  *intent to install*; it cannot see an actual install (that's on the user's machine) —
  that gap is stated, not faked.
- **The CLI is the user's.** Product-side telemetry (install / index_run / first_query)
  is **opt-in only**, consent-gated, and out of scope for the web landing
  (see activation-funnel.md).

## 2. Tooling recommendation

**Primary: Plausible Analytics** (cloud or self-hosted) — cookieless, no consent banner,
~1 KB script, custom events + props, aggregate-only data model. **Baseline (alongside):
Vercel Web Analytics** for Web Vitals (zero-config since we deploy on Vercel).
**Rejected:** GA4 (consent banner, cookies, loses 40–60% to "reject all"); PostHog for
now (session-replay/autocapture leans toward PII; overkill for a static landing).

**Dev-audience caveat:** developers run ad-blockers, so a default third-party Plausible
call loses an estimated 5–25% of technical visitors. We serve the script **first-party**
via `vercel.json` rewrites (`/js/script.js`, `/api/event`) to recover most of them.

Decision rule: start with Plausible custom events; never add anything cookie-based.
*(Pending cmo confirmation: Plausible cloud ~$9/mo vs self-host vs Vercel-WA-only. The
event layer is provider-agnostic, so the choice is a one-block swap in `index.html`.)*

## 3. Event model

| Event | Stage | Fires when | Key properties |
|-------|-------|-----------|----------------|
| `landing_view` | Reach | SPA mount (pageview) | `geo_source`, `channel`, `utm_*`, `path` |
| `cta_clicked` | Intent | Primary/secondary CTA click | `cta_id`, `location` |
| `github_clicked` | Intent | Any link to the GitHub repo | `location` |
| `command_copied` | Intent (install proxy) | Copy button on a `uv run trovex …` command | `command`, `location` |
| `compare_clicked` | Consideration | Click to the `/vs/` comparison pages | `location` |
| `consult_clicked` | **Lead** | "Let's talk" on the consulting band | `location` |
| `install` / `index_run` / `first_query` | Activation | **Product-side, opt-in CLI telemetry — NOT measured on the landing.** | coarse buckets |

`consult_clicked` is the closest **web-measurable proxy to the north star** (a team lead
raising their hand). The activation rows happen on the user's machine and stay opt-in.

### 3.1 Instrumentation map (current `web/src/App.tsx`)

| UI element | Event(s) | Properties |
|-----------|----------|-----------|
| Nav "Get trovex" | `cta_clicked` + `github_clicked` | `cta_id=get-trovex`, `location=nav` |
| Nav "GitHub" | `github_clicked` | `location=nav` |
| Nav "Product" | `cta_clicked` | `cta_id=product`, `location=nav` |
| Hero "Get trovex" | `cta_clicked` + `github_clicked` | `location=hero` |
| Hero `Cmd` copy (`uv run trovex index …`) | `command_copied` | `command=index`, `location=hero` |
| Hero "see it work ↓" | `cta_clicked` | `cta_id=see-it-work`, `location=hero` |
| Bottom CTA "Get trovex" | `cta_clicked` + `github_clicked` | `location=cta` |
| Bottom CTA `Cmd` copy | `command_copied` | `command=index`, `location=cta` |
| **Consulting band "Let's talk →"** | `consult_clicked` | `location=consult-band` |
| Footer "Product" | `cta_clicked` | `cta_id=product`, `location=footer` |
| Footer "Compare" (`/vs/`) | `compare_clicked` | `location=footer` |
| Footer "GitHub" | `github_clicked` | `location=footer` |

### 3.2 Comparison pages (`web/public/vs/*`)

The `/vs/` pages are **static HTML**, so they can't import `analytics.ts`. Each carries:
- the **Plausible auto-pageview** snippet → reach broken down by referrer/UTM natively;
- a shared **`/vs/track.js`** (delegated click listener) that fires `github_clicked`
  and `compare_clicked` with `location=vs-<page-slug>`, so each comparison page has a
  clean per-page conversion rate (powers experiment #5). No cookies/identifiers; no-op
  without an analytics script.

All 7 pages (`vs/`, `claude-md`, `repomix`, `context-hub`, `cursor-memory`, `mem0`,
`vector-db-rag`) are wired. **Blog** (`growth/blog/*.md`) is markdown source, not deployed
HTML — nothing to instrument until those pages render on the site.

## 4. Property schema

**Session/auto** (every SPA event): `path`, `referrer` (host only, never full URL),
`geo_source`, `channel`, `utm_source` / `utm_medium` / `utm_campaign` (lowercased,
length-capped), plus provider-aggregate `country` / `device`.

**Event-specific:** `cta_id` (`get-trovex | product | see-it-work`), `location`
(`nav | hero | cta | consult-band | footer | vs-*`), `command` (`index | serve`).

**Cardinality guard:** every enum is closed; unknowns collapse to `other`/`unknown`, so
properties can't explode and no raw string (possible PII) leaks.

## 5. GEO / AI-engine attribution

Summary; full design in `geo-attribution.md`. `geo_source` precedence: explicit UTM on
links we control → referrer-host match → `direct`/`unknown` fallback. Google AI Overviews
are not separable from organic Google by referrer, so they bucket as `search` unless a UTM
says otherwise. AI-engine attribution is a **floor, not a census**; the
`utm-taxonomy-contract` (project memory) is how every lead raises that floor.

## 6. Product-side (CLI) telemetry — opt-in, out of scope here

`install` / `index_run` / `first_query` run on the user's machine and are deferred to an
**opt-in, consent-gated** CLI telemetry design (activation-funnel.md §4): off by default,
coarse buckets only, no repo identity / paths / source / query text, honor `DO_NOT_TRACK`.
Until it ships, **do not claim install/activation numbers** — use landing proxies
(`command_copied`, `github_clicked`) and GitHub stars/clones (labeled vanity-adjacent).

## 7. Implementation (this PR)

- `web/src/analytics.ts` — provider-agnostic `track()` (no-op unless `window.plausible`
  exists), cookieless `deriveSession()` (closed enums, host-only referrer).
- `web/src/App.tsx` — events wired per §3.1 (incl. `consult_clicked`, `compare_clicked`).
- `web/index.html` — Plausible snippet (auto-skips localhost).
- `web/vercel.json` — first-party proxy rewrites.
- `web/public/vs/*` — Plausible snippet on each comparison page.

`tsc -b && vite build` is green.

## 8. Definition of done

- [x] Events defined, mapped to funnel stages and to real UI elements (incl. consult + compare + vs pages).
- [x] Closed-enum property schema; host-only referrer; no PII.
- [x] GEO-source derivation with stated limits; ties to the UTM contract.
- [x] Tooling recommended (Plausible primary, Vercel WA baseline) with rejected alternatives.
- [x] CLI telemetry scoped opt-in and out of the landing.
- [x] Instrumentation built across the live surfaces; build green.
- [ ] Merge gated on cmo: confirm provider + the live third-party script.
- [ ] Fast-follow: per-page `github_clicked` on `/vs/`; `section_viewed` for scroll tests.
