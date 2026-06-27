<p align="center">
  <img src="https://raw.githubusercontent.com/TsukumoHQ/trovex/main/growth/assets/brand/readme-hero.png" alt="trovex — one canonical doc for your coding agents, ~60% fewer tokens." width="100%">
</p>

<!-- mcp-name: io.github.TsukumoHQ/trovex -->

# trovex

**trovex — one canonical doc for your coding agents, ~60% fewer tokens.**

<p align="center">
  <a href="https://tsukumo.ch/discord?utm_source=github&utm_medium=readme&utm_campaign=discord&utm_content=trovex"><img src="https://img.shields.io/badge/Discord-Join%20the%20community-5865F2?logo=discord&logoColor=white" alt="Join the tsukumo community on Discord"></a>
</p>

Your coding agents (Claude Code, Cursor, Windsurf, Zed, any MCP client) reread the repo
every session to work out which `.md` is current, then answer from a guess. You pay for
that on every session, every agent, every teammate.

trovex indexes your repo's markdown and exposes one MCP tool. Your agent asks a question;
trovex returns the single current doc that answers it as a `path:line` pointer with a
freshness marker (canonical / stale / duplicate), and serves just the section that answers
instead of the whole file. Agents also write what they learn back through one shared point,
so every agent and teammate reads the same source of truth instead of re-deriving it.

About **60% fewer tokens** on doc lookups, measured at equal task-success on our own repo (it varies by yours). Runs locally: vectors in
SQLite, embeddings via ONNX, no cloud or API keys.

## What you're installing

A 30-second trust check, since the decision happens on the README, not the directory listing:

