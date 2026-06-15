# Quickstart

Point trovex at a repo and see the tokens it saves, in about a minute.

## What you need

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- An MCP-capable agent (Claude Code, Cursor, Windsurf, Zed, or any MCP client)

## 1. Index a repo

```bash
uv sync
uv run trovex index /path/to/your/repo
```

This reads the repo's markdown and builds a local index. Everything stays on your machine:
vectors in SQLite, embeddings via ONNX, no cloud and no API keys.

## 2. Start the server

```bash
uv run trovex serve   # MCP at /mcp, dashboard at /
```

## 3. Point your agent at it

Add the trovex MCP endpoint (`http://localhost:8765/mcp` by default) to your agent's MCP
config. In Claude Code:

```bash
claude mcp add trovex --transport http http://localhost:8765/mcp
```

For other clients, add an HTTP MCP server pointing at the same URL.

## 4. See the savings

Work a normal session. Your agent now asks trovex a question and gets back the one current
doc that answers it (a `path:line` pointer with a freshness marker) instead of rereading
several files to guess.

Open the dashboard at `http://localhost:8765/` and look at the **Savings** tab. It shows
would-have-read versus actual tokens on doc lookups. That number is your real reduction, on
your real docs. The first time it moves is the point of the whole thing.

## Optional: route agent writes through trovex

To make agents save what they learn (incidents, decisions, notes) into one shared store
instead of scattering `.md` files, install the PreToolUse hook:

```bash
deploy/hooks/trovex-md-guard.sh
```

Carve out exceptions in `.trovexignore`. After that, an agent writes once and every other
agent and teammate reads the same source of truth back.

## Next

- Didn't see much savings? That's a real answer too. See [the FAQ](./faq.md) on when trovex
  is and isn't worth running.
- Want to know where the ~60% comes from? Read [the token cost of agents rereading docs](../growth/blog/the-token-cost-of-agents-rereading-docs.md).
