# tsukumo — CTO-intent GEO/AEO pages (build spec)

*Owner: geo-lead. For: cro + fullstack to build in `Synergix-lab/tsukumo` (Next.js).*
*Status: DRAFT spec. Honest copy, no fabricated proof. Real numbers flagged `[NEED: …]`.*

This is the GEO/AEO layer for the agency funnel: pages that answer the real questions a
CTO types into Google or asks ChatGPT, and route the qualified ones to the two doors —
**studio** (build my product) and **consulting** (my team struggles with AI).

## Voice + positioning (apply to every page)

- Brand: **tsukumo** (lowercase). No "Synergix" on any public surface (it's the legal
  entity / GitHub org only; never brand copy).
- Position: we turn a client's dev team into **agentic operators** — augment devs, don't
  replace them. Hero claim: *these people run AI **in production** and ship ~10x* — not
  demos, not POCs. Proof = **we build** (we ship our own agent fleets: WRAI.TH, trovex, yoru).
- Repel the anti-persona on purpose: politely turn away "AI is easy / Claude Code seats are
  enough / AI = cheaper." The gap between an AI **demo** and AI **in production** is the product.
- Tone: prod-grade, builder-credible, dev-respecting, anti-generic-AI-agency. Concrete &
  Acid design (brutalist, acid-lime `#c8ff00`). Loud but honest — **no AI-slop** (banned:
  revolutionary, seamless, supercharge, unlock, "AI-powered"; run the anti-ai-slop gate).
- **No fabricated proof.** Self-proof = the suite, named (we built and run **trovex / WRAI.TH
  / yoru** to ship our own work) — NOT the legal company name ("Synergix" never appears in
  public copy). Plus anonymized cases ("a quantitative fund", a real-estate client). Where a
  result number would go, leave `[NEED: real number from <case>]` for the owner — never invent.

## AEO rules (so AI engines cite us)

1. **Direct answer first**: each page opens with a 40–70-word answer block that stands alone
   (this is what gets quoted). Then the supporting depth.
2. **Question-shaped H1 + H2s** for the guide pages.
3. **Define the term early** ("agentic operators", "AI in production") — definitions get cited.
4. **Honest specifics** over adjectives. One credible mechanism beats three superlatives.
5. **JSON-LD** per page (see the schema spec, `growth/agency/geo/schema-spec.md`): FAQPage on
   every page with a visible FAQ; the service pages add `Service`; guide pages `Article`.
6. Each page ends with the **two-door CTA** (studio / consulting) + a calendar/contact link.

## Page set (query → page)

### Commercial pillars (cro/content own the bulk of copy; geo supplies the AEO scaffold)

| Query | URL | Type | One-line job |
|-------|-----|------|--------------|
| "AI dev studio", "AI product studio" | `/studio/` | Service | We build your product with agent fleets, shipping ~10x |
| "AI in production consulting", "AI consulting for dev teams" | `/consulting/` | Service | We make your dev team agentic operators, in your real env |

Both pillars: answer-first hero, what-it-is, how-we-work (respect your env/standards), proof
strip (real cases), who-it's-for + who-it's-NOT-for (anti-persona), FAQ, two-door CTA.

### Answer/guide cluster (geo owns — these are the AEO citation magnets)

Build under `/answers/` (or `/guides/`). Each = direct answer + depth + FAQ + CTA.

---

#### 1. `/answers/get-dev-team-using-ai-agents/`
**Query:** "how to get my dev team using AI agents", "how do I get my developers to use AI"
**Title:** How do I get my dev team actually using AI agents (not just autocomplete)?
**Meta:** Most teams stall at AI-as-autocomplete. Moving to agents in production is a
capability shift — env, standards, and devs' trust. Here's the path, and where a studio helps.
**Direct answer:** Start from your real environment, not a demo. Most teams have Claude Code
as a copilot and stop there; the jump is to agents that run real work in production against
your standards and review gates. That takes three things: a codebase and docs agents can
navigate, guardrails your seniors trust, and devs trained to operate fleets rather than fear
them. tsukumo does this transition with your team, in your repo — we augment your devs, we
don't replace them.
**Sections (H2):** Why teams stall at copilot · What "agents in production" actually requires
(env, guardrails, review) · How we transition your team (augment, not replace) · What changes
in 90 days `[NEED: real before/after from a case]`.
**FAQ:** Will this replace my developers? (No — it makes them operators.) · Do we have to
change our stack? (We work in your existing env/standards.) · Is Claude Code enough? (It's the
copilot floor; production agents need more.)
**CTA:** consulting (primary), studio (secondary).

