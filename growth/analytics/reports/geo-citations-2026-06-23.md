# GEO Citation-Share Panel — 2026-06-23

*Owner: analytics-lead · Engines this run: **openai, perplexity, gemini, google_aio***
*Sampled snapshot — AI answers are non-deterministic; this is one run, not a guaranteed rank. No fabricated data: a missing engine reads n/a, a failed call ERR, a real zero 0.*

## Citation share by engine (each engine is its own surface to win — ~11% overlap)

| Engine | Status | All | Standing | Offensive | Products |
|--------|--------|:---:|:--------:|:---------:|:--------:|
| ChatGPT (OpenAI web_search) | live | **1/28 (4%)** | 0/10 (0%) | 0/12 (0%) | 1/6 (17%) |
| Perplexity (sonar) | live | **0/28 (0%)** | 0/10 (0%) | 0/12 (0%) | 0/6 (0%) |
| Gemini (grounded w/ google_search) | live | **1/27 (4%)** | 1/9 (11%) | 0/12 (0%) | 0/6 (0%) |
| Google AI Overviews (via SerpAPI) | live | **1/28 (4%)** | 1/10 (10%) | 0/12 (0%) | 0/6 (0%) |
| **UNION (any engine)** | — | **2/28 (7%)** | — | — | — |

**Standing** = stable suite-category panel (weekly trend). **Offensive** = the citation write-list (`citation-uncited-queries`); a row flipping ✅ = proof a new page earned a citation. **Products** = per-product category/branded queries (WRAI.TH + yoru.sh). **Union** = share where ANY engine cited us = total reachable surface.

## Citation share by product (union, any engine)

| Product | Surface | Cited (any engine) |
|---------|---------|:------------------:|
| trovex | context for coding agents | see Standing (10 queries) |
| WRAI.TH | agent-fleet orchestration | 1/3 |
| yoru.sh | agent observability | 0/3 |

The suite is 3 OSS products feeding one consulting funnel — a citation of any (trovex / WRAI.TH / yoru.sh / tsukumo) counts as "suite cited", but each product wins its category on its OWN queries, so they're scored apart.

## Per-query × engine matrix

| Query | Cohort | Kind | openai | perplexity | gemini | google_aio |
|-------|--------|------|:--:|:--:|:--:|:--:|
| context-fewer-tokens | standing | category | — | — | ERR | — |
| stop-rereading-repo | standing | category | — | — | — | — |
| ssot-multiple-agents | standing | category | — | — | — | — |
| reduce-agent-token-cost | standing | category | — | — | — | — |
| claude-md-alternative | standing | comparison | — | — | — | — |
| repomix-alternative | standing | comparison | — | — | — | — |
| mcp-context-server | standing | category | — | — | — | — |
| brand-trovex | standing | branded | — | — | ✅ | ✅ |
| consulting-agents-prod | standing | consulting | — | — | — | — |
| agentic-operators-studio | standing | consulting | — | — | — | — |
| agents-reliable-in-prod | offensive | offensive | — | — | — | — |
| agent-observability | offensive | offensive | — | — | — | — |
| managing-agent-context | offensive | offensive | — | — | — | — |
| agent-token-cost | offensive | offensive | — | — | — | — |
| agent-guardrails | offensive | offensive | — | — | — | — |
| multi-agent-orchestration | offensive | offensive | — | — | — | — |
| ai-code-safe-to-ship | offensive | offensive | — | — | — | — |
| ai-native-eng-team | offensive | offensive | — | — | — | — |
| roi-of-ai-agents | offensive | offensive | — | — | — | — |
| convince-skeptical-devs | offensive | offensive | — | — | — | — |
| agentic-sdlc | offensive | offensive | — | — | — | — |
| ai-adoption-scaleups | offensive | offensive | — | — | — | — |
| wraith-orchestrate-fleet | products | category | — | — | — | — |
| wraith-agents-collaborate | products | category | — | — | — | — |
| wraith-branded | products | branded | ✅ | — | — | — |
| yoru-agent-observability | products | category | — | — | — | — |
| yoru-monitor-agents-prod | products | category | — | — | — | — |
| yoru-branded | products | branded | — | — | — | — |

