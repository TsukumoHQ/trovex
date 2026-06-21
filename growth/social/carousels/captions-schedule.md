# Carousel captions + schedule plan (8 rendered, ready for Metricool)

> Carousels rendered by design (Supabase media, PR #278). This is the COPY + schedule plan
> to push them through Metricool. **Auto-lane** (anti-slop sole gate, cmo-approved 23:43) —
> but slot WITH content-lead's calendar (996c1929); don't double-book. A human/owner sees
> the Metricool queue before autoPublish flips.
>
> **Guardrails on every caption:** waitlist soft-launch (no "install now", no launch pre-empt);
> only first-party number ~60% (lives on the ETH card only); every study figure attributed +
> verbatim; @tsukumohq; founder = builder voice. Source-post link goes in the FIRST COMMENT
> (LinkedIn) / a REPLY (X), never the caption body.

## Media base
`https://bxdpevnqdnjcehewbiyg.supabase.co/storage/v1/object/public/media/<property>/carousel/<slug>/<variant>.png`
- property: `tsukumo` (company) or `trovex` (founder)
- variants ordered: `00-cover`, `01-slide` … `NN-slide`, last `NN-cta`; each in `portrait-*` (LinkedIn 1080×1350) and `square-*` (X 1080×1080). 4-slide carousels → 00-cover…05-cta.

## Brand / network routing
- **COMPANY** (brand 6430498, property `tsukumo`, /assessment CTA): X (square) + LinkedIn (portrait).
- **FOUNDER** (brand 6430128, property `trovex`, trovex.dev CTA): X (square) + LinkedIn (portrait) + Threads (portrait).
- Cadence: evidence track ~1 carousel/wk, strongest-data-first. Confirm exact dates with content-lead.

---

## COMPANY carousels (brand 6430498)

### 1. study-metr-slower → `tsukumo.ch/blog/does-ai-make-developers-faster`
**X:** 16 experienced devs, 246 real issues, their own repos. METR measured them about 19% slower with AI — while they felt ~20% faster. the gap between the vibe and the clock is the management problem. ↓
**LinkedIn:** METR ran the randomized trial most teams skip: 16 experienced devs across 246 real issues, on repos they knew. Result — about 19% slower with AI, while the same devs believed they were ~20% faster. Felt speed and measured speed disagreed. The slowdown is fixable: it's the operating model, not the model. Breakdown + source in comments.

### 2. study-gitclear-quality → `tsukumo.ch/blog/does-ai-hurt-code-quality`
**X:** GitClear counted 211M changed lines. as AI spread, copy-pasted code rose from 8.3% to 12.3% and overtook refactoring for the first time. the speed is real; so is the maintenance bill it defers. ↓
**LinkedIn:** GitClear measured 211 million changed lines. Copy-pasted code climbed 8.3%→12.3% while refactoring fell 24.1%→9.5% — in 2024 paste overtook refactor for the first time, and two-week churn rose 3.1%→5.7%. AI defers a maintenance bill onto your team. The method runs on your own repo. Source in comments.

### 3. study-dora-stability → `tsukumo.ch/blog/ai-adoption-delivery-stability`
**X:** Google's 2024 DORA: a 25% rise in AI adoption tracked with a 7.2% drop in delivery stability. the cause isn't bad AI code — it's bigger batches. ↓
**LinkedIn:** The largest study of software delivery we have, Google's 2024 DORA, found rising AI adoption tracked with lower stability: +25% adoption → ~−7.2% stability, ~−1.5% throughput. The cause isn't code quality, it's batch size — AI removes the friction that kept change sets small. The fix is delivery discipline. Source in comments.

### 4. study-stanford-codebase → `tsukumo.ch/blog/ai-productivity-clean-code`
**X:** Stanford, 100k+ devs: AI gave 35-40% on greenfield and single digits on the complex legacy code most teams actually live in. where you point it decides the result. ↓
**LinkedIn:** A Stanford study of 100,000+ developers across 600+ companies split the gains by where the work happens: 35-40% on clean greenfield, single digits (0-10%) on complex brownfield, with one case seeing 2.5× more rework. The lever isn't the model — it's the state of your codebase, which you can change. Source in comments.

### 5. study-apple-reasoning-cliff → `tsukumo.ch/blog/ai-reasoning-complexity-cliff`
**X:** Apple handed frontier reasoning models the exact algorithm. past a complexity threshold, accuracy still collapsed to near-zero. your hardest problems are the edge. ↓
**LinkedIn:** Apple's 2025 "Illusion of Thinking" tested reasoning models on puzzles of rising complexity. Past a threshold, accuracy fell to near-zero — even when the models were handed the exact algorithm. Three regimes: plain wins simple, reasoning wins medium, both collapse on hard. The practical line: above a complexity edge, agents need a human operator. Source in comments.

### 6. copilot-operator-gap → `tsukumo.ch/blog/the-copilot-operator-gap`
**X:** a copilot autocompletes in the editor — maybe 10% of what coding agents do. the gap to agents running work in production isn't a license. ↓
**LinkedIn:** A copilot finishes your line and answers about the open file. That's real, and it's roughly 10% of what agents can do. The other 90% — agents taking a task to production — is an operating problem, not a seat count. Context, orchestration, observability, review gates, team habits. Source in comments.

### 7. five-levers → `tsukumo.ch/blog/how-to-make-ai-work-for-your-dev-team`
**X:** the research is clear AI underdelivers by default. 5 operating levers separate teams that get gains from teams that get rework. none of them is a bigger model. ↓
**LinkedIn:** The studies agree AI underdelivers by default — and agree on why. Five operating levers separate gains from rework: point AI at the right work, keep batches small, measure outcomes not output, serve the agent trusted context, invest in codebase cleanliness. None of them is a model choice. Source in comments.

---

## FOUNDER carousel (brand 6430128, builder voice)

### 8. study-eth-context → `tsukumo.ch/blog/do-agents-md-context-files-help-coding-agents`
**X:** a 2026 ETH Zurich study benchmarked AGENTS.md-style context files. they cut agent success ~3% and raised cost over 20%. more context isn't better — the currently-correct doc is. ↓
**LinkedIn:** A 2026 ETH Zurich study put the "write a better AGENTS.md" instinct on a benchmark, and it lost: repo context files cut agent success ~3% on average and raised cost over 20%. A long auto-generated file dilutes attention. The answer isn't no context — it's the currently-correct doc, per query. That's the problem trovex works on; on a doc-heavy repo it's about 60% fewer tokens per lookup. Source in comments.
**Threads:** more context isn't better. a 2026 ETH Zurich study found AGENTS.md-style files cut agent success ~3% and raised cost over 20%. the fix is the currently-correct doc per query, not a longer file. (that's what trovex does — ~60% fewer tokens on a doc-heavy repo.) ↓

---

## Link placement (all)
- **X:** caption ends with "↓" (swipe cue). Source-post link in a REPLY to the post.
- **LinkedIn / Threads:** "Source in comments" → drop the blog link as the first comment.
- The card's own CTA (assessment / trovex.dev) carries the action; don't duplicate it in the caption.

## Self-audit
- [x] Every study figure attributed + verbatim from the live post; sole first-party number ~60% (ETH card only).
- [x] No "install now"; waitlist soft-launch; no launch pre-empt. @tsukumohq, founder = builder voice.
- [x] anti-slop clean; one idea per post; X ≠ LinkedIn body.
- [ ] Dates: confirm with content-lead (calendar 996c1929) before Metricool autoPublish flip.
