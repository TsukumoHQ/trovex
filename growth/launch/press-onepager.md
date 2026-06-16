# Press / launch one-pager — tsukumo + the suite (DRAFT)

**Status:** DRAFT / press kit copy. Nothing sent to press. Owner-gated; fire only when sites are live + facts confirmed.
**Owner:** launch-lead · **Reviewed against:** suite-positioning.md, ecosystem, mission, agency-* memories, voice, no-synergix-mention, pricing-policy, north-star
**Use:** the single fact sheet a journalist/editor/newsletter can pull from. Copy is factual + non-promotional; press distrusts hype faster than HN does.

> Routing: the suite (wrai.th/trovex/yoru) facts live in this colony; the **tsukumo** (agency) facts are a draft for owner/tsukumo (own repo per repo-routing). This is one combined kit so a journalist sees the whole story; owner confirms the agency facts before any send.

---

## 1. The lead (the one-sentence story)

> A small team is shipping three open-source, local-first tools for running fleets of AI coding agents in production — orchestration, context, and observability — and uses them as the proof behind an AI-engineering consulting practice that turns dev teams into agentic operators.

---

## 2. Boilerplate (the standard "about" — press can quote/copy verbatim)

**The suite (≤60 words):**
> wrai.th, trovex, and yoru are three open-source, MCP-native, local-first tools for running AI coding agents at scale: wrai.th orchestrates an agent fleet (memory, messaging, tasks), trovex serves agents one canonical doc instead of a repo reread (~60% fewer tokens), and yoru shows what agents did. Each works alone; together they run agents without flying blind.

**The agency — tsukumo (≤60 words, owner to confirm):**
> tsukumo is a Switzerland-based AI-engineering studio and consulting practice (est. 2026). It helps startups and scale-up engineering teams run AI coding agents at production quality — augmenting developers, not replacing them — through agentic-dev training, process setup, and building agentic-first systems. The open-source suite is its proof of competence.

---

## 3. The problem (the news hook)

> Teams are adopting AI coding agents fast, but running them well is unsolved: agents burn tokens rereading the same repo every session, lose track of what's canonical, work without shared memory, and leave no trail of what they did. The cost compounds across every session, every agent, and every teammate. The honest fix isn't a bigger context window — it's discipline: one source of truth, coordination, and visibility.

---

## 4. The suite at a glance (one honest line each)

| Tool | Layer | One-liner | Status | License |
|---|---|---|---|---|
| **wrai.th** | orchestration | Mission control for an agent fleet: persistent memory, inter-agent messaging, shared tasks, one dashboard. | public, v1.0 stable | AGPL |
| **trovex** | context / SSOT | Serves each agent the one current doc (`path:line` + freshness) instead of a repo reread. ~60% fewer tokens. | private beta | AGPL core / MIT CLI |
| **yoru** | observability | Know what your agents did overnight: runs, decisions, outcomes. | early — **not yet public** | AGPL |

> Honesty rule for press: state each status plainly. Do **not** imply yoru is shippable or trovex is publicly GA. wrai.th is the one with a real public install today.

---

## 5. Key facts (fact sheet — owner confirms the [bracketed])

- **What it is:** open-source tooling for running AI coding-agent fleets + an AI-engineering consultancy.
- **Founded:** 2026 (tsukumo). · **Location:** Switzerland.
- **Suite repos:** wrai.th → github.com/Synergix-lab/WRAI.TH (public) · trovex → github.com/Synergix-lab/trovex (private beta) · yoru → not public yet.
- **Agency site:** tsukumo.ch.
- **Licensing:** AGPL on the cores (MIT on the trovex CLI) — deliberate: teams wanting to embed privately have a reason to talk; adoption stays frictionless.
- **Business model:** OSS suite = funnel; revenue = consulting for dev teams running agents at scale.
- **The number (real, repo-dependent):** ~60% fewer tokens per doc lookup with trovex on doc-heavy repos; ships a savings view so anyone can verify on their own repo. No other metrics claimed.
- **Customers/testimonials:** none published yet — **do not fabricate.** Agency engagements are real but described qualitatively until clients permission specifics.

---

## 6. Quote (founder — PLACEHOLDER; owner supplies real words)

> [Founder quote — owner to write. Keep it plain, problem-framed, no hype. Example shape, NOT for publication: "Running one agent is easy; running a fleet well is the hard part — most of the cost is wasted context and no shared memory. We built the tools we needed, and we help teams do the same."]

> ⚠️ Never invent a quote, a customer name, or a metric. Leave the placeholder until the owner fills it.

---

## 7. Contact + boilerplate footer

- **Press contact:** [owner name + email — owner to set]
- **Links:** tsukumo.ch · github.com/Synergix-lab/WRAI.TH · github.com/Synergix-lab/trovex
- **One-line footer:** "tsukumo — turning dev teams into agentic operators. Est. 2026, Switzerland."

---

## 8. Asset list (hand to design-lead / capture from running apps)

- [ ] **Logos** (vector + PNG): tsukumo Operator-Cursor mark (acid `#c8ff00` on ink); wrai.th, trovex, yoru wordmarks.
- [ ] **Suite diagram** — the layer stack (yoru / wrai.th / trovex) from suite-positioning.md, press-resolution.
- [ ] **OG/social cards** for each property (already partly built — confirm with design-lead).
- [ ] **Screenshots (real runs):** trovex `index` finishing + savings receipt + a `trovex(q)` result; wrai.th dashboard.
- [ ] **Short demo video/gif** (token before/after) — the most quotable asset.
- [ ] **Founder headshot + short bio** (owner provides).
- [ ] **Brand colors/fonts note:** trovex green `#22c55e`; tsukumo acid `#c8ff00`; lowercase wordmarks.
- [ ] Package as a downloadable press-kit folder (logos + diagram + screenshots + this one-pager as PDF).

---

## 9. Press guardrails (fact-check before any send)

- Every status accurate (wrai.th public, trovex private beta, yoru not public). No "launching soon" on yoru beyond "in development."
- Real ~60% only, framed as repo-dependent + verifiable. No invented metrics, users, logos, or quotes.
- **No public prices** for the agency (pricing-policy) — "inquire / book an assessment," never $ figures.
- Lowercase wordmarks; **no "Synergix" in prose** (GitHub-org/URL identifiers only).
- Consulting framed as the business, not pitched at devs; suite framed as honest tools, not hype.
- Run anti-ai-slop on the final copy.

---

## 10. Send gates + handoff

- [ ] **Gate:** tsukumo.ch live + agency facts confirmed by owner + founder quote/headshot supplied + asset kit assembled.
- [ ] Pair the press push with the coordinated launch window (launch-day-runbook) — press lands when there's somewhere to point it.
- **Handoff:** design-lead (assets), content-lead (align wording with READMEs/site), owner/cmo (fire the sends, supply the bracketed facts + quote). Earned-media outlets to pitch this to: earned-media-targets.md.

*This is a draft press kit. Nothing has been sent to any outlet.*
