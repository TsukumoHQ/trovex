---
name: anti-ai-slop
description: De-slop any copy before it ships — strips the tells that make text read as AI-generated and rewrites it in Trovex's plain, developer-honest voice. Use ALWAYS before committing or publishing any prose: landing/README copy, blog posts, social drafts, launch copy, FAQs, comparison pages, CTAs, email/CLI text. Every lead runs this as the last pass on anything a human will read.
metadata:
  version: 1.0.0
---

# anti-ai-slop — the last pass before copy ships (2026)

Run this on EVERY piece of human-facing text before you commit it. It is a gate, not a
suggestion. If copy fails the checklist, rewrite and re-run. The goal: a developer reads it
and cannot tell a model wrote it.

Authority: this enforces the `voice` project memory and `.agents/product-marketing-context.md`.
When they conflict with anything here, they win.

## Step 1 — kill the banned words (hard fail)

These mark text as AI slop on sight. Zero tolerance — `grep` for them and remove every one:

- **Hype verbs**: supercharge, unlock, unleash, elevate, empower, revolutionize, transform,
  harness, leverage (as a verb), turbocharge, streamline, amplify.
- **Hollow adjectives**: seamless, robust, powerful, cutting-edge, state-of-the-art,
  game-changing, revolutionary, innovative, next-level, world-class, comprehensive, holistic,
  bespoke, frictionless.
- **Filler nouns/phrases**: "in today's fast-paced world", "in the world of", "the realm of",
  "when it comes to", "at the end of the day", "a testament to", "plays a crucial/vital/pivotal
  role", "the power of", "AI-powered", "harness the power", "navigate the landscape",
  "ever-evolving", "treasure trove", "tapestry", "delve", "dive deep", "embark", "journey".
- **Hedge/transition slop**: "it's worth noting that", "it's important to note", "that being
  said", "moreover", "furthermore", "additionally" (as a sentence-starter crutch), "in essence",
  "ultimately", "notably".

## Step 2 — kill the structural tells

- **The "It's not just X, it's Y" frame** — and its cousins ("More than a tool — a partner",
  "X isn't about Y. It's about Z."). Delete on sight.
- **Rule of three everywhere** — "fast, simple, and reliable", "build, ship, and scale".
  One or two concrete items beats three vague ones.
- **Em-dash overuse** — the AI tell of 2025–2026. Max one em-dash per paragraph; prefer a
  period or a comma. (This applies to prose; code/tables exempt.)
- **Empty conclusions** — "In conclusion", "Overall", a closing paragraph that restates the
  intro. Cut it; end on the last real point.
- **Title Case Headings For No Reason** and emoji-bulleted feature lists. Sentence case,
  plain bullets.
- **Symmetrical paragraph soup** — every paragraph the same length, every section the same
  shape. Vary it; let some sentences be short. Like this.
- **Vague quantifiers** — "many", "numerous", "a wide range of", "various", "countless".
  Replace with a real number or cut.

## Step 3 — rewrite to Trovex voice

- **Plain, confident, developer-honest, cost-framed. No hype.** Lowercase wordmark `trovex`.
- **Write from the user's side**: "your agents", "your docs", "your token bill" — not how it's
  built internally.
- **Specific beats clever.** Name the thing. Use the real number (~60% fewer tokens per
  lookup; the savings receipt). One concrete example outweighs a paragraph of adjectives.
- **Words to USE**: canonical, source of truth, tokens, reread, stale, current, local, runs on
  your machine, one answer, freshness.
- **Show the mechanism, not the magic.** Devs trust "returns one `path:line` pointer with a
  freshness marker", not "intelligently surfaces the right context".
- **Cut every sentence that survives deletion.** If removing it loses nothing, it was slop.

## Step 4 — the honesty gate (hard fail)

- **No fabricated proof.** Trovex is pre-launch, zero customers. No invented testimonials,
  logos, user counts, star counts, "trusted by", or made-up benchmarks. Only the real ~60% /
  savings numbers, clearly framed as what they are.
- **No overclaiming.** Don't promise outcomes the product can't guarantee. Hedge honestly with
  a real number, not with weasel words.
- **OSS surfaces are not sales pages.** README/landing stay useful-first; the consulting path
  is low-key.

## Anti-patterns (what this skill refuses to pass)

- Copy that's grammatically perfect and says nothing.
- "De-slopped" text that just swapped one banned word for another synonym (powerful→robust).
- Keeping the AI rhythm (uniform sentences, triadic lists, em-dash addiction) while changing
  vocabulary. Rhythm is the tell — fix it.
- Adding fake specificity (invented stats) to sound concrete. Specific must mean *true*.

## Done checklist

- [ ] `grep`-clean of every Step 1 banned word
- [ ] No "not just X, it's Y", no triadic filler, ≤1 em-dash/paragraph, no restating conclusion
- [ ] Sentence lengths vary; at least one short punchy sentence; no paragraph soup
- [ ] Every vague quantifier replaced with a real number or cut
- [ ] Voice matches `voice` memory; reads from the user's side; uses the real savings number
- [ ] Zero fabricated proof; no overclaim; OSS surface stays non-salesy
- [ ] Read it aloud once — if it sounds like a brochure or a model, rewrite
