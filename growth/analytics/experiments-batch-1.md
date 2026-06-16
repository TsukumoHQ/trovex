# Experiments — Batch 1 (the first 3, stood up)

*Owner: analytics-lead · Status: ready to run · Last updated: 2026-06-16 · Coordinate with: cro-lead (owns the surfaces/copy)*

The first three conversion experiments, pulled from the ICE backlog
([`experiment-backlog.md`](./experiment-backlog.md)) and reconciled to the current
north-star (beta phase: **waitlist signups** are the primary conversion; **consulting
leads** are the revenue end). Each is **runnable now** because its success metric is a
**live** event — no new tracking blocks it.

**Method, given the traffic reality.** trovex.dev / tsukumo.ch are pre-launch and thin.
Concurrent A/B is underpowered at this volume, so batch 1 runs **sequential (E1/E2)** or
**observational (E3)** — judged **directional + qualitative**, not as if significant. One
metric per test, declared up front, no peeking-to-stop, keep the control on a tie. When a
distribution push (Product Hunt / Show HN / GEO seeding) lifts volume, promote E1 to a
concurrent split using the variant contract in §4 (ship the helper *then*, not before — no
dead bucketing code while sequential is the honest method).

---

## E1 — "Request beta access" CTA copy *(primary beta conversion)*

Full design: [`ab-request-access-cta.md`](./ab-request-access-cta.md). Summary:

- **Hypothesis:** the CTA frame changes how many visitors start the waitlist flow.
- **Variants:** A `Request beta access` (control) · B `Get early access` · C `Join the private beta`. Copy-gate-clean (no hype, lowercase `trovex`).
- **Success metric (one):** `request_access_clicked` / `landing_view` (CTA CTR).
- **Guardrail (must not drop):** `request_access_clicked → waitlist_submitted`. A flashier label that pulls clicks but not submits is a **loss**.
- **Events (live):** `landing_view`, `request_access_clicked`, `waitlist_submitted` — all in `web/src/analytics.ts`.
- **Mechanism:** sequential painted-door (A → B → C, fixed windows). No code needed now.
- **Decision:** run each variant to ≥100 `request_access_clicked` or 2 weeks; directional; keep A on a near-tie.
- **Owner split:** cro-lead swaps the CTA copy per window (`App.tsx`); analytics-lead reads it.

## E2 — Consult-band → tsukumo handoff *(suite → agency, consulting north-star proxy)*

Backlog #1. The consult band on trovex.dev is the closest web proxy to the consulting
north-star (`assessment_request where source=suite`), measured one hop earlier.

