# trovex

**One source of truth for your coding agents' docs. Same answers, about 60% fewer tokens.**

Your coding agents (Claude Code, Cursor, Windsurf, Zed, any MCP client) reread the
repo every session to work out which `.md` is current, then answer from a guess. You
pay for that on every session, every agent, every teammate.

trovex indexes your repo's markdown and exposes one MCP tool. Your agent asks a
question; trovex returns the single current doc that answers it as a `path:line`
pointer with a freshness marker (canonical / stale / duplicate), and serves just the
section that answers instead of the whole file. Agents also write what they learn
back through one shared point, so every agent and teammate reads the same source of
truth instead of re-deriving it.

About **60% fewer tokens** on doc lookups, same context quality. Runs locally: vectors
in SQLite, embeddings via ONNX, no cloud or API keys.

## Private beta

trovex is in private beta. The repo is gated while we work with a small group of early
testers. [Request access at trovex.dev](https://trovex.dev) and we'll get you set up.
Early testers get hands-on onboarding and a direct say in the roadmap.

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

## Quick start (once you have access)

Once you're in the beta and have cloned the repo:

```bash
uv sync                                   # install trovex and its deps
uv run trovex index /path/to/repo         # index your repo's markdown (~1 min)
uv run trovex search "how do we deploy?"  # ask a question — prints the tokens saved
uv run trovex serve                       # wire into your agent: MCP at /mcp, dashboard at /savings
```

The `search` step is the fast way to see the point: it returns the one canonical
doc and prints how many tokens that saved versus reading the top few candidates.
Once it's wired into your agent over MCP, the same numbers accumulate on the
savings dashboard at `http://localhost:8765/savings`.

## Self-hosting

Run it behind your own reverse proxy. See `docker/` for a container image.

## License

trovex is licensed under the **GNU AGPL-3.0-or-later** (see [`LICENSE`](LICENSE)).
You can self-host and modify it freely; if you run a modified version as a network
service, AGPL requires you to share your changes.

## Working with a team?

trovex is free to run yourself. If your team is rolling out coding agents at scale —
and wants hands-on help doing it well, or to embed/host a modified trovex privately
without the AGPL's copyleft obligations — that's what the consulting is for.
[Reach out](https://github.com/Synergix-lab/trovex).
<!-- TODO(human): replace the link above with the real consulting contact (private email / booking / form). -->