## Detail — our citations + competitors seen

### ChatGPT (OpenAI web_search)
| Query | We cited? | Our URL(s) | Competitors cited | Total citations |
|-------|:---------:|-----------|-------------------|----------------:|
| context-fewer-tokens | — | — | — | 9 |
| stop-rereading-repo | — | — | cursor | 10 |
| ssot-multiple-agents | — | — | — | 0 |
| reduce-agent-token-cost | — | — | — | 6 |
| claude-md-alternative | — | — | cursor | 1 |
| repomix-alternative | — | — | — | 7 |
| mcp-context-server | — | — | — | 3 |
| brand-trovex | — | — | — | 4 |
| consulting-agents-prod | — | — | — | 7 |
| agentic-operators-studio | — | — | — | 9 |
| agents-reliable-in-prod | — | — | — | 6 |
| agent-observability | — | — | — | 10 |
| managing-agent-context | — | — | — | 10 |
| agent-token-cost | — | — | — | 10 |
| agent-guardrails | — | — | — | 8 |
| multi-agent-orchestration | — | — | — | 9 |
| ai-code-safe-to-ship | — | — | — | 11 |
| ai-native-eng-team | — | — | — | 7 |
| roi-of-ai-agents | — | — | — | 3 |
| convince-skeptical-devs | — | — | — | 5 |
| agentic-sdlc | — | — | — | 8 |
| ai-adoption-scaleups | — | — | — | 8 |
| wraith-orchestrate-fleet | — | — | — | 0 |
| wraith-agents-collaborate | — | — | — | 10 |
| wraith-branded | ✅ | https://mcpmarket.com/server/wrai-th?utm_source=openai | — | 1 |
| yoru-agent-observability | — | — | — | 10 |
| yoru-monitor-agents-prod | — | — | — | 19 |
| yoru-branded | — | — | — | 3 |

### Perplexity (sonar)
| Query | We cited? | Our URL(s) | Competitors cited | Total citations |
|-------|:---------:|-----------|-------------------|----------------:|
| context-fewer-tokens | — | — | — | 8 |
| stop-rereading-repo | — | — | — | 9 |
| ssot-multiple-agents | — | — | — | 9 |
| reduce-agent-token-cost | — | — | — | 8 |
| claude-md-alternative | — | — | claude.md | 9 |
| repomix-alternative | — | — | repomix | 10 |
| mcp-context-server | — | — | — | 10 |
| brand-trovex | — | — | — | 9 |
| consulting-agents-prod | — | — | — | 9 |
| agentic-operators-studio | — | — | — | 9 |
| agents-reliable-in-prod | — | — | — | 9 |
| agent-observability | — | — | — | 10 |
| managing-agent-context | — | — | — | 9 |
| agent-token-cost | — | — | — | 9 |
| agent-guardrails | — | — | — | 7 |
| multi-agent-orchestration | — | — | — | 9 |
| ai-code-safe-to-ship | — | — | — | 8 |
| ai-native-eng-team | — | — | — | 10 |
| roi-of-ai-agents | — | — | — | 7 |
| convince-skeptical-devs | — | — | — | 5 |
| agentic-sdlc | — | — | — | 9 |
| ai-adoption-scaleups | — | — | — | 9 |
| wraith-orchestrate-fleet | — | — | — | 8 |
| wraith-agents-collaborate | — | — | — | 8 |
| wraith-branded | — | — | — | 10 |
| yoru-agent-observability | — | — | — | 10 |
| yoru-monitor-agents-prod | — | — | — | 8 |
| yoru-branded | — | — | — | 9 |