- **Hypothesis:** sharper team-lead framing (and/or higher placement) of the consult band lifts intent to cross to the agency.
- **Variants:** A current band (control) · B sharper "working with a team?" team-lead framing, same low-key posture (no sales-page tone — voice rules).
- **Success metric (one):** `tsukumo_clicked` / `landing_view` (cross-to-agency rate). `consult_clicked` is the secondary read if the band CTA is the consult link vs the tsukumo link.
- **Guardrail:** must not depress `request_access_clicked` (the consult band shouldn't cannibalize the primary beta CTA).
- **Events (live):** `consult_clicked`, `tsukumo_clicked`, `landing_view`.
- **Mechanism:** sequential window (A then B). The crosslink must carry `?utm_source=trovex&utm_medium=oss-suite&utm_campaign=consulting` so tsukumo reads it as `source=suite` (closes the loop to the §E2 metric's downstream `assessment_request`).
- **Decision:** directional; keep A unless B clearly leads AND the guardrail holds.
- **Owner split:** cro-lead wires the band copy/placement + the UTM'd link; analytics-lead reads both sides (trovex `tsukumo_clicked` + tsukumo `tsukumo_visit{source=suite}`).

## E3 — Comparison pages convert AI-engine traffic *(the GEO bet — observational)*

Backlog #5 + #6. The 7 `/vs/` pages are the GEO play; with per-page events live we can read
**which page** and **which channel** actually convert — no split needed, so it runs today.

- **Hypothesis:** `/vs/` pages convert AI-engine-sourced visitors to the primary CTA better than the home page does; and the competitor framings differ in conversion (tells geo-lead where to invest).
- **Success metric (one):** primary-CTA rate **within `channel=ai_engine`** = `request_access_clicked` / `landing_view`, segmented by page (`/vs/<competitor>` vs home). `github_clicked` is a secondary read where a page's CTA is the repo.
- **Read 2 (allocation):** per-`/vs/`-page `request_access_clicked` rate, all channels — rank the 6 competitor framings (claude-md / repomix / mem0 / cursor-memory / vector-db-rag / context-hub) to direct content effort.
- **Events (live):** `landing_view`, `request_access_clicked`, `github_clicked`, `compare_clicked` (per page, attributed by `channel`).
- **Mechanism:** **observational** — no variant assignment; the pages already exist and self-segment by `path` + `channel`. Pure Plausible breakdown.
- **Decision:** report the ranking + the ai_engine-vs-home delta directionally; hand geo-lead the winners/losers. Re-read after GEO seeding sends real AI-engine volume.

---

## 4. Variant-tagging contract (for when a test goes concurrent)

Batch 1 is sequential/observational, so **no bucketing code ships now**. When traffic
justifies a concurrent split (promote E1 first), drop this reusable, cookieless,
no-PII helper into `web/src/analytics.ts` (mirror it in tsukumo `src/lib/analytics.ts`):

```ts
/* Cookieless A/B assignment: sessionStorage-scoped (cleared on tab close), no PII.
 * Stable per session for one experiment key. Pass the result as a `variant` prop on
 * the experiment's success event so Plausible can break the metric down by variant. */
export function getExperimentVariant(key: string, variants: readonly string[] = ['A', 'B']): string {
  const fallback = variants[0] ?? 'A'
  if (typeof window === 'undefined' || variants.length === 0) return fallback
  const storeKey = `trovex_exp_${key}`
  try {
    const existing = window.sessionStorage.getItem(storeKey)
    if (existing && variants.includes(existing)) return existing
    const pick = variants[Math.floor(Math.random() * variants.length)]
    window.sessionStorage.setItem(storeKey, pick)
    return pick
  } catch {
    return variants[Math.floor(Math.random() * variants.length)] // storage blocked → in-memory, never throw
  }
}
```

Usage (E1 concurrent): `const v = getExperimentVariant('cta-copy', ['A','B','C'])` → render
that copy → `trackRequestAccessClick(location)` with `{ variant: v }` merged. Plausible:
`breakdown ... property=event:props:variant filters=event:name==request_access_clicked`.
Custom property `variant` must be allow-listed in both sites' Plausible settings.

Sequential alternative (no code): tag windows by date, or carry `utm_content=cta-a|cta-b|cta-c`
on inbound campaign links (see `utm-convention.md`).

## 5. Honesty / privacy

- One metric per test, declared up front; directional judgement at thin traffic; keep the control on a tie.
- No PII in any event — `variant` + closed-enum source only; email/inquiry PII stays in the first-party store.
- No fabricated results; no social-proof test until real testimonials exist.
- E1's downstream and E2's whole readout depend on the live funnel being reachable — `waitlist_submitted` needs the trovex waitlist backend wired, and the E2→`assessment_request` tail needs tsukumo prod Supabase env (flagged to cmo, tsukumo PR #130). Sequential reads of the *click* metrics work regardless.

## 6. Coordination + rollout (with cro-lead)

1. **cro-lead** runs E1 window A (current copy is already control) → then B → then C; wires E2 band copy + the UTM'd tsukumo link. No analytics changes needed from cro for batch 1.
2. **analytics-lead** reads E1/E2/E3 in the weekly north-star report (experiments section) off the live Plausible events; promotes E1 to concurrent (ship §4 helper) when volume rises.
3. **geo-lead** receives E3's per-page ranking to direct comparison-page effort.

## 7. Acceptance

- [x] 3 experiments locked, each = one hypothesis + one success metric + variants + decision rule.
- [x] Every metric is a **live** event (no test blocked on tracking).
- [x] Reconciled to north-star (waitlist primary; consulting proxy; GEO bet).
- [x] Thin-traffic method: sequential/observational now, concurrent-ready contract documented (no dead code).
- [x] Privacy/honesty: one metric, no PII, no fabricated results, dependencies flagged.
- [x] cro/geo coordination + rollout steps.
