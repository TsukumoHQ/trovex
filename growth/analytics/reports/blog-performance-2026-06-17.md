# Per-Blog-Post Performance — 2026-06-17

*Owner: analytics-lead · Plausible window 2026-05-18→2026-06-17 (LIVE) · GSC + AI-citation columns pending access (see blog-performance.md). No fabricated data — a post with no traffic reads 0.*

**30 posts · 8 with any pageviews · 19 total blog pageviews (window).** Pre-launch: counts are tiny and mostly crawler/verification traffic, not organic readers — this is the baseline, re-read after a distribution push.

| # | Post | Pageviews | Visitors | AI-cited? | GSC pos | Sessions→lead |
|--:|------|----------:|---------:|:---------:|--------:|---------------|
| 1 | `deterministic-state-machines-over-llms` | 5 | 1 | ‹pending› | ‹GSC› | ‹funnel› |
| 2 | `how-we-ship-with-an-agent-fleet` | 4 | 1 | ‹pending› | ‹GSC› | ‹funnel› |
| 3 | `compliance-as-architecture-constraint` | 3 | 1 | ‹pending› | ‹GSC› | ‹funnel› |
| 4 | `managing-context-for-ai-coding-agents` | 2 | 1 | ‹pending› | ‹GSC› | ‹funnel› |
| 5 | `silent-failures-production-invoice-pipeline` | 2 | 1 | ‹pending› | ‹GSC› | ‹funnel› |
| 6 | `custom-jwt-claims-supabase-auth-hooks` | 1 | 1 | ‹pending› | ‹GSC› | ‹funnel› |
| 7 | `rag-in-production-over-regulations` | 1 | 1 | ‹pending› | ‹GSC› | ‹funnel› |
| 8 | `what-agentic-operators-actually-do` | 1 | 1 | ‹pending› | ‹GSC› | ‹funnel› |
| 9 | `agent-governance-and-safety-in-production` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 10 | `ai-10x-not-cheaper` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 11 | `ai-adoption-at-a-scale-up` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 12 | `ai-agent-observability` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 13 | `augment-never-replace-agentic-operators` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 14 | `build-vs-buy-your-ai-capability` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 15 | `building-a-senior-colleague-ai` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 16 | `expose-your-erp-as-mcp` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 17 | `five-layer-memory-for-an-ai-agent` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 18 | `how-to-evaluate-an-ai-consulting-partner` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 19 | `infra-failures-nobody-warns-you-about` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 20 | `is-ai-written-code-safe-to-ship` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 21 | `make-ai-coding-agents-reliable-in-production` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 22 | `measuring-ai-impact-in-production` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 23 | `orchestrating-ai-coding-agent-fleets` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 24 | `running-agent-fleets-in-production` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 25 | `the-copilot-operator-gap` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 26 | `what-agentic-dev-training-looks-like` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 27 | `what-ai-readiness-means-for-a-dev-team` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 28 | `why-ai-coding-agents-cost-so-much` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 29 | `why-ai-demos-die-before-production` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |
| 30 | `winning-over-developers-skeptical-of-ai` | 0 | 0 | ‹pending› | ‹GSC› | ‹funnel› |

## How to read / fill
- **Pageviews/Visitors** are live (Plausible). Rank by these once organic traffic arrives; the top few are where content/geo double down, the zero-traffic tail is rework-or-cut.
- **AI-cited?** — run `geo-citation-monitor.mjs` with the post→target-query map (geo-lead owns the wording); mark a post cited when its URL appears in an engine's citations.
- **GSC pos** — Google Search Console per-page avg position + impressions. Needs a Search
  Console API credential (OAuth service account) + a verified `tsukumo.ch` property —
  flagged to cmo. Once keyed, add a GSC pull here (Search Analytics API, dimension=page).
- **Sessions→lead** — per-landing-path conversion (entry_page=/blog/X → assessment_request).
  Needs a Plausible funnel (entry_page → goal); v2 once there's traffic to power it.