### Gemini (grounded w/ google_search)
| Query | We cited? | Our URL(s) | Competitors cited | Total citations |
|-------|:---------:|-----------|-------------------|----------------:|
| context-fewer-tokens | ERR | — | — | HTTP 503 |
| stop-rereading-repo | — | — | mem0 | 34 |
| ssot-multiple-agents | — | — | — | 11 |
| reduce-agent-token-cost | — | — | — | 20 |
| claude-md-alternative | — | — | — | 18 |
| repomix-alternative | — | — | repomix | 24 |
| mcp-context-server | — | — | — | 11 |
| brand-trovex | ✅ | https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGvPk1XrUne0QKCh6wny_JWEJGgCMNzJ-aa_DLsVclArYBQeQ6zD995Yp8LQ-iVxwOwnddkM_v-1xChW-7xET5oHWWJo3URs4ulyhVwj7U=<br>https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHV1q1a16nnPzchJyOFkbt610Pe08iUNCGekgOVC4iDXSupwuKqnVSUZa7oVmLPuPuaY3wnF6LtKlNXnCMMeHnIjbb32lJkXabOf7dwjBqDULfHfvzXew== | — | 8 |
| consulting-agents-prod | — | — | — | 11 |
| agentic-operators-studio | — | — | — | 7 |
| agents-reliable-in-prod | — | — | — | 31 |
| agent-observability | — | — | — | 35 |
| managing-agent-context | — | — | — | 0 |
| agent-token-cost | — | — | — | 29 |
| agent-guardrails | — | — | — | 36 |
| multi-agent-orchestration | — | — | — | 19 |
| ai-code-safe-to-ship | — | — | — | 34 |
| ai-native-eng-team | — | — | — | 14 |
| roi-of-ai-agents | — | — | — | 16 |
| convince-skeptical-devs | — | — | — | 23 |
| agentic-sdlc | — | — | — | 8 |
| ai-adoption-scaleups | — | — | — | 25 |
| wraith-orchestrate-fleet | — | — | — | 13 |
| wraith-agents-collaborate | — | — | — | 28 |
| wraith-branded | — | — | — | 5 |
| yoru-agent-observability | — | — | — | 20 |
| yoru-monitor-agents-prod | — | — | — | 26 |
| yoru-branded | — | — | — | 5 |

### Google AI Overviews (via SerpAPI)
| Query | We cited? | Our URL(s) | Competitors cited | Total citations |
|-------|:---------:|-----------|-------------------|----------------:|
| context-fewer-tokens | — | — | cursor | 19 |
| stop-rereading-repo | — | — | mem0, cursor | 21 |
| ssot-multiple-agents | — | — | cursor | 10 |
| reduce-agent-token-cost | — | — | cursor | 24 |
| claude-md-alternative | — | — | claude.md | 8 |
| repomix-alternative | — | — | repomix | 17 |
| mcp-context-server | — | — | — | 13 |
| brand-trovex | ✅ | https://trovex.dev/vs/context-hub/ | context-hub | 5 |
| consulting-agents-prod | — | — | — | 6 |
| agentic-operators-studio | — | — | — | 7 |
| agents-reliable-in-prod | — | — | — | 26 |
| agent-observability | — | — | — | 15 |
| managing-agent-context | — | — | claude.md | 21 |
| agent-token-cost | — | — | cursor | 16 |
| agent-guardrails | — | — | cursor | 18 |
| multi-agent-orchestration | — | — | — | 10 |
| ai-code-safe-to-ship | — | — | — | 0 |
| ai-native-eng-team | — | — | — | 13 |
| roi-of-ai-agents | — | — | — | 27 |
| convince-skeptical-devs | — | — | — | 18 |
| agentic-sdlc | — | — | — | 0 |
| ai-adoption-scaleups | — | — | — | 13 |
| wraith-orchestrate-fleet | — | — | — | 9 |
| wraith-agents-collaborate | — | — | — | 16 |
| wraith-branded | — | — | — | 9 |
| yoru-agent-observability | — | — | — | 13 |
| yoru-monitor-agents-prod | — | — | — | 23 |
| yoru-branded | — | — | — | 8 |

