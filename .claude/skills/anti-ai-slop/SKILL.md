---
name: anti-ai-slop
description: De-slop any copy before it ships — strips the statistical and lexical tells that make text read as AI-generated and rewrites it in Trovex's plain, developer-honest voice. Use ALWAYS as the last pass before committing or publishing any prose: landing/README copy, blog posts, social drafts, launch copy, FAQs, comparison pages, CTAs, email/CLI text. Every lead runs this on anything a human will read.
metadata:
  version: 2.0.0
  research_date: 2026-06-15
---

# anti-ai-slop — the last pass before copy ships

Run this on EVERY piece of human-facing text before you commit it. It is a gate, not a
suggestion. Fail → rewrite → re-run. Goal: a developer reads it and cannot tell a model wrote it.

Authority: enforces the `voice` project memory and `.agents/product-marketing-context.md`.
They win on any conflict.

**The single most important idea (2026):** detectors and sharp readers no longer key on
vocabulary alone — they key on *burstiness* and *restraint*. AI prose has uniform sentence
length, even rhythm, and relentless polish. Human prose is bursty: short. Then a longer,
winding one. A fragment. The rhythm is the tell. Fix rhythm first, words second.

## Step 1 — kill the overused words (grep, hard fail)

These spiked in usage after 2022 and now mark text as AI. Note: the set *drifts* — once a word
gets called out, models lean on the next one. Treat this as live, not fixed.

- **Faded but still radioactive** (called out ~2024, avoid anyway): delve, tapestry, intricate,
  meticulous, underscore, testament, boast/boasts, vibrant, nuanced, realm.
- **Current high-signal markers (2025–2026)**: showcase/showcasing, highlight/highlighting,
  enhance, leverage, foster/fostering, pivotal, crucial, robust, seamless, align with, resonate,
  landscape, ensure/ensuring, encompass, garner, bolster, commendable, elevate, streamline.
- **Hype verbs/adjectives**: supercharge, unlock, unleash, empower, revolutionize, transform,
  cutting-edge, state-of-the-art, game-changing, world-class, next-level, frictionless, holistic,
  bespoke, comprehensive.
- **AI-powered** specifically — banned in Trovex copy (per voice memory).

## Step 2 — kill the phrase templates & rhetorical tells

Verbatim AI scaffolds — delete on sight:

- "It's not just X, it's Y" / "not only… but also…" / "not X, but Y".
- "stands as / serves as a testament to", "marks a turning point", "represents a shift".
- "Despite its [strengths], [X] faces challenges…" and the "Challenges and Future Prospects"
  section formula with vague optimism.
- "highlights/underscores the importance of", "plays a pivotal/crucial role", "contributing to
  the broader…", "reflecting broader trends".
- **Rule of three everywhere**: "fast, simple, and reliable", "build, ship, and scale". One or
  two concrete items beat three vague ones.
- **Vague attribution**: "researchers say", "experts argue", "studies show", "some critics",
  "industry reports" — name the source or cut.
- **Avoiding plain "is/are"**: replacing the copula with "serves as / features / boasts /
  marks". Just say *is*.
- **Empty "-ing" tails**: "…, ensuring a better experience", "…, highlighting its value" tacked
  onto sentences without substance.
- **Empty conclusion**: "In conclusion / Overall / Ultimately" that restates the intro. End on
  the last real point.

## Step 3 — kill the formatting tells

- **Em-dash overuse** — the loudest 2026 tell. Max one per paragraph; prefer a period or comma.
  (Prose only; code/tables exempt.)
- **Boldface sprinkled for emphasis** on random phrases. Bold sparingly or not at all.
- **Title Case Headings**. Use sentence case.
- **Inline-header bullet lists** ("**Thing:** description") repeated for everything. Use prose
  or plain bullets where a list isn't earned.
- **Curly quotes/apostrophes** auto-inserted — use straight quotes in code-adjacent copy.
- Emoji-bulleted feature lists.

## Step 4 — rewrite to Trovex voice

- **Plain, confident, developer-honest, cost-framed. No hype.** Lowercase `trovex`.
- **Burstiness**: vary sentence length on purpose. Include at least one short, blunt sentence.
- **Write from the user's side**: "your agents", "your docs", "your token bill" — not internals.
- **Specific beats clever.** Real number over adjective (~60% fewer tokens per lookup; the
  savings receipt). One concrete example outweighs a paragraph of praise.
- **Words to USE**: canonical, source of truth, tokens, reread, stale, current, local, runs on
  your machine, one answer, freshness.
- **Show the mechanism, not the magic**: "returns one `path:line` pointer with a freshness
  marker" beats "intelligently surfaces the right context".
- **Don't elegant-variation**: repeating "doc" is fine; swapping in "document / file / artifact
  / resource" to avoid repetition is itself a tell. Repeat the plain word.
- **Cut every sentence that survives deletion.**

## Step 5 — the honesty gate (hard fail)

- **No fabricated proof.** Pre-launch, zero customers. No invented testimonials, logos, user/star
  counts, "trusted by", or made-up benchmarks. Only the real ~60% / savings numbers, framed as
  what they are.
- **No overclaiming.** Don't promise outcomes the product can't guarantee.
- **OSS surfaces are not sales pages.** README/landing stay useful-first; consulting stays low-key.

## Anti-patterns (won't pass)

- Grammatically perfect, says nothing.
- Swapped one banned word for a synonym (powerful→robust) and called it done.
- Fixed vocabulary but kept the AI rhythm (uniform sentences, triadic lists, em-dash addiction).
  Rhythm is the tell.
- Added fake specificity (invented stats) to sound concrete. Specific must be *true*.

## Done checklist

- [ ] Read aloud — rhythm is bursty, not a uniform drone; ≥1 short blunt sentence
- [ ] grep-clean of Step 1 words; no Step 2 phrase templates; ≤1 em-dash/paragraph
- [ ] No title-case headings, no bold-sprinkle, no inline-header list overuse
- [ ] Every vague quantifier/attribution replaced with a real number/source or cut
- [ ] Voice matches `voice` memory; from the user's side; plain words repeated, not varied
- [ ] Zero fabricated proof; no overclaim; OSS surface non-salesy

## Sources (2026-06-15)
Wikipedia "Signs of AI writing" (live tell catalogue); studies on post-2022 lexical
overrepresentation (delve/underscore/tapestry spikes + the post-callout drop); 2026 detector
guides on burstiness/restraint; de-slop editing guides on sentence-length variation and
removing canned transitions.
