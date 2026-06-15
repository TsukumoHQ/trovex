# Experiment — "Request beta access" CTA copy A/B

*Owner: analytics-lead · Status: designed, ready to run · Last updated: 2026-06-16 · Coordinate with: cro-lead (owns App.tsx CTA)*

The waitlist CTA is the top of the primary funnel now (`request_access_clicked →
waitlist_submitted`). Small copy changes on the highest-traffic button are the cheapest
conversion lever. This designs the test; cro-lead wires the chosen mechanism.

---

## Hypothesis

The CTA's framing changes how many visitors start the waitlist flow. A benefit/early-access
frame ("early access") may beat a transactional one ("request access") — or vice-versa.
We don't know; we measure.

## Variants (one control + two)

| Variant | Copy | Frame |
|---------|------|-------|
| **A (control)** | `Request beta access` | neutral, honest, matches the private-beta reality |
| B | `Get early access` | benefit / scarcity |
| C | `Join the private beta` | belonging / exclusivity |

Copy must pass the **anti-ai-slop copy-gate** (memory `copy-gate`) and the voice rules —
no hype words, lowercase `trovex`, developer-honest. All three above are clean.

## Success metric (one)

**Primary:** `request_access_clicked` / `landing_view` (CTA click-through rate).
**Guardrail (must not drop):** `request_access_clicked → waitlist_submitted` (a flashier
label that pulls clicks but not submits is a loss). Secondary read: overall
`landing_view → waitlist_submitted`.

Declared before start; no switching metrics mid-flight.

## Assignment mechanism (low-traffic-aware)

trovex.dev is low-traffic pre-launch, so a concurrent 3-way split is underpowered. Two
options, pick with cro:

1. **Recommended — sequential painted-door:** ship A for a fixed window (e.g. 1–2 weeks or
   until N clicks), then B, then C; compare windows. Simplest, no bucketing code; confound
   = time/traffic-mix (note it). Good when volume is tiny.
2. **Concurrent split (if volume rises):** assign a `variant` (A/B/C) once per visitor via
   `sessionStorage` (cookieless, no PII, cleared on tab close) and attach it as a
   `variant` prop to `request_access_clicked` + `waitlist_submitted`. I can add a tiny
   `getExperimentVariant('cta-copy')` helper to `analytics.ts` when we choose this path —
   not shipping dead code before then.

Either way, **tag the variant** so it's measurable: `variant` event prop (concurrent) or
the window dates (sequential). For inbound campaign links, `utm_content=cta-a|cta-b|cta-c`
can carry it too (see `utm-convention.md`).

## Sample size / decision rule (honest)

At pre-launch volume this won't hit p<0.05 fast. Rule: run until each variant has **≥100
`request_access_clicked`** OR 2 weeks, whichever first; then **judge directional +
qualitative**, not as if significant. If two variants are within a few points, keep the
control (A) — it's the most honest label. Ship the winner, re-run only if a variant clearly
leads.

## Rollout

1. cro-lead picks mechanism (default: sequential) and wires variant A copy first (already
   the planned CTA), calling `trackRequestAccessClick(location)` (live in `analytics.ts`).
2. analytics-lead adds the `variant` prop/helper only if concurrent split is chosen.
3. Read in the weekly north-star report (experiments section), then decide.

## Acceptance

- [x] Hypothesis + one control + two variants (copy-gate-clean).
- [x] Single success metric + guardrail (clicks that don't convert = loss).
- [x] Low-traffic-aware assignment (sequential default; concurrent split path defined).
- [x] Honest sample-size/decision rule (directional, keep control on a tie).
- [x] Coordination + rollout steps with cro-lead; uses the live `request_access_clicked` event.
