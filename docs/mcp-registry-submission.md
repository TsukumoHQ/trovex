# Publishing trovex to the MCP Official Registry — DRAFT runbook

**Status: DRAFT. A human runs the live submission — this is not automated.**
The registry listing is the keystone: publish once to the Official MCP Registry
(`registry.modelcontextprotocol.io`) and it propagates to PulseMCP, the GitHub MCP
Registry (renders in VS Code), Docker's MCP catalog, and other downstream indexes.

The manifest itself — [`server.json`](../server.json) at the repo root — is written and
validated against the official `2025-12-11` schema. What's left is the human-run publish.

> These steps follow the MCP registry process as of 2026-06. The `mcp-publisher`
> requirements evolve — **cross-check the current docs** at
> <https://github.com/modelcontextprotocol/registry> before you run them.

## What's in `server.json`

| Field | Value |
|-------|-------|
| `name` | `io.github.tsukumohq/trovex` (GitHub-namespace; authenticated via GitHub OIDC as the repo owner) |
| `version` | `0.11.0` (matches `pyproject.toml`) |
| `packages[0]` | PyPI `trovex`, run with `uvx`, subcommand `serve` |
| `transport` | `streamable-http` at `http://localhost:8765/mcp` (trovex is a local HTTP MCP server, not stdio) |

## Prerequisites (do these first)

1. **Publish trovex to PyPI.** The manifest lists a PyPI package `trovex@0.11.0`, but
   it is **not on PyPI yet** (`pypi.org/pypi/trovex/json` → 404 as of 2026-06). The
   registry validates package ownership, so this must exist first.
   - Build + publish (the project already uses hatchling):
     ```bash
     uv build
     uv publish        # needs a PyPI token; or: python -m twine upload dist/*
     ```
   - **Ownership link:** the registry verifies you own the PyPI package by looking for
     the line `mcp-name: io.github.tsukumohq/trovex` in the package's README/long
     description. Add that line to the PyPI long description (or wherever the current
     `mcp-publisher` docs require) before publishing, or the publish step will fail
     validation.
2. **GitHub OIDC auth.** The `io.github.tsukumohq/*` namespace is owned by whoever
   can authenticate to the `TsukumoHQ` GitHub org/repo. Run the publish as that user
   (interactive `mcp-publisher login github`) or from a GitHub Action with the repo's
   OIDC token.

## Submission steps

```bash
# 1. Install the publisher CLI (check the repo for the current install method)
#    e.g. via Go, or a released binary from modelcontextprotocol/registry.
#    See: https://github.com/modelcontextprotocol/registry

# 2. From the trovex repo root (server.json already present):
mcp-publisher validate          # lint the manifest against the live schema
mcp-publisher login github      # GitHub OIDC for the io.github.tsukumohq namespace
mcp-publisher publish           # pushes server.json to the Official Registry
```

If `mcp-publisher init` is run instead of using the committed file, it would overwrite
`server.json` — **don't**; the committed manifest is already correct and validated.

## After publishing

- Confirm the listing at `https://registry.modelcontextprotocol.io` (search `trovex`).
- It should propagate to PulseMCP / GitHub MCP Registry within their refresh windows.
- On every release: bump `version` in both `pyproject.toml` and `server.json`, re-publish
  to PyPI, then re-run `mcp-publisher publish`.

## Coordination

- **Listing copy** (the public description shown in registries) is **launch-lead's** call.
  The `description` in `server.json` is a tight, developer-honest default (≤100 chars,
  uses the real ~60% number, no hype) — launch-lead can refine it before the human
  publishes; keep it within the registry's length limit and the brand voice.
- The PyPI publish + the live registry submit are **external actions** left for a human
  per the autonomy rules (no live submits from agents).
