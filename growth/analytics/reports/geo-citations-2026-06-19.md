# GEO Citation-Share — 2026-06-19 (openai-web-search)

*Owner: analytics-lead · Engine: OpenAI web_search (model `gpt-4o`) · Sampled snapshot — AI answers are non-deterministic; this is one run, not a guaranteed rank. No fabricated data.*

**Suite citation share: 0/22 queries (0%)** — i.e. of the ICP questions probed, the share where trovex/tsukumo/wrai.th/yoru.sh was cited.

**By cohort:**
- **Standing** (suite-category panel, stable weekly trend): **0/10 (0%)**
- **Offensive** (the citation write-list being built — `citation-uncited-queries`): **0/12 (0%)** — verification overlay; expected 0 until pages deploy + get indexed.

| Query | Cohort | Kind | We cited? | Our URL(s) | Competitors cited | Total citations |
|-------|--------|------|:---------:|-----------|-------------------|----------------:|
| context-fewer-tokens | standing | category | — | — | — | 10 |
| stop-rereading-repo | standing | category | — | — | — | 10 |
| ssot-multiple-agents | standing | category | — | — | — | 10 |
| reduce-agent-token-cost | standing | category | — | — | — | 8 |
| claude-md-alternative | standing | comparison | — | — | — | 0 |
| repomix-alternative | standing | comparison | — | — | repomix | 6 |
| mcp-context-server | standing | category | — | — | — | 3 |
| brand-trovex | standing | branded | — | — | — | 3 |
| consulting-agents-prod | standing | consulting | — | — | — | 8 |
| agentic-operators-studio | standing | consulting | — | — | — | 10 |
| agents-reliable-in-prod | offensive | offensive | — | — | — | 7 |
| agent-observability | offensive | offensive | — | — | — | 10 |
| managing-agent-context | offensive | offensive | — | — | — | 10 |
| agent-token-cost | offensive | offensive | — | — | — | 10 |
| agent-guardrails | offensive | offensive | — | — | — | 5 |
| multi-agent-orchestration | offensive | offensive | — | — | — | 10 |
| ai-code-safe-to-ship | offensive | offensive | — | — | — | 14 |
| ai-native-eng-team | offensive | offensive | — | — | — | 7 |
| roi-of-ai-agents | offensive | offensive | — | — | — | 6 |
| convince-skeptical-devs | offensive | offensive | — | — | — | 7 |
| agentic-sdlc | offensive | offensive | — | — | — | 6 |
| ai-adoption-scaleups | offensive | offensive | — | — | — | 6 |

## How to read this
- **Share is the metric** — track it weekly; one run is noisy, the trend is the signal.
- **Two cohorts:** *standing* keeps the weekly trend comparable; *offensive* is the post-deploy verification overlay for the queries tech-copy/geo are actively building answers for. A row in *offensive* flipping ✅ is the proof a new page earned a citation.
- **Unbranded "category" queries** = the real prize (a buyer asking generically). **Branded** = does the engine even know us yet.
- Hand the not-cited rows back to geo-lead/tech-copy: those are the answer/comparison pages to ship or strengthen.
- Engine coverage: OpenAI web_search live; **Perplexity + Google AI Overviews are TODO (need their own keys)** — add them to widen the panel.

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