- **First-party, open source.** Built and run in production by [tsukumo](https://tsukumo.ch), the team behind it. AGPL-3.0-or-later.
- **Local-first, nothing leaves your machine.** Vectors in SQLite, embeddings via ONNX. No cloud, no API keys, no network call to answer a query.
- **Confined writes, no shell.** Six MCP tools: three read-only (`trovex`, `trovex_read`, `trovex_search`) and three that mutate only trovex's own doc store (`trovex_write`, `trovex_tag`, `trovex_delete`). No shell execution, no writes to your source files.
- **The ~60% is reproducible.** Measured at equal task-success on our own repo (median 69%, ~41–81% by repo, n=26, LLM-judged); `trovex search` prints the savings on yours. Full method at [trovex.dev/measure](https://trovex.dev/measure).

## Quick start

trovex is in public beta, on PyPI. No clone needed — `uv tool install` puts `trovex`
on your PATH:

```bash
uv tool install trovex   # one-time, no clone

trovex index /path/to/your/repo        # index your markdown (~1 min)
trovex search "how do we roll back a deploy?"   # ask — prints the tokens it saved
trovex serve                           # wire into your agent: MCP at /mcp, dashboard at /savings
```

Don't have `uv`? It's a one-line install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
(or `brew install uv`).

The `search` step is the fast way to see the point: it returns the one canonical doc and
prints how many tokens that saved versus reading the top few candidates. Once trovex is
wired into your agent over MCP, the same numbers accumulate on the savings dashboard at
`http://localhost:8765/savings`.

> Prefer not to install anything yet? `uvx trovex search "..."` runs a single command in a
> throwaway environment — no install.

## Wire it into your agent

trovex is an MCP server. Point your client at `http://localhost:8765/mcp` after `trovex serve`.
Per-client setup (Claude Code, Cursor, Windsurf, Cline, Zed, Roo) is at
[trovex.dev/for](https://trovex.dev/for/). For Claude Code:

```bash
claude mcp add --transport http trovex http://localhost:8765/mcp
```

For **Cursor**, one click (after `trovex serve`):
[**Add trovex to Cursor**](cursor://anysphere.cursor-deeplink/mcp/install?name=trovex&config=eyJ1cmwiOiJodHRwOi8vbG9jYWxob3N0Ojg3NjUvbWNwIn0=)

## How it works

trovex turns your repo's markdown into one queryable, canonical store, then serves each
agent the single current doc that answers a question — not a pile of candidates to rank.

```mermaid
flowchart LR
  A["Your repo<br/>.md files"] -->|trovex index| B["Chunk + parse"]
  B --> C["Embed locally<br/>ONNX · bge-small"]
  C --> D[("sqlite-vec<br/>vector store")]
  Q["Agent question"] -->|MCP| E["Route + rerank"]
  D --> E
  E --> F["One canonical doc<br/>path:line + freshness"]
  F --> G["Agent answers from<br/>the current doc"]
```

Four ideas do the work:

- **Canonical, not complete.** For each question there should be one doc that answers it.
  trovex marks every doc canonical / stale / duplicate, so retrieval can prefer the one
  that's still true — a stale doc is exactly as similar to a query as the current one, so
  similarity alone can't tell them apart.
- **Route, then serve the section.** A query returns a `path:line` pointer to the one doc
  and just the section that answers — not the whole file, and not the top-k pile your agent
  would otherwise read and rank itself. Closing that gap is where the tokens are saved.
- **Local by default.** Indexing, embeddings (ONNX, `bge-small-en-v1.5`) and vector search
  (sqlite-vec) all run on your machine. No cloud, no API key, no network call to answer a query.
- **A shared write-back path.** Agents store what they learn once (`trovex_write`) in
  trovex's own store; every other agent and teammate reads it back (`trovex_read`) instead
  of re-deriving it.

The read-and-write loop that keeps every agent on the same source of truth:

```mermaid
sequenceDiagram
  participant A as Agent
  participant T as trovex (MCP)
  participant S as Store (sqlite-vec)
  A->>T: trovex("how do we roll back a deploy?")
  T->>S: route + rerank candidates
  S-->>T: one canonical doc
  T-->>A: path:line + section + freshness
  A->>T: trovex_write("rollback runbook: …")
  T->>S: upsert (dedupes near-copies)
  Note over S: the next agent reads it back via trovex_read
```

## Prove it on your own repo

The ~60% is a claim you can run, not a number to take on faith. Two commands:

```bash
trovex bench /path/to/your/repo          # token-accounting model — instant, no LLM, no key
trovex bench /path/to/your/repo --eval   # full answer+judge A/B at equal task-success (needs OPENAI_API_KEY)
```

`bench` reports the distribution (median + spread), not a best case: the cost of reading the
one routed canonical doc versus the top-k candidates an unaided agent would read. `--eval`
goes further — both arms answer, an LLM judges, and a saving counts only when both answer
correctly. Full method and our own numbers are at [trovex.dev/measure](https://trovex.dev/measure).

Already running trovex through the md-guard hook? `trovex measure` compares your real `.md`
token consumption before and after, from the hook's baseline log.

## MCP tools

- `trovex(q)` — route a question to the right on-disk `.md` and get back `path:line` pointers
  with freshness markers, not a pile of files to rank.
- `trovex_write(content, kind?, doc_id?, tags?)` / `trovex_read(query | doc_id, section?)` —
  docs owned *inside* trovex. An agent stores a record (an incident, a decision, "what
  actually worked") once; every other agent and a second dev read it back as content
  (optionally just one section) instead of re-deriving it. See [`REFONTE.md`](REFONTE.md).
- `trovex_search(query, k?, tags?)` — passage-level retrieval across the store with tag
  filters, for when you want the top matching chunks rather than one canonical doc.
- `trovex_tag(...)` / `trovex_delete(...)` — tag or soft-delete a stored doc; delete is a
  recoverable archive, not a hard wipe. Both touch only the trovex store, never your files.

Humans read trovex-owned docs at `/doc/{id}` in the rendered reader. To make agents route
`.md` writes through `trovex_write` instead of the disk, install the PreToolUse hook
`deploy/hooks/trovex-md-guard.sh` and carve out exceptions in `.trovexignore`.

## How it compares

- vs `CLAUDE.md` / `AGENTS.md`: one static file that goes stale and can't route a question
  to the right doc, vs many docs kept canonical and served per query. [More](https://trovex.dev/vs/claude-md/).
- vs `repomix` / files-to-prompt: pack the whole repo into the window vs retrieve the one
  answer. [More](https://trovex.dev/vs/repomix/).
- vs a vector DB / plain RAG: a ranked pile of candidate chunks with no freshness signal vs
  one current doc with an explicit marker. [More](https://trovex.dev/vs/vector-db-rag/).

The reasoning behind the ~60% number is written up in
[the benchmark methodology](https://trovex.dev/measure).

## Stack

- Python 3.11 + uv
- FastAPI (MCP HTTP + server-rendered HTML UI)
- fastembed (local embeddings, ONNX under the hood)
- sqlite-vec (vector search in SQLite)
- Jinja2 + HTMX (UI, no build step)

## Public beta

trovex is in public beta. Install it, run it on your repo, and if it saves you tokens a
[GitHub star](https://github.com/TsukumoHQ/trovex) helps other devs find it. Issues and
PRs welcome.

Questions, or comparing notes with other people running agents? Join the community on Discord:
[tsukumo.ch/discord](https://tsukumo.ch/discord?utm_source=github&utm_medium=readme&utm_campaign=discord&utm_content=community).

## Security

trovex is **local-first and single-tenant**: it runs on your machine, indexes your docs, and
serves your agents. Mutations are gated behind the `X-TROVEX-Write-Token` header — and the
default is **fail-closed**: with no token configured, trovex auto-generates a per-instance
token on first run and persists it to `<data_dir>/.write_token` (chmod 600), so a
network-exposed instance does not accept anonymous writes. Set `TROVEX_WRITE_TOKEN` to share
one token across machines, or `TROVEX_ALLOW_UNAUTH_WRITES=1` to deliberately run with open
writes on a trusted localhost. The trust model, what's hardened, and how to report a
vulnerability are documented in [`SECURITY.md`](SECURITY.md).

## License

trovex is licensed under the **GNU AGPL-3.0-or-later** (see [`LICENSE`](LICENSE)). You can
self-host and modify it freely; if you run a modified version as a network service, AGPL
requires you to share your changes.

## Part of the suite

trovex is the **context** layer of a four-part open-source suite for running AI coding agents in production, built by [tsukumo](https://tsukumo.ch):

- **trovex** — context: serve agents the one canonical doc per query instead of rereading the repo (~60% fewer tokens per lookup; method at [trovex.dev/measure](https://trovex.dev/measure)).
- **[wrai.th](https://github.com/TsukumoHQ/WRAI.TH)** — orchestration: run and coordinate a fleet of agents.
- **[yoru](https://yoru.sh)** — observability: session receipts of what each agent actually did.
- **[dokan](https://github.com/TsukumoHQ/dokan)** — deterministic execution: run the agent's settled, repeatable work as scripts in clean containers, no model in the loop.

## Working with a team?

trovex is free to run yourself. If your team is rolling out coding agents at scale and wants
hands-on help doing it well, or to embed and host a modified trovex privately without the
AGPL's copyleft obligations, that's what the consulting is for.
[Reach out](https://tsukumo.ch/consulting/?utm_source=trovex&utm_medium=oss-suite&utm_campaign=consulting&utm_content=readme):
tsukumo, the team behind trovex.
