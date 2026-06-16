# Partnership / co-marketing target list (no spam) (DRAFT)

**Status:** DRAFT / plan + outreach drafts. Nothing sent. A human reviews + sends each, personalized. Owner-gated.
**Owner:** launch-lead · **Reviewed against:** voice, no-synergix-mention, ecosystem, outreach.md, community-plan.md, north-star
**Repo:** github.com/Synergix-lab/trovex · **Landing:** trovex.dev

> This is **co-marketing** (mutual, value-first integration/content partnerships), distinct from `outreach.md` (1:1 newsletter/Discord notes) and `community-plan.md` (where-to-show-up calendar). The unit here is a *relationship*: we give before we ask, and the fit has to be honest both ways.

---

## 0. Principles (the no-spam contract)

- **Value-first, always.** Ship something useful to them *before* any ask — a working integration, a PR, a genuinely good "works with X" doc, a thoughtful mention. No cold "wanna cross-promote?" with nothing on the table.
- **Honest fit only.** If we can't say in one line why their users genuinely benefit, it's not a partner. Forced fits read as spam.
- **Complementary, not competing.** Partner with tools that sit *next to* trovex (clients, orchestration, observability, frameworks). Direct context-routing competitors get *positioned against*, not partnered with (see §5).
- **Asymmetric is fine.** A small tool helping a bigger one (a clean integration + docs) earns goodwill even if the return is delayed. Play the long game.
- **One relationship > ten blasts.** Same rule as outreach: a real collaborator beats a list.
- **Brand rules:** lowercase `trovex`; no "Synergix" in prose; real ~60% only; consulting angle stays off the OSS collab surface.

---

## 1. The suite (internal — the first and easiest cross-promo)

Before any external partner: the three suite tools reinforce each other. This is owned cross-promo, no permission needed (suite-positioning.md, ecosystem).

| Tool | Fit with trovex | Co-marketing move |
|---|---|---|
| **WRAI.TH** (multi-agent orchestration over MCP) | trovex is the context/SSOT layer the orchestrated agents read/write through. Honest pairing: orchestrate with wrai.th, keep them on one source of truth with trovex. | Cross-link in both READMEs + a "the suite" section; a joint "running an agent fleet" guide (wraith-kit.md, suite-positioning.md). |
| **yoru** (agent observability) | "know what your agent did last night" pairs with trovex's savings receipts. | Mention only once yoru is public (suite-positioning rule); until then no claims. |

> The suite story is the backbone every external partnership cross-references — trovex is the context layer that pairs with the rest, never framed as a rival.

---

## 2. MCP clients / agent IDEs (consume MCP servers — highest mutual value)

> A "trovex works with <client>" doc + a verified config is value for *their* users and discovery for us. Most have community "awesome"/showcase surfaces.

