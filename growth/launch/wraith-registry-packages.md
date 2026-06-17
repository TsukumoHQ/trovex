# wrai.th — ready-to-submit registry packages (DRAFT)

**Status:** DRAFT / copy-complete packages. Nothing submitted. A human fires each; owner-gated.
**Owner:** launch-lead · **Reviewed against:** wraith-kit.md (§0 facts, §2 list), mcp-registries.md, directory-packages-top5.md, suite-positioning.md, voice, no-synergix-mention, autonomy-rules
**Repo:** github.com/Synergix-lab/WRAI.TH (PUBLIC, v1.0.0 stable)

> Upgrades `wraith-kit.md §2` (the registry *list*) into **paste-ready submission packages** — every field
> filled, format rules, gotchas, human steps — mirroring `directory-packages-top5.md` for trovex. wrai.th is
> the launchable lead (public v1.0), so these are **reversible/compounding** and can seed ahead of the one-shots
> (launch-day-runbook §1) once the owner fires them. wrai.th is the `agent-relay` MCP server **and** a Go binary,
> so it has two shelves trovex doesn't: MCP registries + the Go ecosystem.

---

## 0. Master copy (reuse across every listing — keep in sync with wraith-kit §2)

- **Name:** `wrai.th` · **Binary:** `agent-relay`
- **Tagline (≤60):** Mission control for your AI agents — memory, messaging, tasks. (56)
- **Short (≤100, Official Registry hard limit):** Local Go binary giving a fleet of AI agents persistent memory, messaging, and tasks over MCP. (99)
- **One-paragraph:**
  > Running one AI coding agent is easy; running several is where it breaks — no shared memory, no way to
  > talk, no view of the work. wrai.th is a local Go binary (one binary, one SQLite file, 58 MCP tools, zero
  > required config) that gives a fleet of agents persistent cross-session memory, inter-agent messaging, and
  > a shared task board, watched from one dashboard. Any MCP client plugs in (Claude Code, Cursor, Windsurf).
  > 100% local by default, no cloud, no telemetry; an optional API key turns it into a shared team server.
- **Tags:** `mcp`, `ai-agents`, `orchestration`, `multi-agent`, `developer-tools`, `go`, `golang`, `sqlite`, `claude-code`, `cursor`, `local-first`, `agent-memory`
- **Install:** `curl -fsSL https://raw.githubusercontent.com/Synergix-lab/WRAI.TH/main/install.sh | bash`
- **License:** AGPL-3.0 · **Repo:** github.com/Synergix-lab/WRAI.TH
- **Proof (real only):** v1.0.0 stable, API stable, 58 MCP tools, local-first. No fabricated stars/users/testimonials.
- **Assets (hand to design-lead — wrai.th brand TBD, coordinate):** square logo, dashboard screenshot, a `register → coordinate → dashboard` diagram, a short ≤30s screen capture of 2–3 agents sharing memory + claiming tasks.

> ⚠️ **Two naming gotchas to resolve before submitting (eng):**
> 1. **Reverse-DNS name** — `io.github.Synergix-lab/wrai.th` has a dot in the final segment; confirm the MCP
>    registry accepts it, else use `io.github.Synergix-lab/wraith` (or the exact repo slug). Must match the
>    namespace the OIDC login verifies.
> 2. **Package type** — wrai.th is a **Go binary**, not PyPI. The Official Registry needs a real package
>    coordinate (OCI image, an `mcpb` bundle, or a GitHub-release-based package), not a `pypi` block. Eng
>    confirms which transport/package the registry supports for a Go binary before publish.

---

## 1. Official MCP Registry — `registry.modelcontextprotocol.io` (keystone)

**Type:** `server.json` + `mcp-publisher` (OIDC) · **Cost:** free · **Why first:** auto-feeds PulseMCP / Docker / GitHub MCP Registry (VS Code) / Anthropic.

**`server.json` to add at repo root (DRAFT — eng confirms name + package per §0 gotchas):**
```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.Synergix-lab/wraith",
  "description": "Local Go binary giving a fleet of AI agents persistent memory, messaging, and tasks over MCP.",
  "repository": { "url": "https://github.com/Synergix-lab/WRAI.TH", "source": "github" },
  "version": "1.0.0",
  "packages": [
    {
      "registry_type": "oci",
      "identifier": "<ghcr.io/synergix-lab/wraith or the real OCI/mcpb coordinate — eng confirms>",
      "version": "1.0.0",
      "transport": { "type": "stdio" }
    }
  ]
}
```
> `description` ≤100 (counted: ok). The `packages` block is a placeholder — a Go binary isn't pypi; eng picks OCI / mcpb / github-release and the real identifier.

