# Product Marketing Context

*Last updated: 2026-06-15*

## Product Overview
**One-liner:** Trovex is the canonical doc store for your coding agents — one source of truth, ~60% fewer tokens.
**What it does:** Trovex indexes a repo's markdown, then serves AI agents the single current doc that answers a query (a `path:line` pointer with a freshness marker) instead of letting them reread the whole repo to guess which file is canonical. Agents also read only the relevant section, and write what they learn back through one shared point, so every agent and teammate sees the same source of truth.
**Product category:** Context / memory infrastructure for AI coding agents (MCP server + CLI).
**Product type:** Open-source developer tool (self-hosted, runs locally).
**Business model:** Open source as the top of a consulting funnel. The tools are free — core under **AGPL-3.0**, CLIs under **MIT** — and the business sells **consulting to dev teams** (helping them run AI coding agents well at scale). Trovex is one of several OSS tools the founder ships to feed this funnel. AGPL on the core is deliberate: teams that want to embed/host it privately without copyleft obligations have a concrete reason to reach out → consulting/commercial conversation. MIT on the CLI keeps adoption frictionless.

## Target Audience
**Target companies:** Solo developers and small eng teams (1–20) running AI coding agents on real, doc-heavy repos. MCP-ecosystem early adopters.
**Decision-makers:** The developer themselves (bottom-up adoption). No procurement — one person installs it.
**Primary use case:** Stop coding agents from burning tokens (and money) rereading the same `.md` files every session to figure out which is current.
**Jobs to be done:**
- "When my agent needs project knowledge, give it the one right answer cheaply, not six files to sift."
- "Keep my agents and my teammates working from the same, current docs instead of stale copies that drift."
- "Stop re-deriving what another agent already figured out."
**Use cases:**
- Multi-agent / multi-session work on a repo with many overlapping `.md` (runbooks, ADRs, READMEs, wikis).
- Small teams where two devs' agents should share one source of truth.
- Agents recording incidents/decisions/post-mortems other agents can read later.

## Personas
| Persona | Cares about | Challenge | Value we promise |
|---------|-------------|-----------|------------------|
| The agent-heavy IC dev | shipping fast, token/$ cost, not babysitting context | agents reread the repo, blow context, surface stale docs | one canonical answer per query, ~60% fewer tokens |
| Small-team tech lead | shared truth across the team's agents | each dev's agent re-derives the same things; docs drift | a single point of passage = SSOT, no sync |
| MCP tinkerer | trying useful MCP servers, local-first | wants signal vs. the 20k MCP servers | a tool that pays for itself with a visible savings number |
| Consulting buyer (team lead / eng manager) | their team's agents are wasteful & inconsistent at scale | rolling agents out well across a team is hard | hands-on help (the founder's consulting); Trovex is the proof of competence and the way in |

## Problems & Pain Points
**Core problem:** Coding agents spend thousands of tokens reading `.md` files just to guess which one is canonical — every session, every agent, repeatedly.
**Why alternatives fall short:**
- `CLAUDE.md` / `AGENTS.md` / `.cursorrules`: a single static blob; goes stale, doesn't scale to a big corpus, no per-query routing, no freshness signal.
- Dumping the repo (repomix / files-to-prompt): floods the context window with everything, the opposite of token-efficient.
- Plain RAG/context servers: return a pile of candidate chunks to sift, not the one canonical doc with a freshness marker.
**What it costs them:** Money (tokens), polluted context windows (worse answers), and wasted work re-deriving what another agent already found.
**Emotional tension:** Distrust ("is the agent even reading the right doc?") and the nagging sense of paying for the same lookup over and over.

## Competitive Landscape
**Direct:** Context-management MCP servers (e.g. context-hub "CTX", "Context Mode") — fall short by returning candidate chunks to rank, not one canonical answer with freshness, and rarely close the write/SSOT loop.
**Secondary:** Static instruction files (CLAUDE.md, AGENTS.md, .cursorrules) — fall short because they don't scale, go stale, and can't route a query to the right doc/section.
**Indirect:** "Just let the agent read files" + bigger context windows — falls short because cost compounds across sessions and a whole fleet, and big context ≠ correct/current context.

