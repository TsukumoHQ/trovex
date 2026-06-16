# Trovex — Experiment Backlog (ICE-scored)

*Owner: analytics-lead · Status: v2 (refreshed for live instrumentation) · Last updated: 2026-06-16*

Prioritized A/B / optimization experiments, pulled from the other leads' shipped work.
Every test is one hypothesis + one success metric + an ICE score. **No test runs before
its metric is live** — and as of PR #37/#56/#59 the web funnel **is** live (Plausible
custom events + Vercel WA on the home SPA; `github_clicked` / `compare_clicked` on all 7
`/vs/` pages; `consult_clicked` on the consulting band). So the web tests below are now
**ready**, not blocked. Only the activation/retention tests still wait on opt-in telemetry.

---

## What changed since v1

- **Tracking is live** → `command_copied`, `cta_clicked`, `github_clicked`,
  `compare_clicked`, `consult_clicked` all fire. Confidence scores rise for the
  web-measurable tests (we can now actually read them).
- **New live surfaces:** consulting band (`consult_clicked`), 7 comparison pages
  (per-page `github_clicked`), the CLI savings **auto-print shipped** (#11) — so the aha
  is live even though *measuring* its retention effect still needs opt-in telemetry.
- Still blocked on telemetry: anything reading `install` / `first_query` / `repeat`.

## Reading the scores

**ICE** = Impact × Confidence × Ease, each 1–10, mean (1 decimal). Confidence now also
reflects "the metric is live and readable." Pre-launch traffic is still thin → see below.

## Traffic reality

Low pre-launch traffic. **Sequential / before-after** with a `variant` prop, judged
**directional + qualitative** until traffic powers significance. One live test per
surface; one success metric per test, declared up front; no peeking-to-stop.

## Backlog (ranked)

| # | Hypothesis | Variant(s) | Success metric (one) | Source | ICE | Status |
|---|-----------|-----------|----------------------|--------|-----|--------|
| 1 | Consult-band copy/placement lifts consulting-lead intent | current vs sharper team-lead framing / higher placement | `consult_clicked` / sessions | cro-lead PR#18 | **7.7** | **ready** (metric live) |
| 2 | One primary CTA above the fold beats two | 1 CTA vs CTA+secondary | `github_clicked` / sessions | cro-lead | **7.3** | **ready** |
| 3 | First-query savings auto-print raises repeat usage | aha line on vs off | `repeat` (2nd query-day) | cro-lead PR#11 (shipped) | **7.3** | blocked — opt-in telemetry |
| 4 | Hero copy-command `index` (value step) gets copied more than `serve` | `index /path` vs `serve` | `command_copied` / sessions | cro-lead | **6.7** | **ready** |
| 5 | Comparison pages convert AI-engine traffic better than home | `/vs/` vs home for `channel=ai_engine` | `github_clicked` rate within `ai_engine` | geo-lead #32/#49 | **6.7** | **ready** (per-page events live) |
| 6 | Which competitor framing converts best (allocate content effort) | claude-md / repomix / mem0 / cursor-memory / vector-db-rag / context-hub | per-page `github_clicked` rate | geo-lead | **6.7** | **ready** (observational, no split) |
| 7 | A sharper H1/deck lifts engagement past the hero | current vs content-lead variant | `section_viewed` past hero | content-lead | **6.3** | **ready** (`section_viewed` live) |
| 8 | A shareable savings receipt seeds referral sessions | receipt share on vs off | referred sessions (`utm_medium=referral`) | cro-lead #24/#50 | **5.7** | needs receipt feature + UTM |
| 9 | MCP-registry listing copy lifts registry→site intent | listing A vs B | `utm_source=mcp-registry` × `github_clicked` | launch-lead | **5.7** | needs UTM on listings |
| 10 | FAQ order/added objection reduces hero-only bounce | current vs reordered | `cta_clicked` after FAQ view | cro/content | **5.3** | needs `section_viewed` |

(#10-style social-proof test stays out until real testimonials exist — never fabricate.)

## Batch 1 — the first 3, stood up → [`experiments-batch-1.md`](./experiments-batch-1.md)

Reconciled to the beta-phase north-star (**waitlist signups** primary; **consulting leads**
the revenue end), the first three locked experiments are:

1. **E1 — request-access CTA copy** (`ab-request-access-cta.md`) — the **primary beta
   conversion** (`request_access_clicked` / `landing_view`). Promoted above the old #1
   because the waitlist, not a github star, is the trovex conversion now.
2. **E2 — consult-band → tsukumo handoff** (backlog #1) — closest web proxy to the
   consulting north-star; metric `tsukumo_clicked` / `landing_view`, UTM'd to `source=suite`.
3. **E3 — comparison pages convert AI-engine traffic** (#5 + #6) — the GEO bet, observational
   (per-page × `channel`), hands geo-lead the allocation ranking.

Each runs on a **live** event; sequential/observational at current thin traffic (see the
batch-1 doc for the method + the concurrent-ready variant contract).

## Instrumentation status

`section_viewed { section }` (scroll-depth / hero-pass / FAQ) is **shipped + live** in
`web/src/analytics.ts` (`trackSectionViews()`), so #7 and #10 are unblocked for a future
batch.

## Acceptance

- [x] Backlog refreshed for live instrumentation: status per row (ready vs blocked).
- [x] Re-scored ICE (Confidence reflects metric-is-live).
- [x] New tests for the now-live surfaces (consult band, 7 comparison pages, aha auto-print).
- [x] Honest: thin-traffic method, telemetry-blocked tests flagged, no fabricated proof.
- [x] Named the next instrumentation (`section_viewed`) and the 3 tests to run first.
