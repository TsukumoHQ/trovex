# wrai.th — launch kit (DRAFT, do not fire)

**Status:** DRAFT / copy only. A human submits/posts. Nothing fired live.
**Owner:** launch-lead · **Reviewed against:** mission, ecosystem, voice, no-synergix-mention, copy-gate, domain-research
**Repo:** github.com/Synergix-lab/WRAI.TH (PUBLIC, v1.0.0 stable) · **Discord:** discord.gg/QPq7qfbEk8

> Why this is P1: per `mission`, wrai.th is the biggest top-of-funnel of the OSS suite (public + v1.0
> stable). It drives devs → discover the suite (trovex, yoru) → the Tsukumo agency consulting lead. This
> adapts the trovex launch kit to wrai.th's real, shipped facts.
>
> Brand: lowercase wordmark `wrai.th`. No company name in prose (no-synergix-mention; Synergix-lab is the
> GitHub org only, Tsukumo is the agency — neither is named in launch copy). Real facts only — v1.0 is
> stable so "stable" is honest; install is real; Discord is real. No fabricated stars/users/testimonials.

---

## 0. Real product facts (grounding — pulled from the live README, don't drift)

- **What:** "mission control for your AI agents" — run a *fleet* of agents that persist memory, talk to
  each other, and ship tasks, watched from one dashboard.
- **Shipped:** v1.0.0 **stable**, API stable. One binary, one SQLite file, **58 MCP tools**, zero required config.
- **Local:** 100% local by default, no cloud, no telemetry. Optional API key turns it into a shared team server.
- **Stack:** Go, SQLite (FTS5), MCP protocol, AGPL-3.0.
- **Install:** `curl -fsSL https://raw.githubusercontent.com/Synergix-lab/WRAI.TH/main/install.sh | bash`
  (or build from source: Go 1.25+ + CGO). Binary = `agent-relay`; relay on localhost:8090; dashboard at `/v2/`.
- **Core capabilities:** persistent cross-session memory (survives `/clear`), token-aware context budgeting,
  inter-agent messaging (5 addressing modes, P0–P3 priority, TTL), nested tasks (3 levels, roll-up, optional
  Linear mirror), scoped conflict-aware memory + FTS5 + RAG `query_context`, profile archetypes, server-side
  notification rules.
- **Clients:** any MCP client — Claude Code, Cursor, Windsurf.

---

## 1. Show HN

HN rules (domain-research): no superlatives, link the repo, founder answers substantively, NO booster comments.

**Title (pick one):**
1. **`Show HN: wrai.th – mission control for a fleet of AI coding agents (Go, MCP)`** *(recommended)*
2. `Show HN: wrai.th – give your AI agents persistent memory and a way to talk (one Go binary)`
3. `Show HN: wrai.th – run multiple coding agents that remember and coordinate, locally`

**Submission link:** the repo (github.com/Synergix-lab/WRAI.TH). It's public + v1.0, so it stands on its own.

**Founder first comment (HN-admin structure, honest, technical):**
```
Hi HN — I build tools for teams running AI coding agents, and wrai.th is the orchestration piece.

One sentence: it's a local Go binary that gives a fleet of AI agents persistent memory, inter-agent
messaging, and a shared task board, with a dashboard to watch them — all over MCP.

The problem: agents have no memory across sessions, no way to talk to each other, and no shared view of
the work. Every session starts from zero and every agent works alone. Once you're running more than one
agent (or coming back the next day), that hurts.

How it works:
- One binary, one SQLite file (FTS5), 58 MCP tools, zero required config. Any MCP client plugs in
  (Claude Code, Cursor, Windsurf).
- Memory persists across /clear and restarts; get_session_context restores an agent's full state in one
  call, with token-aware budget pruning (priority × relevance × freshness) so it fits the window.
- Messaging: 5 addressing modes (direct/broadcast/team/conversation/user), P0–P3 priority, TTL, delivery
  tracking. Nested tasks up to 3 levels with roll-up; optional Linear mirror.
- 100% local by default, no cloud, no telemetry. Flip on an API key and the same binary becomes a shared
  team server.

It's v1.0 and stable — I run my own multi-agent projects on it. AGPL-3.0. Install is one curl line (or
build from source, Go 1.25+ + CGO for SQLite FTS5).

I'd like feedback on the coordination model — addressing modes, the task hierarchy, where the context
budgeting picks the wrong thing to keep. Repo: https://github.com/Synergix-lab/WRAI.TH · Discord in the README.
```
> Same anti-vote-ring rule as trovex: founder answers questions, no friends posting booster comments.

**Likely-question answers (reuse + wrai.th-specific):**
- *"Isn't this just LangGraph / CrewAI / an agent framework?"* → Those are frameworks you write agents in.
  wrai.th is infrastructure underneath any MCP client — it doesn't replace your agent, it gives whatever
  agent you already run (Claude Code, Cursor) memory + messaging + a task board. You don't rewrite anything.
- *"Why a binary instead of a Python lib?"* → One binary, one SQLite file, zero config, runs anywhere, no
  env to manage. It's the thing that's always on while your agents come and go.
- *"Local — does anything leave my machine?"* → No. 100% local default, no telemetry. The API key is opt-in
  for sharing a server across a team.
