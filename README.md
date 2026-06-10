# ctx

Token-efficient routing for agent-generated `.md` docs.

Agents (Claude Code, etc.) burn thousands of tokens reading `.md` files trying
to figure out which one is canonical. `ctx` indexes a repo's markdown corpus,
exposes a single MCP tool `ctx(q)` that returns minimal pointers (path:line +
freshness marker), and lets agents read only the relevant file.

**Target**: -60% tokens spent on `.md` reads, same context quality.

## MCP tools

- `ctx(q)` — route to the right on-disk `.md` (returns pointers; the v0.8 router).
- `ctx_write(content, kind?, doc_id?)` / `ctx_read(query|doc_id)` — **v0.9**: docs
  owned *inside* ctx. Store records / memory / coordination and read them back as
  content, so every agent (and a second dev) shares one source of truth instead of
  re-deriving. First slice of the doc-centralization refonte — see `REFONTE.md`.

## Stack

- Python 3.11 + uv
- FastAPI (MCP HTTP + SSR HTML UI)
- fastembed (local embeddings, ONNX under the hood)
- sqlite-vec (vector search in SQLite)
- Jinja2 + HTMX (UI, no build step)

## Quick start (dev)

```bash
uv sync
uv run ctx index /path/to/repo
uv run ctx serve  # MCP at /mcp, UI at /
```

## Production

Deployed at `ctx.prod.synergix.ch` via Traefik. See `docker/` for the image.
