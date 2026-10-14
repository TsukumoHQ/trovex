# Quickstart

Point trovex at a repo and see the tokens it saves, in about a minute.

This is the canonical quickstart. The landing (trovex.dev), the per-editor pages
(trovex.dev/for/) and the README use the same commands; the source of truth is
`web/src/quickstart.json`, and `npm run build` in `web/` fails if a page drifts from it.

## What you need

- [uv](https://docs.astral.sh/uv/) (it fetches a matching Python 3.11+ for you)
- An MCP-capable agent (Claude Code, Cursor, Windsurf, Zed, Cline, Roo, or any MCP client)

## 1. Install

```bash
uv tool install trovex
```

One-time, no clone. It puts `trovex` on your PATH.

## 2. Index a repo

```bash
trovex index /path/to/repo
```

This reads the repo's markdown and builds a local index. Everything stays on your machine:
vectors in SQLite, embeddings via ONNX, no cloud and no API keys. The first run downloads the
embedding model.

## 3. Ask it something

```bash
trovex search "how do we roll back a deploy?"
```

It returns the one canonical doc and prints how many tokens that saved versus reading the top
few candidates.

## 4. Start the server

```bash
trovex serve   # MCP at http://localhost:8765/mcp, dashboard at http://localhost:8765/
```

## 5. Point your agent at it

Add the trovex MCP endpoint (`http://localhost:8765/mcp`) to your agent's MCP config. In
Claude Code:

```bash
claude mcp add --transport http trovex http://localhost:8765/mcp
```

Or, on Claude Code only, `trovex setup` registers the same server and also installs the trovex
skill and Active-Memory hooks in one step (safe to re-run; restart Claude Code afterwards).

The exact config for Cursor, Windsurf, Zed, Cline and Roo is at
[trovex.dev/for](https://trovex.dev/for/).

## Try it without installing

```bash
uvx trovex index /path/to/repo
uvx trovex search "how do we roll back a deploy?"
```

Index first: on a fresh machine `uvx trovex search` alone has nothing to search and prints no
savings line.

## 6. See the savings

Work a normal session. Your agent now asks trovex a question and gets back the one current
doc that answers it (a `path:line` pointer with a freshness marker) instead of rereading
several files to guess.

Open the dashboard at `http://localhost:8765/savings`. It shows would-have-read versus actual
tokens on doc lookups. That number is your real reduction, on your real docs.

## Optional: route agent writes through trovex

To make agents save what they learn (incidents, decisions, notes) into one shared store
instead of scattering `.md` files, install the PreToolUse hook (from a clone of this repo):

```bash
deploy/hooks/trovex-md-guard.sh
```

Carve out exceptions in `.trovexignore`. After that, an agent writes once and every other
agent and teammate reads the same source of truth back.

## Next

- Want to know where the ~60% comes from? Read the method at
  [trovex.dev/measure](https://trovex.dev/measure/).
