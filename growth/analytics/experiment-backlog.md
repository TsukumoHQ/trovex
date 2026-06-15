# Trovex — Experiment Backlog (ICE-scored)

*Owner: analytics-lead · Status: v1 · Last updated: 2026-06-15*

Prioritized A/B / optimization experiments, pulled from the other leads' actual work.
Every test is one hypothesis + one success metric + an ICE score. **No test runs before
its metric is instrumented and live** (tracking-plan.md). Candidates come from cro-lead
(landing CRO, aha auto-print, consult CTA, referral), geo-lead (comparison pages),
launch-lead (registry listings) and content-lead (hero copy).

---

## Reading the scores

**ICE** = Impact × Confidence × Ease, each 1–10, score = mean (1 decimal).
- **Impact** — effect on the north star (qualified reach → consulting leads), not vanity.
- **Confidence** — that it works **and that we can detect it.** Pre-launch traffic is
  thin, so "we can measure it" caps confidence honestly — a rare-event test (leads) or one
  needing opt-in telemetry (retention) scores lower here even if the idea is strong.
- **Ease** — build + run cost.

## Traffic reality (read before running anything)

trovex.dev is pre-launch and low-traffic. **Do not run concurrent 50/50 splits** — there
isn't enough traffic to power parallel arms. Default method:

- **Sequential / before-after** with a `variant` custom property on events, judged on
  **directional + qualitative** signal, not p<0.05, until traffic supports it.
- **One live test per surface** at a time (no overlapping changes on the hero).
- **One success metric per test**, declared before it starts. No peeking-to-stop.
- Painted-door is fair for demand tests (e.g. consult CTA) as long as the click is logged
  honestly and the door isn't a dead end for the user.

## Backlog (ranked)

| # | Hypothesis | Variant(s) | Success metric (one) | Source | ICE | Prereq |
|---|-----------|-----------|----------------------|--------|-----|--------|
| 1 | First `trovex search` printing the savings number raises repeat usage | aha line on vs off | `repeat` (2nd query-day) rate | cro-lead PR #11 | **7.3** | opt-in telemetry live |
| 2 | One primary CTA above the fold beats two | 1 CTA vs CTA+"See it work" | `cta_clicked` / `github_clicked` rate per `landing_view` | cro-lead `growth/cro-landing` | **7.0** | web tracking live |
| 3 | A low-key consult CTA lifts consulting-lead clicks without hurting OSS feel | consult CTA shown vs hidden | `consult_clicked` rate | cro-lead PR #18 | **7.0** | `consult_clicked` event + real CONSULT_URL (human) |
| 4 | Hero copy-command `index` (value step) gets copied more than `serve` | `index /path` vs `serve` | `command_copied` rate | cro-lead | **6.7** | web tracking live |
| 5 | "vs CLAUDE.md / repomix / context-hub" comparison pages convert AI-engine traffic better than home | comparison landing vs home for `ai_engine` sessions | `cta_clicked` rate within `channel=ai_engine` | geo-lead | **6.3** | tracking + UTM contract + pages built |
| 6 | A sharper H1/deck lifts engagement past the hero | current H1 vs content-lead variant | scroll-past-hero → `cta_clicked` | content-lead | **6.3** | web tracking + a `hero_scrolled` or section-view event |
| 7 | A shareable savings receipt seeds referral sessions | receipt share affordance on vs off | referred sessions (`utm_medium=referral`) | cro-lead (P2 referral) | **5.7** | tracking + receipt feature + UTM |
| 8 | MCP-registry listing copy variant lifts registry→site intent | listing copy A vs B | sessions `utm_source=mcp-registry` × `github_clicked` | launch-lead | **5.7** | UTM on listings + registry live |
| 9 | FAQ order/added objection reduces hero-only bounce | current vs reordered FAQ | `cta_clicked` after FAQ section view | cro/content | **5.3** | web tracking + section-view event |
| 10 | A social-proof element lifts CTA | stars/quote shown vs not | `cta_clicked` rate | (deferred) | **4.7** | ⚠️ **no real testimonials — do NOT fabricate.** Stars only; low priority |

## Instrumentation this backlog needs (feeds back to the tracking plan)

These events aren't in the live plan yet — they gate the tests above:

- `consult_clicked` — `{ location }` — when the consulting CTA is clicked (#3). High value:
  it's the closest measurable signal to the north star.
- section-view event (e.g. `section_viewed` `{ section }`) — for scroll-depth / FAQ /
  hero-pass tests (#6, #9). One IntersectionObserver, fire-once per section.
- `share_clicked` — `{ surface }` — savings-receipt share affordance (#7).
- Retention (`repeat`) for #1 needs the **opt-in CLI telemetry** (activation-funnel.md §4).
  Until it exists, #1 is judged on the local single-user signal + qualitative only.

I'll add `consult_clicked` + `section_viewed` to the tracking plan as a fast follow (they
unblock the three highest-ICE web tests). `share_clicked` and telemetry wait on their
features.

## Run order (given the above)

1. **Now (once web tracking merges):** #2, #4 — pure copy/layout, instant to run, validate
   cro-lead's already-shipped landing changes.
2. **After `consult_clicked` + real CONSULT_URL:** #3 — closest proxy to leads.
3. **After comparison pages + UTM adoption:** #5 — highest strategic leverage (GEO).
4. **After opt-in telemetry:** #1 — the activation/retention hinge.
5. Backfill #6–#9 as their events/features land. #10 only if/when real proof exists.

## Acceptance

- [x] Prioritized backlog: each entry = hypothesis + single success metric + variants + ICE.
- [x] Candidates pulled from cro/geo/launch/content leads' real work, cited per row.
- [x] Honest about thin traffic (sequential not parallel; directional judging) and about
      tests blocked on telemetry / human input / unbuilt features.
- [x] Names the new events the tests need and commits to adding the two cheapest as a follow-up.
