# trovex content strategy

*Owner: content-lead (Discovery team) · last updated 2026-06-15 · status: living doc*

The job of content here is not traffic. It's **qualified reach that surfaces consulting
leads**: awareness → discovery (incl. AI-engine citations) → activation (install → a
visible savings number) → retention → referral → a team lead who reaches out. Every piece
below maps to a stage in that chain. If a piece doesn't move discovery, activation, or the
consulting path, we don't write it.

Pre-launch, zero customers. The only proof number is the real **~60% fewer tokens per doc
lookup**. No fabricated logos, quotes, counts, or benchmarks, ever.

## Positioning the content defends

trovex owns one category sentence: **context infrastructure for coding agents**: the
canonical doc store that serves an agent the one current doc per query instead of letting
it reread the repo. The recurring proof is the savings receipt. Content exists to make that
sentence the answer a developer (or an AI engine) gives when asked "how do I stop my coding
agent rereading docs / burning tokens?"

## Pillars

Four pillars. Each is a cluster: one cornerstone post plus spin-off answer-pages and social.

1. **Token economics of agents**: what rereading docs actually costs, measured, with
   reproducible math. (Cornerstone live: [the token cost of agents rereading docs](../blog/the-token-cost-of-agents-rereading-docs.md).)
   *Funnel stage: discovery + activation.*
2. **SSOT & multi-agent coordination**: one shared write path so agents and teammates stop
   re-deriving the same thing; docs that don't drift. *Stage: discovery + retention (the
   team angle that leads to consulting).*
3. **Local-first agent infrastructure**: runs on your machine, SQLite + ONNX, no cloud or
   keys; why local matters for cost, privacy, and latency. *Stage: discovery + activation
   (lowers the "another service to run" anxiety).*
4. **MCP ecosystem how-tos**: wiring trovex into Claude Code / Cursor / Windsurf / Zed,
   comparison pages, registry presence. *Stage: discovery (high-intent) + activation.*

## What we publish, in priority order

Ranked by impact on the funnel, not by effort.

1. **The cornerstone post** (one per pillar, ~1 every 2 weeks). Measured, specific,
   answer-up-front, GEO-structured. This is the asset everything else repurposes from.
2. **Comparison / alternative pages**: "trovex vs CLAUDE.md", "trovex vs repomix",
   "trovex vs a plain context server". High buyer-intent and heavily AI-cited. One page per
   real alternative, honest about when the alternative is the right call.
3. **AEO answer-pages**: short, single-question pages spun from cornerstone sub-sections
   ("how much does it cost when my agent rereads docs?", "is a bigger context window
   cheaper?"). Built to be quoted by ChatGPT / Perplexity / Google AI Overviews.
4. **How-to / quickstart content**: install in under 5 minutes to the first savings
   number. This is the activation lever; treat it as content, not an afterthought.
5. **Build-in-public notes**: short, honest dev-log posts about what we measured and what
   broke. Cheap to produce, credible, good forum and social fuel.

## GEO/AEO craft (how we get cited by AI engines)

Apply to every public piece:

- **Answer up front.** A one-paragraph TL;DR that fully answers the title question before
  any preamble. Engines lift the answer, not the build-up.
- **Question-shaped headings** that match how devs actually ask.
- **Specific and falsifiable**: real numbers, named alternatives, a date. Engines prefer
  claims they can attribute.
- **Structured data**: `FAQPage` / `QAPage`, `HowTo`, `SoftwareApplication`, `TechArticle`,
  `BreadcrumbList` JSON-LD on the rendered pages. *(Handoff: geo-lead wires the schema when
  the /blog and comparison pages are built; content supplies the FAQ/Q&A blocks.)*
- **Own the entity**: define "context infrastructure for coding agents" consistently across
  README, landing, blog, and registry listings. Third-party surfaces (GitHub, MCP
  registries, forums) carry weight; keep the category sentence identical everywhere.

## The repurpose chain

One cornerstone post is the head of a chain. We don't write five things; we write one and
atomize it. Distribution is half the work — it's scheduled, not bolted on.

```
cornerstone post (content-lead)
  ├─→ X/Twitter thread        → the numbers + the receipt screenshot   (social-lead drafts)
  ├─→ LinkedIn narrative       → the same story, first-person, longer    (social-lead drafts)
  ├─→ forum seed               → HN Show / Lobsters / relevant subreddit, framed as
  │                              "I built X, here's what I measured" — never a promo (launch-lead)
  ├─→ 2–3 AEO answer-pages      → standalone pages from the post's sub-questions (content + geo)
  └─→ README / docs snippet     → keep the canonical sentence in sync     (content-lead)
```

Rules of the chain:
- Every spin-off **links back** to the cornerstone (internal-link silo).
- Social and forum drafts are **drafts only**: a human fires the live posts (autonomy
  rule). Link goes in a reply, not the first post, to protect reach.
- The **savings receipt is the creative**. Use the real number or your own real receipt;
  never invent one.

## Cadence

- **1 cornerstone every 2 weeks.** Quality and consistency beat volume for a solo founder.
- **Comparison/AEO pages fill the off-weeks**: cheaper, derived from the cornerstone.
- **Repurpose within 48h** of a cornerstone going live, while it's fresh.
- Re-run live competitive/keyword research (deep-research) when the web rate-limit clears;
  this plan was built on internal priors + the project memories and should be refreshed.

## Handoffs (who does what)

- **content-lead**: cornerstones, comparison pages, README/landing words, lead magnets, the
  FAQ/Q&A copy blocks, the editorial calendar.
- **geo-lead**: JSON-LD schema, programmatic page structure, internal-link silos, keyword
  targeting, registry SEO.
- **social-lead**: X / LinkedIn / forum drafts from the repurpose chain (drafts only).
- **launch-lead**: Show HN / Product Hunt / registry submissions (drafts only; human fires).
- **cro-lead**: landing structure, CTA treatment, above-fold proof, activation flow.
- **analytics-lead**: which AI engine / referrer sent the session, activation funnel,
  install→repeat, so we publish-then-measure rather than publish-blind.

## Definition of done for any content piece

- [ ] Maps to a funnel stage (discovery / activation / consulting path).
- [ ] Answer-up-front + question-shaped headings (GEO).
- [ ] Real ~60% only; zero fabricated proof.
- [ ] Voice spec respected; anti-ai-slop pass run as the last step.
- [ ] Repurpose chain queued (or explicitly skipped, with reason).
- [ ] Consulting path stays low-key and earned, never a pitch.