- *"How does this relate to trovex / yoru?"* → They're the same idea at different layers: wrai.th orchestrates
  the fleet, trovex gives them one canonical doc store (context), yoru shows what they did (observability).
  Use wrai.th alone or together. (See suite-positioning.md.)

---

## 2. Registries / directories

wrai.th is an MCP server (the `agent-relay` server) — same shelf as trovex. Two channels:

**MCP registries** (per mcp-registries.md mechanics + public-launch-kit-deep.md target list):
- Official MCP Registry — `server.json`, name `io.github.Synergix-lab/wrai.th` (reverse-DNS = GitHub org,
  technical identifier only, not brand prose). Auto-feeds PulseMCP / Docker / GitHub MCP Registry / Anthropic.
- Glama, awesome-mcp-servers (PR), mcp.so, client directories (Cline/Continue/Cursor).
- Smithery: wrai.th can run as a server with an API key, so a hosted HTTP endpoint is more feasible here than
  for trovex — but only list a brand-neutral host, never a Synergix-branded one.

**Go ecosystem** (wrai.th is also a Go binary — extra shelves trovex doesn't have):
- pkg.go.dev (automatic on a tagged release; confirm the module path is clean).
- Awesome lists: awesome-go (strict criteria — only if it qualifies), awesome-mcp, awesome-ai-agents,
  awesome-devtools. PR per list, match format.
- A GitHub Release with prebuilt binaries (the installer already falls back to prebuilt) — release notes
  are marketing surface; keep them honest + changelog-linked.

**Submission copy (master):**
- Tagline (≤60): `Mission control for your AI agents — memory, messaging, tasks.` (one option)
- ≤100-char desc: `Local Go binary giving a fleet of AI agents persistent memory, messaging, and tasks over MCP.`
- Tags: `mcp`, `ai-agents`, `orchestration`, `developer-tools`, `go`, `golang`, `sqlite`, `multi-agent`,
  `claude-code`, `cursor`, `local-first`, `agent-memory`.

---

## 3. Community seeding

Same value-first rules as community-plan.md (contribute >> promote, read venue rules, no copy-paste). wrai.th
has an existing Discord — that's the home base, not a cold start.

| Venue | Angle |
|---|---|
| r/mcp | core fit — orchestration via MCP; author flair path |
| r/LocalLLaMA | local-first / no-telemetry / runs-on-your-machine angle (strict — read sidebar) |
| r/ChatGPTCoding, r/AI_Agents, r/LLMDevs | multi-agent coordination pain |
| MCP / Cline / Continue / Cursor Discords | #showcase once, then answer |
| Go communities (r/golang, Gophers Slack) | "one Go binary, SQLite FTS5, zero config" is a Go-audience story |
| own Discord (discord.gg/QPq7qfbEk8) | grow + support the existing community |

**r/mcp seed draft:**
```
Built wrai.th: a local Go binary that gives a fleet of AI agents persistent memory, inter-agent messaging,
and a shared task board — all over MCP, so any client (Claude Code/Cursor/Windsurf) plugs in. One binary,
one SQLite file, 58 MCP tools, zero config, 100% local. v1.0 stable. Repo + Discord:
github.com/Synergix-lab/WRAI.TH. Happy to talk the coordination model.
```

---

## 4. README-as-marketing (it's already strong — light notes)

The live README is already a good marketing surface (clear "Why", one-prompt setup, real screenshots, honest
v1.0 framing). Suggestions, not a rewrite:
- Keep the honest "stable, battle-tested on real projects" framing — don't inflate to enterprise claims.
- Add a one-line **suite cross-link** near the top: "pairs with trovex (context) and yoru (observability) —
  see the suite." (feeds the funnel; see suite-positioning.md.)
- A low-key consulting line at the bottom ("running agent fleets across a team? we do that — [Tsukumo]") once
  the agency site is live. Keep it a footnote, not a pitch. No company name until tsukumo.ch is live.
- Check that no "Synergix" appears as a vendor/brand in the prose (org/URL identifiers are fine).

---

## 5. Sequencing + guardrails

- wrai.th is **public + stable**, so unlike trovex it is NOT behind the private-beta hold. But this kit is
  still **drafts** — a human fires HN/PH/registry submits (per autonomy-rules, no live third-party posting).
- Order: registries (Official first) → Show HN (one-shot, weekday AM, founder free) → community seeding →
  Go-ecosystem shelves. Don't stack one-shots.
- No booster comments, no vote solicitation, no fabricated proof (it's v1.0 with real usage — say exactly
  that, nothing more). No "Synergix" in prose. Real facts from §0 only.
- Run anti-ai-slop on any copy before it's posted.

## 6. Handoffs

- cmo: confirm whether to fire wrai.th's public launch now (it's not gated like trovex) or hold for the agency
  site + suite story to land together. This kit is ready either way.
- design-lead: HN/PH/registry needs OG card + gallery assets for wrai.th (brand TBD — coordinate).
- social-lead: build-in-public + thread repurposing from this kit.
- Pairs with suite-positioning.md (how wrai.th + trovex + yoru fit).

*All copy above is a draft. Nothing has been submitted or posted.*