#### 2. `/answers/agentic-coding-for-teams/`
**Query:** "agentic coding for teams", "what is agentic coding", "AI agents for software teams"
**Title:** What is agentic coding for teams — and what does it take to do it for real?
**Meta:** Agentic coding = AI agents doing real engineering work against your standards, not
suggesting snippets. Here's what it means for a team and what production-grade requires.
**Direct answer (define early):** Agentic coding is letting AI agents carry out real
engineering tasks end to end — read the repo, plan, edit, test, open PRs — against your
review gates, instead of just suggesting lines. For a team, doing it for real means shared
context (one source of truth for the agents), observability (knowing what the agent did), and
operators who supervise fleets. tsukumo builds that capability with your team.
**Sections:** Agentic coding vs autocomplete · The three production gaps: context,
observability, operators · Why "more seats" doesn't get you there · Doing it without breaking
your standards.
**FAQ:** Is agentic coding safe in production? · How is this different from Copilot/Cursor? ·
Do we need new tools? (We use a suite we built — WRAI.TH/trovex/yoru — and your stack.)
**CTA:** consulting + studio.

#### 3. `/answers/ship-faster-with-ai-agents/`
**Query:** "ship faster with AI agents", "AI to ship features faster", "10x with AI agents"
**Title:** Can AI agents actually make my team ship faster? (Honestly.)
**Meta:** Yes, but not from buying seats. The speed comes from running agent fleets in
production with the right context and guardrails. Here's where the ~10x is real and where it isn't.
**Direct answer (honest, repels hype):** Sometimes — and not the way most vendors sell it.
Buying AI seats gets you autocomplete, not throughput. The real speed comes from running agent
fleets against a codebase and docs they can navigate, with guardrails your seniors trust, so a
small team operates like a larger one. It's prod-grade output and ~10x on the right work — not
a magic multiplier on everything, and not cheaper headcount. tsukumo sets this up in your env.
**Sections:** Where the speed actually comes from · Where AI does NOT speed you up (be honest)
· What ~10x means (and doesn't) `[NEED: real throughput number from a case]` · The setup that
makes it real.
**FAQ:** Is this just hype? · Does it mean fewer developers? (No — same devs, more output.) ·
How fast do we see it?
**CTA:** studio + consulting.

#### 4. `/answers/ai-in-production-vs-demos/`
**Query:** "AI in production", "why do AI demos fail in production", "production-grade AI dev"
**Title:** Why AI works in demos but breaks in production — and how to cross that gap
**Meta:** The demo-to-production gap is where most AI initiatives die: real codebases,
standards, scared devs, and no observability. Here's what crossing it takes.
**Direct answer:** Demos run on a clean slate; your production has a real codebase, real
standards, and real people. AI breaks at that boundary because it lacks durable context, there's
no visibility into what it did, and the team doesn't trust it. Crossing the gap means giving
agents a source of truth, instrumenting what they do, and training operators to supervise them.
That gap is exactly what tsukumo crosses — we live in production, on our own products.
**Sections:** The four reasons demos don't survive production · Context, observability,
trust · Why we're credible here (we run our own fleets) · The crossing, step by step.
**FAQ:** What makes you different from an AI agency? (We build; we run AI in prod ourselves.) ·
Will you respect our existing environment? · What if our devs are skeptical?
**CTA:** consulting + studio.

## Internal linking (silo)

- Studio ↔ Consulting cross-link in the nav + footer (the two doors, every page).
- Each guide page links to the relevant pillar (`/studio/` or `/consulting/`) and 1–2 sibling
  guides.
- The pillars link down to the guides as "common questions".
- Home links to both pillars + the guide hub (`/answers/`).
- Suite proof: where natural, link to the OSS products (trovex.dev, the WRAI.TH repo, yoru.sh)
  as proof-of-build — but the agency CTA stays the conversion, not the OSS.

## What geo delivers next (paired task)

- `growth/agency/geo/schema-spec.md` — JSON-LD (Organization + ProfessionalService + Service +
  FAQPage), llms.txt / llms-full.txt, sitemap, per-page meta (task `fa22881f`).

## Open items for cro/content/owner

- Real result numbers per case (CIL traffic/leads, quant-fund/throughput, our own ship metrics)
  — every `[NEED: …]` above. Until supplied, ship the pages with the qualitative claim only;
  do not invent numbers.
- Final URL scheme (`/answers/` vs `/guides/`) — geo recommends `/answers/` for AEO clarity.
- Confirm which cases are nameable (CIL) vs anonymized (quant fund). Self-proof is the **suite**
  (trovex / WRAI.TH / yoru), named as what we built — the legal company name stays out of public copy.
