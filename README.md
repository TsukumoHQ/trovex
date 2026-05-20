# ctx

Token-efficient routing for agent-generated `.md` docs.

Agents (Claude Code, etc.) burn thousands of tokens reading `.md` files trying
to figure out which one is canonical. `ctx` indexes a repo's markdown corpus,
exposes a single MCP tool `ctx(q)` that returns minimal pointers (path:line +
freshness marker), and lets agents read only the relevant file.

**Target**: -60% tokens spent on `.md` reads, same context quality.

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
