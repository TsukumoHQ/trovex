# trovex

Token-efficient routing for agent-generated `.md` docs.

Agents (Claude Code, etc.) burn thousands of tokens reading `.md` files trying
to figure out which one is canonical. `trovex` indexes a repo's markdown corpus,
exposes a single MCP tool `trovex(q)` that returns minimal pointers (path:line +
freshness marker), and lets agents read only the relevant file.

**Target**: -60% tokens spent on `.md` reads, same context quality.

## MCP tools

- `trovex(q)` — route to the right on-disk `.md` (returns pointers; the v0.8 router).
- `trovex_write(content, kind?, doc_id?)` / `trovex_read(query|doc_id, section?)` — **v0.9+**:
  docs owned *inside* trovex. Store records / memory / coordination and read them back as
  content (optionally just one section), so every agent (and a second dev) shares one
  source of truth instead of re-deriving. See `REFONTE.md`.

Humans read trovex-owned docs at `/doc/{id}` (rendered reader). To make agents route
`.md` writes through `trovex_write` instead of the disk, install the PreToolUse hook
`deploy/hooks/trovex-md-guard.sh` (carve out exceptions in `.trovexignore`).

## Stack

- Python 3.11 + uv
- FastAPI (MCP HTTP + SSR HTML UI)
- fastembed (local embeddings, ONNX under the hood)
- sqlite-vec (vector search in SQLite)
- Jinja2 + HTMX (UI, no build step)

## Quick start (dev)

```bash
uv sync
uv run trovex index /path/to/repo
uv run trovex serve  # MCP at /mcp, UI at /
```

## Production

Deployed at `trovex.prod.synergix.ch` via Traefik. See `docker/` for the image.

## License

Trovex is licensed under the **GNU AGPL-3.0-or-later** (see [`LICENSE`](LICENSE)).
You can self-host and modify it freely; if you run a modified version as a network
service, AGPL requires you to share your changes.

## Working with a team?

trovex is free to run yourself. If your team is rolling out coding agents at scale —
and wants hands-on help doing it well, or to embed/host a modified trovex privately
without the AGPL's copyleft obligations — that's what the consulting is for.
[Reach out](https://github.com/Synergix-lab/trovex).
<!-- TODO(human): replace the link above with the real consulting contact (private email / booking / form). -->

