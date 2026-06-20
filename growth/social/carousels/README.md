# trovex/tsukumo — carousel specs (batch 1)

> **DRAFT specs. Nothing rendered, nothing posted.** design-lead runs the generator
> from these JSON files; a human fires each carousel per the calendar. cmo gates this
> batch before anything arms.

Repurposes content already published + anti-slop-PASSED on `tsukumo.ch/blog` into the
carousel format (design generator `growth/assets/_tools/gen_carousel.mjs`).
Low slop risk (no net-new claims), high leverage (the study data travels).

## How design renders these
Each `.json` here is a complete, generator-ready spec (slug · audience · kicker · cover ·
slides · cta). Per file:

```
node growth/assets/_tools/gen_carousel.mjs growth/social/carousels/<file>.json
```

→ portrait (LinkedIn 1080×1350) + square (X 1080×1080) PNGs per slide, uploaded to Supabase
media (`kind:carousel`, `slug:<slug>`). Audience drives the default CTA, but every spec sets
`cta` explicitly so there's no ambiguity.

## Audience / CTA rule (P0 — do not break)
- **FOUNDER account (6430128)** → BUILDER CTA only (`trovex.dev`). NEVER consulting
  (Synergix conflict, record 0b61b80f).
- **COMPANY account (6430498) / tsukumo.ch** → assessment CTA (`tsukumo.ch/assessment`).

## Batch 1 — 6 carousels (study evidence + counter-pillar)

| Spec file | Audience | CTA route | Source post (link in caption / first comment) |
|---|---|---|---|
| `study-metr-slower.json` | company | /assessment | `tsukumo.ch/blog/does-ai-make-developers-faster` |
| `study-dora-stability.json` | company | /assessment | `tsukumo.ch/blog/ai-adoption-delivery-stability` |
| `study-gitclear-quality.json` | company | /assessment | `tsukumo.ch/blog/does-ai-hurt-code-quality` |
| `study-stanford-codebase.json` | company | /assessment | `tsukumo.ch/blog/ai-productivity-clean-code` |
| `study-eth-context.json` | **founder** | trovex.dev | `tsukumo.ch/blog/do-agents-md-context-files-help-coding-agents` |
| `five-levers.json` | company | /assessment | `tsukumo.ch/blog/how-to-make-ai-work-for-your-dev-team` |

## Batch 2 — added to the stream

| Spec file | Audience | CTA route | Source post (link in caption / first comment) |
|---|---|---|---|
| `study-apple-reasoning-cliff.json` | company | /assessment | `tsukumo.ch/blog/ai-reasoning-complexity-cliff` |
| `copilot-operator-gap.json` | company | /assessment | `tsukumo.ch/blog/the-copilot-operator-gap` |

Apple ('Illusion of Thinking') completes the earned-evidence study set. copilot-operator-gap
is the positioning wedge (seats ≠ operating model), routing to /assessment.

**ETH Zurich runs on the founder account on purpose:** the AGENTS.md / context-file finding
is the cleanest builder bridge to trovex (serve the currently-correct doc), so it earns a
`trovex.dev` CTA without any consulting pitch.

## Already covered by the seeded generator (do NOT re-spec — would duplicate)
- **trovex token-cost ~60% explainer** → seeded `token-cost` (founder) in `gen_carousel.mjs`.
- **6 readiness dimensions** → seeded `six-gaps` (company) in `gen_carousel.mjs`.

If the calendar wants a *company-voice* token-cost or a *founder-voice* readiness variant,
that's a deliberate batch-2 spec, not a re-render of the seeds.

## Honesty / proof
- Only first-party number is trovex **~60% fewer tokens per lookup**.
- Every other number is an **attributed third-party study figure**, copied verbatim from the
  live, anti-slop-PASSED blog post (METR ~19% slower; DORA 25% adoption → −7.2% stability;
  GitClear 8.3%→12.3% paste, 24.1%→9.5% refactor, 3.1%→5.7% churn, 211M lines; Stanford
  100k+ devs, 35-40% greenfield / single-digit brownfield / one case 2.5× rework; ETH Zurich
  ~3% success drop, >20% cost rise). No fabricated metrics, logos, or testimonials.
- Source link goes in the post caption (X) / first comment (LinkedIn), never baked into the
  card. The card's foot is the single CTA URL.

## Calendar slotting (coordinate with content-lead, do NOT firehose)
These slot into content-lead's publication calendar (doc `996c1929`) as the EVIDENCE track,
~1 study carousel / week, spaced so the company account isn't all-research. Suggested order
(strongest data first): METR → GitClear → DORA → Stanford → ETH (founder) → five-levers.
Founder ETH carousel rides the founder cadence (builder voice), not the company grid.

## Gate
This is **batch 1 of carousel specs for cmo review** (per task `c3275e26`). On GO:
design renders, content-lead slots into the calendar, a human fires. Nothing arms until then.
