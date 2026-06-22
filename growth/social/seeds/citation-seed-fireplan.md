# Citation seed kit — fire-plan (social-lead)

> **A HUMAN fires every one of these.** This is the *firing discipline* layer — the snippet
> COPY lives single-sourced in the geo doc (don't duplicate it): **`trovex_read f334c83e`**
> (GEO citation seed kit — 14 answer/comparison snippets + per-snippet UTM'd trovex.dev links).
>
> Lever: analytics — **0/4 owned-domain citations**; on-page is maxed, only off-site moves the
> AI-engine citation share (Perplexity/ChatGPT/AIO source Reddit + HN heavily).
> Positioning = **public beta, open source**. Only first-party number ~60%. Lowercase `trovex`.

## The one rule
Answer the question **first and completely**. The link is the citation, not the point. If the
snippet doesn't genuinely answer the thread, don't post it. Never a link-drop, never an ad.

## Skip / coordinate
- **#5 mcp-server-for-repo-docs + #6** → SKIP. launch-lead already folded these into the
  OSS-list / awesome-mcp blurbs (trovex 9872a469) — bare GitHub link there, don't double-seed.
- Founder-voice venues (a builder answering): **NO consulting** (P0 0b61b80f). Company/neutral
  venues can carry the consulting wedge, but these snippets are tool-answers — keep them builder.

## Venue + cadence (per-account, human-paced)
| # | Snippet (in f334c83e) | Best venues | utm_source |
|---|---|---|---|
| 1 | stop-agent-rereading-docs | HN "agents reread repo", r/ChatGPTCoding, r/ClaudeAI | hackernews / reddit |
| 2 | reduce-agent-token-costs | r/LocalLLaMA, HN cost-of-agents | reddit / hackernews |
| 3 | token-cost-of-agent-context | cost-mechanism threads, newsletters | hackernews / newsletter |
| 4 | canonical-context-for-agents | "what is X" / definitional, Perplexity-style | reddit / hackernews |
| 7–8 | (SSOT / stale-docs cluster — see doc) | HN/Reddit CLAUDE.md·AGENTS.md threads | hackernews / reddit |
| 9 | bigger-context-window-rereading | "just use a 1M window" threads | hackernews / reddit |
| 10 | local-first-context-for-agents | r/LocalLLaMA, r/selfhosted, privacy | reddit |
| 11 | vs/claude-md | claude.md-alternative threads (highest-citation) | reddit / hackernews |
| 12 | vs/repomix | repomix-alternative threads | reddit / hackernews |
| 13 | vs/context-hub | "context store over MCP" threads | reddit / hackernews |
| 14 | vs/cursor-memory | Cursor-memory / cross-editor threads | reddit / hackernews |

**Comparison snippets (11–14) are the highest-citation format** — prioritize them; the engines
reach for repomix/cursor/mem0/claude.md on our category queries (GEO panel 9e9c78ab).

## Venue priority (2026 GEO data — lane base f3260b49)
AI engines cite from a **wider pool than the organic SERP**: >40% of AI-Overview citations don't
rank top-10, and the cited pool leans Reddit / Quora / YouTube transcripts / docs. So seed where
the engines actually retrieve, in this order:
1. **Reddit** — primary. The subreddits already mapped per snippet above (r/ChatGPTCoding, r/ClaudeAI,
   r/LocalLLaMA, r/AI_Agents, r/selfhosted). Highest citation pull for our category questions.
2. **Quora** — primary. Definitional / "what is X" / "how do I X" snippets (1, 3, 4, 7–9) fit Quora's
   evergreen Q&A surface, which the engines retrieve heavily. ⚠️ `utm_source=quora` NOT yet mapped in
   analytics — request pending (see UTM note); hold Quora links until mapped or the click decays to unknown.
3. **HN** — keep, but for the **dev-credibility** hit (real builders reading), not citation volume. The
   comparison snippets (11–14) and cost/mechanism threads play best here.
The off-site lever is the binding constraint on citations (owned-domain = 0/4, on-page maxed) — the
venue is the move, not more on-page work.

## Pace (don't get the domain flagged)
- **≤1–2 seeds / week per account**, staggered across days. Never two in the same subreddit in a
  week. Build/keep real account history (~9:1 give:promote).
- Reply to responses for the first hour — that's where the answer earns the citation.
- One genuine answer per thread; don't paste the snippet verbatim into unrelated threads —
  adapt the opener to the actual question (ping geo for a venue-specific reword if needed).

## UTM (every link)
`utm_source=<hackernews|reddit>` (CLOSED list — mapped), `utm_medium=community`,
`utm_campaign=geo-seed`, `utm_content=<snippet-slug>` (already on each link in f334c83e).
**Lobsters / Discord / Quora are NOT mapped** in analytics.ts → ping analytics before using those as a
source, or the click decays to unknown. `threads` also unmapped. Quora mapping requested 2026-06-22
(needed to promote Quora to a primary venue per the priority section above).

## Status
DRAFT fire-plan. Snippets ready in f334c83e. Human fires per this cadence; I coordinate venues
with geo-lead and flag rewords. Nothing auto-posted — forum answers are not an autoPublish lane.