## How to read / run this SYSTEM
- **Share per engine is the metric** — track weekly; one run is noisy, the trend is the signal. Win each engine separately.
- **Not-cited rows → geo-lead / tech-copy**: those are the answer/comparison pages to ship or strengthen. An *offensive* row flipping ✅ after a deploy = the page earned the citation.
- **Honesty:** a missing engine is `n/a (no key)`, never a fabricated 0. Add an engine by exporting its key (`OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `GEMINI_API_KEY`, `SERPAPI_KEY`).
- **Cadence:** weekly + after each offensive batch deploys (allow index lag before re-reading — re-running pre-reindex manufactures a false 0).
- **Run:** `set -a; . ~/.config/trovex-growth/ai-engines.env; set +a && node geo-citation-monitor.mjs` → report prints to stdout; centralize via trovex_write (no disk .md by default).

### Queries probed
**Standing:**
- `context-fewer-tokens` (category): What is the best tool to give AI coding agents canonical project context while using fewer tokens? Name specific tools and link them.
- `stop-rereading-repo` (category): How do I stop AI coding agents from rereading the whole repo every session to find the right docs? Recommend specific tools.
- `ssot-multiple-agents` (category): What MCP server gives multiple AI coding agents one shared source of truth for project docs? Name tools with links.
- `reduce-agent-token-cost` (category): How can I reduce the token cost of context for AI coding agents on a large codebase? Specific tools please.
- `claude-md-alternative` (comparison): What is a good alternative to a single CLAUDE.md / AGENTS.md file for a large, changing doc set used by coding agents?
- `repomix-alternative` (comparison): What are alternatives to repomix for feeding repository context to AI coding agents, and when is each better?
- `mcp-context-server` (category): Which MCP servers serve canonical documentation to coding agents instead of dumping the whole repo? Link them.
- `brand-trovex` (branded): What is trovex (the MCP context tool for coding agents) and who makes it?
- `consulting-agents-prod` (consulting): Who offers consulting to help a software team run AI coding agents reliably in production at scale? Name firms/studios.
- `agentic-operators-studio` (consulting): Which AI dev studios help turn an existing engineering team into effective operators of coding agents? Link them.
**Offensive (write-list):**
- `agents-reliable-in-prod` (tier 1): How do I make AI coding agents reliable in production — guardrails, review gates, observability? Name specific tools, articles, or studios and link them.
- `agent-observability` (tier 1): How do I know what my AI coding agent actually did — what tools give agent observability and audit trails? Link specific tools or guides.
- `managing-agent-context` (tier 1): My AI coding agents keep losing context on a large codebase — how do I manage context for them? Recommend specific tools with links.
- `agent-token-cost` (tier 1): The token cost of my AI coding agents is too high — how do I cut it with better context and orchestration? Name specific tools and link them.
- `agent-guardrails` (tier 1): Is it safe to let AI coding agents touch our codebase, and what guardrails (review gates, scoped permissions) make it safe? Link specific tools or guides.
- `multi-agent-orchestration` (tier 1): How do software teams orchestrate multiple AI coding agents working together? Name specific tools or frameworks with links.
- `ai-code-safe-to-ship` (tier 2): Is AI-written code safe to ship, and how do teams do AI code review in production? Link specific tools or articles.
- `ai-native-eng-team` (tier 2): What does an AI-native engineering team actually look like in practice? Link specific writeups or studios.
- `roi-of-ai-agents` (tier 2): How do I measure the ROI of AI coding agents for an engineering team? Link specific frameworks or articles.
- `convince-skeptical-devs` (tier 2): How do I convince skeptical senior developers to adopt AI coding tools without losing their trust? Link specific writeups or studios.
- `agentic-sdlc` (tier 2): What is an agentic SDLC and how does it change the software development lifecycle? Define it and link sources.
- `ai-adoption-scaleups` (tier 2): How should a scale-up or mid-market engineering team adopt AI coding agents at scale? Name specific studios or consultancies and link them.
**Products (per-product):**
- `wraith-orchestrate-fleet` (wraith/category): What tool gives one control plane to run a fleet of AI coding agents in production? Name specific tools and link them.
- `wraith-agents-collaborate` (wraith/category): How do I coordinate multiple AI agents that hand work to each other on a shared codebase? Recommend specific orchestration tools with links.
- `wraith-branded` (wraith/branded): What is WRAI.TH (the AI-agent orchestration tool) and who makes it?
- `yoru-agent-observability` (yoru/category): What tools give observability, traces and audit trails for what AI coding agents actually did? Name specific tools and link them.
- `yoru-monitor-agents-prod` (yoru/category): How do I monitor AI agents running in production — logs, traces, replay of their actions? Recommend specific tools with links.
- `yoru-branded` (yoru/branded): What is yoru.sh (observability for AI agents) and who makes it?