**Human steps:**
- [ ] Resolve the two §0 gotchas (name segment + Go package type) with eng.
- [ ] Add `server.json` at repo root; version = release tag.
- [ ] `mcp-publisher login github-oidc` (someone with rights on the Synergix-lab org).
- [ ] Tag the release; `mcp-publisher publish` (or the CI/OIDC path, per mcp-registries.md PR-#52 pattern).
- [ ] Verify it resolves at registry.modelcontextprotocol.io + the REST API returns it.
- [ ] (Recommended) wire a tagged-release Action with `id-token: write` so listings never go stale.

**Gotchas:** name must be reverse-DNS matching the GitHub namespace; description hard cap 100; metadata-only (binary lives in the package registry); PulseMCP propagation up to ~1 week.

---

## 2. Glama — `glama.ai/mcp`

**Type:** web form (build-validated) · **Cost:** free · **Note:** gates the awesome-mcp PR.

**Human steps:**
- [ ] Sign in with GitHub; submit `https://github.com/Synergix-lab/WRAI.TH`.
- [ ] Ensure a fresh clone builds/runs (Go 1.25+ + CGO) — Glama validates.
- [ ] Fill tagline/description/tags from §0.
- [ ] Grab the Glama badge → add to README (needed for awesome-mcp).
**Gotcha:** build-check fail = no verified listing; confirm the cold-build/install path first.

---

## 3. mcp.so — `mcp.so`

**Type:** web form + GitHub login · **Cost:** free.
**Human steps:**
- [ ] Sign in; submit the repo URL; fill name/tagline/description/tags (§0); attach §0 assets.
- [ ] Confirm the README renders in their preview.

---

## 4. awesome-mcp-servers — PR to `punkpeye/awesome-mcp-servers`

**Type:** GitHub PR · **Cost:** free · **Pre-req:** Glama listing first.

**Paste-ready line (verify legend in their README — keys change):**
```markdown
- [wrai.th](https://github.com/Synergix-lab/WRAI.TH) 🏎️ 🏠 - Local Go binary: persistent memory, inter-agent messaging, and a shared task board for a fleet of AI agents over MCP. 58 tools, one binary.
```
- 🏎️ = Go, 🏠 = local/self-hosted — **confirm the current legend keys.** Category: likely "Orchestration" / "Developer Tools" / "Knowledge & Memory" — match what's there; place alphabetically.
**Human steps:** confirm Glama listing → read CONTRIBUTING + category list → fork, add one alphabetical line in the right section, match format → focused PR (one server) → don't bump/spam.

---

## 5. Go ecosystem — pkg.go.dev + awesome lists + GitHub Release

**pkg.go.dev** — automatic on a tagged release.
- [ ] Confirm the module path in `go.mod` is clean + public; tag a release; verify the page renders (docs/README pull through).

**awesome-go** — PR, **strict criteria** (stable, tested, documented, non-trivial). Only submit if wrai.th qualifies.
- [ ] Check awesome-go CONTRIBUTING criteria honestly; if it qualifies, PR one line in the right category, match format. If borderline, skip — a rejected awesome-go PR is noise.

**Other awesome-* (PR each, match format):** awesome-mcp (covered §4), awesome-ai-agents, awesome-devtools.

**GitHub Release** — release notes are a marketing surface.
- [ ] Cut a release with prebuilt binaries (installer falls back to prebuilt); honest notes + changelog link; no hype.

---

## 6. Smithery — `smithery.ai` (CONDITIONAL)

wrai.th can run as a server with an API key, so a hosted HTTP endpoint is more feasible than for trovex.
- [ ] **Only list a brand-neutral host** (never a Synergix-branded one) — and only if a hosted wrai.th is a decision cmo/eng want (local-first is the default story). Else skip / stay local-stdio.

---

## 7. Fire order + tracking

1. **Official Registry** (after §0 gotchas resolved) → auto-feeds PulseMCP/Docker/VS Code.
2. **Glama** → grab badge.
3. **mcp.so** + **awesome-mcp PR** (needs Glama).
4. **Go ecosystem:** pkg.go.dev (auto on tag), GitHub Release, awesome-go (only if it qualifies).
5. **Smithery** only if a brand-neutral hosted endpoint + a hosted-wrai.th decision exist.
- [ ] Log each (registry, date, live y/n, URL); re-publish Official on each new tag.

## 8. Voice / brand QA
- [ ] lowercase `wrai.th`; **no "Synergix"/"Tsukumo" in prose** (GitHub-org / reverse-DNS identifier only).
- [ ] No banned words, no superlatives ("stable" is honest — v1.0.0 is stable); real facts only, no fabricated stars/users.
- [ ] No consulting CTA in registry listings (not a sales surface).
- [ ] Every install line + the cold build actually run (eng verifies before any human submits).

*All packages above are drafts. Nothing has been submitted.*
