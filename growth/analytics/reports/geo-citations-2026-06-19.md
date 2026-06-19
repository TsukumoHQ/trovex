# GEO Citation-Share Panel — 2026-06-19

*Owner: analytics-lead · Engines this run: **openai, perplexity, gemini, google_aio***
*Sampled snapshot — AI answers are non-deterministic; this is one run, not a guaranteed rank. No fabricated data: a missing engine reads n/a, a failed call ERR, a real zero 0.*

## Citation share by engine (each engine is its own surface to win — ~11% overlap)

| Engine | Status | All | Standing | Offensive |
|--------|--------|:---:|:--------:|:---------:|
| ChatGPT (OpenAI web_search) | live | **0/22 (0%)** | 0/10 (0%) | 0/12 (0%) |
| Perplexity (sonar) | live | **0/22 (0%)** | 0/10 (0%) | 0/12 (0%) |
| Gemini (grounded w/ google_search) | live | **0/0 (0%)** | 0/0 (0%) | 0/0 (0%) |
| Google AI Overviews (via SerpAPI) | live | **1/22 (5%)** | 1/10 (10%) | 0/12 (0%) |
| **UNION (any engine)** | — | **1/22 (5%)** | — | — |

**Standing** = stable suite-category panel (weekly trend). **Offensive** = the citation write-list (`citation-uncited-queries`); a row flipping ✅ = proof a new page earned a citation. **Union** = share where ANY engine cited us = total reachable surface.

## Per-query × engine matrix

| Query | Cohort | Kind | openai | perplexity | gemini | google_aio |
|-------|--------|------|:--:|:--:|:--:|:--:|
| context-fewer-tokens | standing | category | — | — | ERR | — |
| stop-rereading-repo | standing | category | — | — | ERR | — |
| ssot-multiple-agents | standing | category | — | — | ERR | — |
| reduce-agent-token-cost | standing | category | — | — | ERR | — |
| claude-md-alternative | standing | comparison | — | — | ERR | — |
| repomix-alternative | standing | comparison | — | — | ERR | — |
| mcp-context-server | standing | category | — | — | ERR | — |
| brand-trovex | standing | branded | — | — | ERR | ✅ |
| consulting-agents-prod | standing | consulting | — | — | ERR | — |
| agentic-operators-studio | standing | consulting | — | — | ERR | — |
| agents-reliable-in-prod | offensive | offensive | — | — | ERR | — |
| agent-observability | offensive | offensive | — | — | ERR | — |
| managing-agent-context | offensive | offensive | — | — | ERR | — |
| agent-token-cost | offensive | offensive | — | — | ERR | — |
| agent-guardrails | offensive | offensive | — | — | ERR | — |
| multi-agent-orchestration | offensive | offensive | — | — | ERR | — |
| ai-code-safe-to-ship | offensive | offensive | — | — | ERR | — |
| ai-native-eng-team | offensive | offensive | — | — | ERR | — |
| roi-of-ai-agents | offensive | offensive | — | — | ERR | — |
| convince-skeptical-devs | offensive | offensive | — | — | ERR | — |
| agentic-sdlc | offensive | offensive | — | — | ERR | — |
| ai-adoption-scaleups | offensive | offensive | — | — | ERR | — |

## Detail — our citations + competitors seen

### ChatGPT (OpenAI web_search)
| Query | We cited? | Our URL(s) | Competitors cited | Total citations |
|-------|:---------:|-----------|-------------------|----------------:|
| context-fewer-tokens | — | — | — | 10 |
| stop-rereading-repo | — | — | — | 10 |
| ssot-multiple-agents | — | — | — | 0 |
| reduce-agent-token-cost | — | — | — | 10 |
| claude-md-alternative | — | — | — | 0 |
| repomix-alternative | — | — | repomix, aider | 6 |
| mcp-context-server | — | — | — | 3 |
| brand-trovex | — | — | — | 3 |
| consulting-agents-prod | — | — | — | 11 |
| agentic-operators-studio | — | — | — | 10 |
| agents-reliable-in-prod | — | — | — | 8 |
| agent-observability | — | — | — | 10 |
| managing-agent-context | — | — | cursor | 10 |
| agent-token-cost | — | — | — | 10 |
| agent-guardrails | — | — | — | 7 |
| multi-agent-orchestration | — | — | — | 10 |
| ai-code-safe-to-ship | — | — | — | 5 |
| ai-native-eng-team | — | — | — | 8 |
| roi-of-ai-agents | — | — | — | 4 |
| convince-skeptical-devs | — | — | — | 7 |
| agentic-sdlc | — | — | — | 6 |
| ai-adoption-scaleups | — | — | — | 8 |