## Differentiation
**Key differentiators:**
- Returns the ONE canonical doc (with `path:line` + freshness: canonical / stale / duplicate), not a candidate list.
- Section-level reads — serve two paragraphs, not the whole file.
- Shared write path — agents save what they learn once; the whole fleet and teammates read it (SSOT by construction).
- Local-first — runs on your machine, vectors in SQLite, ONNX embeddings, no cloud or API keys.
- Token-savings receipts — a dashboard that shows exactly what you stopped spending.
**How we do it differently:** One point of passage for every read and write, so there's no sync and no copies that drift.
**Why that's better:** Same answers and context for ~60% fewer tokens, plus a single source of truth across agents and people.
**Why customers choose us:** It pays for itself with a number you can see, and it's a 1-minute local install with no lock-in.

## Objections
| Objection | Response |
|-----------|----------|
| "My context window is huge — why bother?" | Cost compounds: every session × every agent × every teammate. Big context also ≠ current context; Trovex serves the *right* doc, cheaply. |
| "I already use CLAUDE.md / AGENTS.md." | That's one static blob that goes stale and can't route a query to the right doc/section. Trovex keeps many docs canonical and serves the one that answers. |
| "Another tool to run?" | One MCP server, ~1-minute local setup, no cloud/keys. It shows you the tokens it saves so it justifies itself. |

**Anti-persona:** Teams with a tiny doc set or no agents; enterprises that want a hosted SaaS with SSO/compliance (Trovex is local OSS today).

## Switching Dynamics
**Push:** Agents reread the repo, blow the context window, surface stale docs, and the token bill keeps climbing.
**Pull:** One canonical answer per query + a visible savings number + local, no-lock-in setup.
**Habit:** Just letting the agent read files / hand-maintaining a CLAUDE.md.
**Anxiety:** "Is it one more thing to maintain?" and "Will it actually return the *right* doc?" (answered by the freshness markers + the savings receipts).

## Customer Language
**How they describe the problem:**
- "My agent keeps rereading the whole repo."
- "It picked the old/stale doc again."
- "I'm burning tokens / money on context."
- "Which file is the source of truth?"
**How they describe us:**
- "One source of truth for my agents."
- "It just gives the agent the right doc."
**Words to use:** canonical, source of truth, tokens, reread, stale, current, local, runs on your machine, one answer, freshness.
**Words to avoid:** hype/puffery (revolutionary, seamless, supercharge, unlock), "AI-powered", vague "context management", em-dash-heavy AI-slop phrasing.
**Glossary:**
| Term | Meaning |
|------|---------|
| canonical | the current, authoritative doc for a topic |
| stale / duplicate | freshness markers Trovex returns alongside a result |
| MCP | Model Context Protocol — how agents call Trovex's tools |
| SSOT | single source of truth — one shared store for all agents/people |
| record | an agent-written note (incident/decision) saved in the store |

## Brand Voice
**Tone:** Plain, confident, developer-honest. Cost-framed, no hype.
**Style:** Direct and specific; write from the user's side ("your agents", "your docs"), not how it's built. Specific > clever. Lowercase wordmark `trovex`.
**Personality:** precise, frugal, credible, no-nonsense, quietly opinionated.

## Proof Points
**Metrics:** ~60% fewer tokens per doc lookup (one canonical answer vs. reading the top stale files); savings-dashboard "receipts" (e.g. tokens saved this week).
**Customers:** None yet — pre-launch, OSS. Do NOT fabricate logos/testimonials.
**Testimonials:** none yet.
**Value themes:**
| Theme | Proof |
|-------|-------|
| Token-efficient | savings dashboard shows would-have-read vs actual, ~60% reduction |
| Right answer, not a pile | freshness-marked canonical result, stale/duplicate skipped |
| Shared source of truth | one read/write point across agents and teammates |
| Local, no lock-in | SQLite + ONNX, no cloud/API keys |

## Goals
**Business goal:** Adoption that surfaces consulting leads. OSS reach (activations + an engaged following) builds credibility and a top-of-funnel; the money is **consulting for dev teams** running agents at scale. Trovex is a proof-of-competence magnet, not a product to monetize directly.
**Conversion action (product):** `uv run trovex index <repo>` then run it / star the repo on GitHub; be discovered via MCP registries.
**Conversion action (business):** A team lead seeing the tool → reaches out for help running agents well across their team (consulting). Make that path visible (e.g. a low-key "working with a team? let's talk" on the site/README) without turning the OSS into a sales page.
**Current metrics:** Pre-users. Landing live at trovex.dev (just shipped); repo github.com/TsukumoHQ/trovex.
