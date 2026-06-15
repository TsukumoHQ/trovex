# Trovex — Waitlist Conversion Tracking

*Owner: analytics-lead · Status: v1 · Last updated: 2026-06-16*

Under the hybrid private-beta GTM (memory `gtm-model`), **waitlist signup is the primary
conversion** (and the consulting-lead source). The repo is private; "Get trovex / install
now" is replaced by **"request beta access"**. This doc defines how we measure that funnel,
privacy-respectingly, and the exact hooks the waitlist surface must call.

---

## 1. The funnel

`landing_view → request_access_clicked → waitlist_submitted`, sliced by `geo_source` / `channel` / `utm_*`.

| Step | Event | Fires when | Notes |
|------|-------|-----------|-------|
| Reach | `landing_view` | SPA mount | already live |
| Intent | `request_access_clicked` | "request beta access" CTA clicked | replaces `github_clicked` as the intent signal |
| **Conversion** | `waitlist_submitted` | waitlist form submits **successfully** | the primary metric |

Old `github_clicked` / `command_copied` stay as secondary curiosity signals but are **no
longer the conversion** — the repo is private, so a GitHub click is not adoption.

## 2. Hooks (ready in `web/src/analytics.ts`)

The CTA + form live in `App.tsx` (cro-lead's file). These one-call helpers make it
instrumented from birth — **cro-lead / whoever builds the form calls them**:

```ts
import { trackRequestAccessClick, trackWaitlistSubmitted, getAttribution } from './analytics'

// on the "request beta access" CTA:
onClick={() => trackRequestAccessClick('hero')}   // or 'nav' | 'cta' | 'consult-band'

// on a SUCCESSFUL submit (after the endpoint returns 2xx):
trackWaitlistSubmitted()

// to PERSIST source with the signup, send this with the POST body (server stores it):
fetch('/api/waitlist', { method: 'POST', body: JSON.stringify({ email, ...getAttribution() }) })
```

## 3. Privacy (non-negotiable)

- **The email is volunteered PII for the beta.** It lives only in the first-party
  waitlist store (Vercel fn → storage / GitHub issue per `gtm-model`). It is **never**
  sent to analytics. `waitlist_submitted` carries source attribution only.
- `getAttribution()` returns closed-enum `geo_source` / `channel` / `utm_*` + host-only
  `referrer` — no PII — so the server can attribute the signup to a source.
- No cookies, no cross-site identifiers, no fingerprinting.
- Don't log the email to any analytics/event pipeline. Storage ≠ analytics.

## 4. Server-side capture (for the waitlist endpoint)

The endpoint should persist, next to each signup: `email`, `created_at`, and the
attribution object (`geo_source`, `channel`, `utm_source/medium/campaign/content`,
`referrer` host). That makes **signups-by-source** queryable even for clients that strip
UTMs (referrer-host fallback) — see `utm-convention.md`. Store raw UTM strings server-side
too if useful, but keep them out of any third-party tool.

## 5. Reporting

The north-star weekly report now **leads with `waitlist_submitted` by source** (see
`north-star-report-template.md` §0–1). Key rates: `landing_view → request_access_clicked`
(CTA pull), `request_access_clicked → waitlist_submitted` (form completion),
`landing_view → waitlist_submitted` (overall), each split by `channel`.

## 6. Status / handoff

- [x] Events + helpers shipped in `analytics.ts` (`request_access_clicked`,
      `waitlist_submitted`, `getAttribution`).
- [x] North-star report updated to lead with waitlist.
- [ ] **cro-lead:** wire the CTA → `trackRequestAccessClick`, and the form success →
      `trackWaitlistSubmitted`; POST `getAttribution()` with the signup.
- [ ] **backend/whoever owns the endpoint:** persist the attribution object with each
      signup (§4). UTM convention in `utm-convention.md`.