### Perplexity (sonar)
| Query | We cited? | Our URL(s) | Competitors cited | Total citations |
|-------|:---------:|-----------|-------------------|----------------:|
| context-fewer-tokens | — | — | — | 8 |
| stop-rereading-repo | — | — | — | 9 |
| ssot-multiple-agents | — | — | — | 10 |
| reduce-agent-token-cost | — | — | — | 7 |
| claude-md-alternative | — | — | — | 8 |
| repomix-alternative | — | — | repomix | 10 |
| mcp-context-server | — | — | — | 10 |
| brand-trovex | — | — | — | 9 |
| consulting-agents-prod | — | — | — | 7 |
| agentic-operators-studio | — | — | — | 9 |
| agents-reliable-in-prod | — | — | — | 9 |
| agent-observability | — | — | — | 10 |
| managing-agent-context | — | — | — | 9 |
| agent-token-cost | — | — | — | 9 |
| agent-guardrails | — | — | — | 8 |
| multi-agent-orchestration | — | — | — | 8 |
| ai-code-safe-to-ship | — | — | — | 7 |
| ai-native-eng-team | — | — | — | 9 |
| roi-of-ai-agents | — | — | — | 8 |
| convince-skeptical-devs | — | — | — | 8 |
| agentic-sdlc | — | — | — | 9 |
| ai-adoption-scaleups | — | — | — | 9 |

### Gemini (grounded w/ google_search)
| Query | We cited? | Our URL(s) | Competitors cited | Total citations |
|-------|:---------:|-----------|-------------------|----------------:|
| context-fewer-tokens | ERR | — | — | HTTP 429 |
| stop-rereading-repo | ERR | — | — | HTTP 429 |
| ssot-multiple-agents | ERR | — | — | HTTP 429 |
| reduce-agent-token-cost | ERR | — | — | HTTP 429 |
| claude-md-alternative | ERR | — | — | HTTP 429 |
| repomix-alternative | ERR | — | — | HTTP 429 |
| mcp-context-server | ERR | — | — | HTTP 429 |
| brand-trovex | ERR | — | — | HTTP 429 |
| consulting-agents-prod | ERR | — | — | HTTP 429 |
| agentic-operators-studio | ERR | — | — | HTTP 429 |
| agents-reliable-in-prod | ERR | — | — | HTTP 429 |
| agent-observability | ERR | — | — | HTTP 429 |
| managing-agent-context | ERR | — | — | HTTP 429 |
| agent-token-cost | ERR | — | — | HTTP 429 |
| agent-guardrails | ERR | — | — | HTTP 429 |
| multi-agent-orchestration | ERR | — | — | HTTP 429 |
| ai-code-safe-to-ship | ERR | — | — | HTTP 429 |
| ai-native-eng-team | ERR | — | — | HTTP 429 |
| roi-of-ai-agents | ERR | — | — | HTTP 429 |
| convince-skeptical-devs | ERR | — | — | HTTP 429 |
| agentic-sdlc | ERR | — | — | HTTP 429 |
| ai-adoption-scaleups | ERR | — | — | HTTP 429 |

### Google AI Overviews (via SerpAPI)
| Query | We cited? | Our URL(s) | Competitors cited | Total citations |
|-------|:---------:|-----------|-------------------|----------------:|
| context-fewer-tokens | — | — | — | 12 |
| stop-rereading-repo | — | — | cursor, mem0 | 16 |
| ssot-multiple-agents | — | — | — | 12 |
| reduce-agent-token-cost | — | — | — | 20 |
| claude-md-alternative | — | — | claude.md, github.com/anthropics | 10 |
| repomix-alternative | — | — | repomix | 21 |
| mcp-context-server | — | — | cursor | 9 |
| brand-trovex | ✅ | https://in.linkedin.com/company/trovexai<br>https://trovex.ai/<br>https://tracxn.com/d/companies/trovex/__0VzjlVZ-kX2x7TnLiSim-e7AApZDjcrEjDEzqOJASvM | — | 10 |
| consulting-agents-prod | — | — | — | 16 |
| agentic-operators-studio | — | — | — | 11 |
| agents-reliable-in-prod | — | — | — | 32 |
| agent-observability | — | — | — | 17 |
| managing-agent-context | — | — | cursor | 31 |
| agent-token-cost | — | — | mem0 | 11 |
| agent-guardrails | — | — | cursor | 27 |
| multi-agent-orchestration | — | — | — | 11 |
| ai-code-safe-to-ship | — | — | — | 18 |
| ai-native-eng-team | — | — | — | 12 |
| roi-of-ai-agents | — | — | — | 14 |
| convince-skeptical-devs | — | — | — | 14 |
| agentic-sdlc | — | — | — | 13 |
| ai-adoption-scaleups | — | — | — | 26 |

## How to read / run this SYSTEM
- **Share per engine is the metric** — track weekly; one run is noisy, the trend is the signal. Win each engine separately.
- **Not-cited rows → geo-lead / tech-copy**: those are the answer/comparison pages to ship or strengthen. An *offensive* row flipping ✅ after a deploy = the page earned the citation.
- **Honesty:** a missing engine is `n/a (no key)`, never a fabricated 0. Add an engine by exporting its key (`OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `GEMINI_API_KEY`, `SERPAPI_KEY`).
- **Cadence:** weekly + after each offensive batch deploys (allow index lag before re-reading — re-running pre-reindex manufactures a false 0).
- **Run:** `set -a; . ~/.config/trovex-growth/ai-engines.env; set +a && node geo-citation-monitor.mjs`

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