| Client | URL / handle | Fit | Mutual-value first move |
|---|---|---|---|
| **Cline** | cline.bot · github.com/cline | VS Code agent with a curated one-click **MCP Marketplace** that accepts submissions — the clearest open lane of any IDE. Users feel token cost directly. | Submit a polished trovex entry to the Cline MCP Marketplace + a "trovex + Cline" quickstart; then offer to docs/Discord. **(#1 — top move)** |
| **Goose (Block)** | goose-docs.ai · github.com/block/goose | OSS on-machine agent (39k+ stars, 70+ extensions, now under Linux Foundation AAIF). Local-first agent + local-first context = honest philosophy match. Active Discord curates community extensions. | Build/test a trovex Goose extension; PR or "community extension" doc; share in their extension channel. |
| **Continue.dev** | continue.dev · github.com/continuedev | OSS context provider for VS Code/JetBrains, has a **Hub** of blocks + MCP servers. trovex as a canonical-doc block is additive, not competing with their autocomplete. | Publish a trovex block to the Continue Hub + "use trovex as your context block" guide. |
| **Roo Code** | roocode.com · github.com/RooCodeInc | Cline fork, MCP support **but no marketplace** (manual config). Gap = users hand-wire servers. | Write the missing "add trovex to Roo Code" doc + a custom-mode recipe; offer to docs/Discord. |
| **Zed** | zed.dev · github.com/zed-industries/zed | Fast Rust editor, agent panel + MCP "context servers." Audience = perf-minded devs who value local-first/ONNX. | Contribute a trovex context-server example to Zed docs/community. |
| **Cursor / Windsurf / Claude Code** | cursor.com · windsurf.com · Claude Code | Major MCP consumers but closed/vendor-driven — no community submission lane. | "works with X" install docs only; no outreach needed. |

**Value-first first move (per client):**
- [ ] Write + verify a working `trovex` MCP config for that client (test it actually connects). This is the gift.
- [ ] Add a short "Use with <client>" section to trovex's README/docs.
- [ ] Where they have a community integrations list / awesome repo → a clean PR adding trovex (per their format).
- [ ] Only then, if warranted, a friendly heads-up to their community/maintainers — not a pitch.

---

## 3. Complementary tools / frameworks (non-competing — "use alongside")

> Agent frameworks + memory/knowledge tools where a "trovex alongside X" story is honest (they orchestrate/build; trovex routes the docs).

| Tool | URL / handle | Fit | Mutual-value first move |
|---|---|---|---|
| **Mastra** | mastra.ai · github.com/mastra-ai/mastra | TS-first agent framework, first-class MCP, active community. Agents load trovex as an MCP tool to cut tokens on codebase tasks. Strongest TS-ecosystem fit + natural WRAI.TH bridge. | Build a Mastra + trovex example agent; submit to their examples/showcase. **(top move)** |
| **Mem0 / OpenMemory** | mem0.ai · github.com/mem0ai | Local-first **memory** MCP (preferences across sessions). Memory ≠ code context. "trovex (what the code is now) + OpenMemory (what you prefer)" — honest combo, both local-first. | Joint "memory + canonical context" recipe; cross-link in docs. |
| **Basic Memory** | github.com/basicmachines-co/basic-memory | Human-readable markdown knowledge MCP. Notes layer pairs with trovex's code-truth layer. | Co-author a "two layers of agent context" post. |
| **LangGraph** | langchain-ai.github.io/langgraph | Graph/durable agent framework, large community, MCP adapters. Code-agent graphs that read repos benefit from trovex's savings. | Contribute a "code agent with trovex context" template. |
| **CrewAI** | crewai.com · github.com/crewAIInc/crewAI | Role-based multi-agent framework, MCP support. Multi-agent code crews rereading repos = exactly trovex's cost problem; bridges to the WRAI.TH story. | Example crew sharing one trovex doc across agents. |

> Lead the framework collabs with **WRAI.TH (orchestration) + trovex (context)** together — the suite is genuinely complementary to LangGraph/CrewAI/Mastra users, not competitive.

**Value-first first move:**
- [ ] A genuine "trovex + <tool>" usage doc or small example repo showing the honest combo.
- [ ] Engage in their issues/discussions as a real user first; mention trovex only on direct fit.

---

## 4. Newsletters / podcasts / creators / communities (genuine collab, not paid)

> Collab = a good guest writeup, a demo, a thoughtful contribution — not buying placement. Pairs with `outreach.md` (the 1:1 notes) and `community-plan.md` (cadence).

| Venue | URL / handle | Fit | Value-first first move |
|---|---|---|---|
| **PulseMCP → "The Agentic Loop"** | pulsemcp.com/newsletter (Tadas & Mike, MCP Steering Committee) | De-facto MCP newsletter + directory; features concrete, documented servers with a real story. "~60% fewer tokens, local-first" is exactly their angle; steering-committee reach. | Hand them a reproducible token-savings benchmark write-up to feature. **(top move)** Claim the directory listing first. |
| **Latent Space** (swyx & team) | latent.space | Top AI-engineer newsletter/podcast; "context engineering" is a recurring theme. | Publish a rigorous, data-backed "context engineering for coding agents" piece; offer as editorial value, no pitch. Highest-reach credibility play. |
| **CodeGen News** | codegen.substack.com | Tool-roundup newsletter on AI-code tooling. | Submit trovex + the benchmark for a tools section. |
| **Coding-agent YouTubers/streamers** | YouTube (reviewers covering Cline/Roo/Goose) | Demo-driven; trovex's before/after token count is visual. | Offer a ready-to-record demo repo + savings receipt; let them try on stream. |

**Communities where collabs form organically** (pairs with community-plan.md): MCP Discord (request `mcp-server-authors` flair → author channels), r/mcp, Goose Discord, Mastra/LangChain/CrewAI Discords, r/LocalLLaMA + Lobsters + HN (lead with the local-first/ONNX angle). First move everywhere: be useful first, share working examples + benchmarks, never drop a bare link.

> Ecosystem hubs (awesome-mcp-servers PR, official MCP Registry, Glama/mcp.so/PulseMCP directory claims) are covered operationally in **mcp-registries.md** — do them there, not as separate "outreach."

**Value-first first move:**
- [ ] Be a useful presence first (answer questions, contribute) before proposing anything.
- [ ] Offer *them* something: a tight writeup on the token-cost problem, real data they can use, a demo — not "please feature me."
- [ ] One personalized note per venue (outreach.md §B), never a batch.

---

## 5. Position against, not partner with (avoid the awkward ask)

Direct context-routing competitors — frame trovex's difference honestly, don't pitch them as partners (competitive-analysis, geo-lead comparison pages):

| Competitor | URL | Why it's a competitor, not a partner |
|---|---|---|
| **Repomix** | repomix.com · github.com/yamadashy/repomix | Packs the whole repo into an AI-friendly file (+ token counts, MCP server). Overlaps on "feed code efficiently." Comparison page: canonical-doc + freshness vs full-repo pack. |
| **LeanCTX** | github.com/yvgude/lean-ctx | Local Rust binary, MCP tools, markets "60–90% fewer tokens" + local-first — the closest positioning twin. A "vs LeanCTX" comparison page is warranted. |
| **CTX / context-hub generator** | github.com/context-hub/generator | "Context as Code" + MCP server for codebase context. Direct category competitor. |
| **andrewyng/context-hub** | github.com/andrewyng/context-hub | Same category, high-profile name. Position against; monitor. |

> These belong in comparison/alternative pages (geo-lead), not the partner list. Be fair, never trash them.

---

## 6. Top mutual-value first moves (do these first)

The pattern across all six: **ship the listing / working example / benchmark first — ask second.**

1. **Cline MCP Marketplace** — submit a polished trovex entry + "trovex + Cline" quickstart. Clearest open lane → real installs.
2. **PulseMCP / The Agentic Loop** — hand them a reproducible token-savings benchmark to feature; steering-committee reach, perfect editorial fit. (Claim the directory listing first.)
3. **Goose extension (Block / AAIF)** — build + PR a community extension; local-first philosophy match, active Discord, Linux Foundation credibility.
4. **Mastra example agent** — ship a working Mastra + trovex example to their showcase; strongest TS-framework community, natural WRAI.TH bridge.
5. **Mem0 / OpenMemory joint recipe** — "memory + canonical code context, both local-first" co-content; honest, non-competing, two-way audience.
6. **Latent Space context-engineering piece** — rigorous data on cutting coding-agent token cost, offered as editorial value. Highest-reach credibility play.

---

## 7. Outreach micro-drafts (use only after the value-first move landed)

**A. Maintainer note — after we shipped an integration/PR (1:1):**
```
Hi [name] — I use [their tool] with my coding agents and added a working trovex MCP config + a short
"use with [tool]" doc ([link]). trovex routes an agent to the one canonical .md (path:line + freshness)
instead of rereading the repo — ~60% fewer tokens on doc-heavy repos. Opened a PR adding it to your
[integrations list] in your format; happy to adjust. No ask — just thought your users running agents
might find it useful.
```

**B. Joint-content feeler — to a creator/newsletter we've already engaged with (1:1):**
```
Hi [name] — really liked [specific thing they made]. I've got real before/after data on what coding
agents waste rereading docs (and a local tool that measures it). If a writeup or demo on the token-cost
angle would be useful for your audience, happy to put it together — your call on format. No worries if not.
```

> Both: founder voice ("I"), one em-dash max, no company name, no hype, real ~60% only. Never send before the gift landed.

---

## 8. Guardrails + handoff

- **Drafts only** — a human reviews + sends each, personalized. No automated sending, no batch.
- Never: fake a personal connection, send identical copy to multiple partners, ask for cross-promo with nothing given, frame a competitor as a partner, or surface the consulting pitch on an OSS collab.
- No "Synergix" in any note/profile; no fabricated proof; ~60% is repo-dependent + verify.
- Track each relationship (partner, what we gave, date, response, next step) in a simple sheet for cmo.
- **Handoff:** launch-lead can ship the value-first *gifts* (integration configs, docs, clean PRs) as normal low-risk work; the *outreach sends* wait for owner/cmo review (need real account/identity).

*All copy above is a draft. Nothing has been sent.*
