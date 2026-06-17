# GEO citation attack — query → target → gap (0/10 offensive)

**Owner:** geo-lead · **Date:** 2026-06-17 · From analytics' citation-share monitor (`growth/analytics/geo-citation-monitor.mjs`, report `reports/geo-citations-2026-06-16.md`, **0/10** on the first OpenAI-web-search run).

## The reframe (important)

The 0/10 is **not** a "we have no answers" problem. Every one of the 10 probed queries **already has a strong, live target page** — trovex.dev has 9 `/answers/*` (QAPage schema) + 12 `/vs/*` comparison pages + a full `llms.txt`/`llms-full.txt`/sitemap. The 0/10 is best explained by:
1. **Indexing lag** — the pages shipped ~the monitor date; OpenAI web_search hadn't indexed them.
2. **One non-deterministic run, OpenAI-only** — the report says so itself; Perplexity + Google AI Overviews are still TODO (need keys).
3. **Young/branded** — for `brand-trovex` the engine simply doesn't know us yet; that's earned-citation + time, not an on-page fix.

So the offensive is **tune + widen + earn**, not "build pages that already exist." This doc maps each query to its page and the real gap.

## Property split

8 of 10 queries are **trovex-product** (trovex.dev / this repo). 2 are **consulting** (tsukumo.ch — separate repo). The dispatch said "tsukumo repo"; the queries put the bulk on trovex.dev. Mapped accordingly below.

## The map

| # | Query (monitor id) | Kind | Property | Target URL (exists, live) | Gap → action |
|---|---|---|---|---|---|
| 1 | context-fewer-tokens | category | trovex | `/answers/canonical-context-for-agents/` | no Speakable / no freshness date → add (PR B) |
| 2 | stop-rereading-repo | category | trovex | `/answers/stop-agent-rereading-docs/` | Speakable + freshness → PR B |
| 3 | ssot-multiple-agents | category | trovex | `/answers/shared-source-of-truth-multiple-agents/` (+ `/source-of-truth-multi-agent-repos/`) | 2nd page now surfaced in llms.txt (this PR); Speakable+freshness → PR B |
| 4 | reduce-agent-token-cost | category | trovex | `/answers/reduce-agent-token-costs/` | Speakable + freshness → PR B |
| 7 | mcp-context-server | category | trovex | `/answers/mcp-server-for-repo-docs/` | **was missing from llms.txt — added this PR**; Speakable+freshness → PR B |
| 5 | claude-md-alternative | comparison | trovex | `/vs/claude-md/` | Speakable + freshness; confirm a 40–60-word direct answer leads → PR B |
| 6 | repomix-alternative | comparison | trovex | `/vs/repomix/` | repomix *is* cited here — beat it: Speakable + freshness + sharper "when each is better" lead → PR B |
| 8 | brand-trovex | branded | trovex | `/` + `llms.txt` (both strong) | on-page already optimal; this is **discovery/age** → earned citations + time (off-site), not a content fix |
| 9 | consulting-agents-prod | consulting | **tsukumo** | `/answers/what-is-ai-in-production-consulting`, `/answers/get-dev-team-using-ai-agents` | tune for "reliably in production **at scale**" intent → PR C (tsukumo) |
| 10 | agentic-operators-studio | consulting | **tsukumo** | `/answers/ai-native-engineering-team`, `/studio`, glossary "agentic operator" | tune for "AI **dev studio**" framing → PR C (tsukumo) |

## Done this PR (A)
- `web/public/llms.txt`: surfaced `mcp-server-for-repo-docs` (the Q7 target — was absent) and `source-of-truth-multi-agent-repos` (2nd Q3 target) in the Answers list.
- This map.

## Sequenced next (the actual citability lift)
- **PR B — trovex (highest lift):** add `Speakable` + `dateModified`/`datePublished` to all 9 `/answers` + 12 `/vs` pages. Recency is the biggest cheap signal (industry data: ~+30% citation; ~82% of cited pages are <30 days), and Speakable marks the passage engines quote. Both are currently **absent** on these pages. Confirm each page leads with a 40–60-word direct answer.
- **PR C — tsukumo:** confirm/tune the two consulting answer pages for the exact Q9/Q10 intent ("at scale / in production", "AI dev studio").
- **analytics-lead:** re-run the monitor (owns `OPENAI_API_KEY`) to track movement once PR B deploys + indexes; **widen the panel to Perplexity + Google AI Overviews** before drawing conclusions from one OpenAI run.
- **launch / social / content:** the off-site half — `brand-trovex` and cold category discovery are won by earned citations (Reddit/HN/awesome-lists/listicles), per `growth/geo/earned-citation-strategy.md` (tsukumo) and the suite's own GitHub presence.

## Honesty
No fabricated metrics; the only number is the real ~60% (trovex). The map states what exists vs what's missing — no claim that 0/10 is "fixed" by content alone; the largest lever for the branded/cold queries is time + earned citations, tracked weekly by analytics.
