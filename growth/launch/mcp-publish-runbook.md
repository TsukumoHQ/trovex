# MCP Official Registry — publish runbook + status

**Owner:** launch-lead · **Task:** PUBLISH to MCP Official Registry (P1, live) · **Branch:** growth/launch-mcp-publish
**Status (2026-06-16):** BLOCKED on two prerequisites below. server.json validates; tooling confirmed. Not published yet — not faking it.

---

## What I verified

- `server.json` is on `main`, name `io.github.synergix-lab/trovex`, version 0.11.0. It **passes**
  `mcp-publisher validate` against registry.modelcontextprotocol.io.
- `mcp-publisher` CLI works (installed from the official release).
- `gh` is authed as helios-code (SSH, OAuth token).

## Why I could not publish tonight (two hard blockers)

**1. The PyPI package does not exist.**
`server.json` declares a `pypi` package `trovex` v0.11.0, but `https://pypi.org/pypi/trovex/json` returns
**404**. Publishing now would list a `uvx trovex` install that fails for every user, and the registry can't
verify package ownership. The package must be published to PyPI first, and its README/long-description must
contain the ownership marker:
```
mcp-name: io.github.synergix-lab/trovex
```
Needs: eng + PyPI credentials (or PyPI Trusted Publishing, see the workflow). Also confirm the package
actually builds an installable wheel — today the README shows `uv run trovex` from source, not `pip install`.

**2. Auth can't be done headless under the github namespace.**
`mcp-publisher login` methods: `github` (interactive browser/device-code — can't complete headless),
`github-oidc` (GitHub Actions only), `dns`/`http` (prove a domain, but that would change the server name
away from `io.github.synergix-lab/...`). To keep the github-canonical name, publish must run either from CI
(OIDC) or via a human's interactive login.

## The unblock (this PR provides it)

`.github/workflows/publish-mcp.yml` — a tag-triggered, **non-interactive** publish path:
- Builds + publishes the package to PyPI via **Trusted Publishing** (no stored token).
- Authenticates to the MCP registry via **GitHub OIDC** (no interactive login).
- Runs `mcp-publisher publish ./server.json`.
- A human pushing tag `v0.11.0` is the go signal; this also makes every future release auto-publish.

### One-time setup a human with org rights must do
1. PyPI: create the `trovex` project (or configure Trusted Publishing) → Settings → Publishing → add a
   GitHub publisher: repo `Synergix-lab/trovex`, workflow `publish-mcp.yml`.
2. Add the `mcp-name: io.github.synergix-lab/trovex` marker to the package's README/long-description.
3. Confirm `python -m build` produces a working wheel and `uvx trovex serve` runs from it.
4. Keep `server.json` `version` == the tag.
5. Push the tag: `git tag v0.11.0 && git push origin v0.11.0`.

### Alternative (faster, manual, if a human is at a terminal tonight)
```
# eng publishes trovex to PyPI first (with the mcp-name marker), then:
mcp-publisher login github          # interactive — approve the device code as a Synergix-lab org owner
mcp-publisher publish ./server.json
```
Run the interactive login yourself in this session with:  `! /tmp/mcp-publisher login github`
(then I can run validate/publish), or hand it to eng.

## After it publishes — verify propagation
- Listing API: `https://registry.modelcontextprotocol.io/v0/servers?search=trovex`
- PulseMCP auto-ingests within ~a week (no separate submit).
- Then GitHub MCP Registry (VS Code Extensions view), Docker, Anthropic consumers pick it up.

*Nothing has been published. This branch ships the path; publishing waits on the two prerequisites.*
