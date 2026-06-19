# wrai.th — MCP/Go registry listings + per-registry submission checklists

**Status:** DRAFT / copy only. Nothing here is submitted live. A human runs each checklist.
**Owner:** launch-lead · **Reviewed against:** wraith-kit.md, mcp-registries.md (trovex template), voice, synergix-wraith-url-exception
**Repo:** github.com/Synergix-lab/WRAI.TH (PUBLIC, v1.0.0 stable) · **Discord:** discord.gg/QPq7qfbEk8

> **Why this exists / how it relates to the trovex pack:** mcp-registries.md is the trovex (Python/PyPI)
> playbook. wrai.th is a **Go binary** and is **already public + v1.0 stable**, so (a) the publish mechanics
> differ (no PyPI; GitHub Releases + Go ecosystem instead) and (b) per the coordinated-launch plan
> (unfreeze-checklist §0) wrai.th registries are the **"can go FIRST" reversible/compounding** bucket — they
> are NOT gated on the trovex public flip or the tsukumo build. This is the run-checklist layer for
> wraith-kit.md §2 (which has the channels + master copy but not the step-by-step a human follows).

---

## 0. Order + the leverage (do in this sequence)

Registries are wrai.th's app-store shelf — MCP early adopters who already run coding agents browse here. As
with trovex, the **Official MCP Registry is the keystone**: submit once → auto-propagates to PulseMCP
(weekly), Docker Hub, the GitHub MCP Registry (renders in VS Code's Extensions view), and Anthropic-named
consumers. wrai.th *also* has Go-ecosystem shelves trovex doesn't.

**Submit order:**
1. **GitHub Release** with prebuilt binaries + honest release notes (the artifact every other shelf points at).
2. **Official MCP Registry** (`server.json` + `mcp-publisher`) → auto-propagates free to PulseMCP / VS Code / Docker.
3. **pkg.go.dev** (automatic on a clean tagged release — just verify it resolves).
4. **Glama** (web form; build validation; now gates the awesome-mcp-servers PR).
5. **awesome-mcp-servers** (GitHub PR; requires a Glama listing first).
6. **mcp.so** (web form + GitHub login).
7. **awesome-go** (strict criteria PR — only if it qualifies) + other awesome lists.
8. **Smithery** — feasible for wrai.th (it runs as a server with an API key) but only with a **brand-neutral**
   hosted endpoint; see §8.
9. Secondary directories (batch, same master copy).

### Blockers / dependencies (flagged — eng/owner, not launch-lead's to ship)
- [ ] **[VERIFY] Does `server.json` exist at the WRAI.TH repo root?** The Official Registry needs it. Draft in §2.
- [ ] **[VERIFY — the key Go decision] What package type does wrai.th publish as on the Official Registry?**
      The registry's first-class `registry_type`s are npm / pypi / nuget / oci / mcpb — none is "a bare Go
      binary." Two honest paths, eng picks one (don't ship a `server.json` that doesn't resolve):
      - **(a) Remote server** — wrai.th runs as an HTTP MCP server with an API key, so list it as a `remotes`
        entry pointing at a **brand-neutral** hosted endpoint (NOT a Synergix-branded host). Best if a hosted
        wrai.th is desired.
      - **(b) Packaged binary** — publish the binary as an **OCI image** or an **mcpb bundle** wrapping the
        GitHub-release binary, and reference that in `packages`. Best to keep it local-first/self-hosted.
      Confirm which the registry currently accepts for a Go tool before publishing.
- [ ] **[VERIFY] Exact reverse-DNS server name.** Repo is `WRAI.TH` (has a dot). Confirm the registry accepts
      `io.github.Synergix-lab/wrai.th` (or wants the literal repo case `io.github.Synergix-lab/WRAI.TH`).
      The name MUST match the GitHub namespace the OIDC login verifies. Don't guess — check a published Go
      example in the registry.
- [ ] **[VERIFY] `mcp-publisher` OIDC publish** must be run by someone with rights on the `Synergix-lab` org
      (same constraint as trovex PR #52). Interactive device-code won't run headless.

---

## 1. Canonical listing copy (master — reuse, trim per registry)

Lowercase wordmark `wrai.th`. No superlatives. Brand prose never names the company (Synergix appears ONLY in
the unavoidable repo URL / reverse-DNS identifier — synergix-wraith-url-exception). Real facts only — v1.0 IS
stable, so "stable" is honest; no fabricated stars/users/testimonials.

**Name:** `wrai.th`
**Reverse-DNS name (Official Registry):** `io.github.Synergix-lab/wrai.th`  *(technical identifier only — [VERIFY] dot/case)*

**Tagline (≤60 chars):**
> Mission control for your AI agents — memory, messaging, tasks.

**Short description (≤100 chars — Official Registry hard limit):**
> Local Go binary: a fleet of AI agents with shared memory, messaging, and tasks over MCP.

> *(counted ≤100 — re-count after any edit; the registry hard-caps it.)*

**One-paragraph description (directories that allow prose):**
> Running one coding agent is easy; running several falls apart — they don't share memory, they re-derive what
> another already figured out, they step on each other, and you have no single view of who did what. wrai.th is
> a local control plane for a fleet of agents: persistent cross-session memory (survives `/clear`),
> inter-agent messaging, a shared task board (claim / start / complete), and one dashboard — all over MCP, so
> any client (Claude Code, Cursor, Windsurf) plugs in. One binary, one SQLite file, 58 MCP tools, zero config,
> 100% local by default (no cloud, no telemetry). An optional API key turns it into a shared team server.

**Tags / categories:** `mcp`, `mcp-server`, `ai-agents`, `orchestration`, `multi-agent`, `developer-tools`,
`go`, `golang`, `sqlite`, `claude-code`, `cursor`, `local-first`, `agent-memory`

**Install (local — the default):**
```bash
curl -fsSL https://raw.githubusercontent.com/Synergix-lab/WRAI.TH/main/install.sh | bash
# binary = agent-relay · relay on localhost:8090 · dashboard at /v2/
# (or build from source: Go 1.25+ with CGO)
```

**MCP client config (stdio) — what a user pastes into their agent:**
```json
{
  "mcpServers": {
    "wrai-th": {
      "command": "agent-relay",
      "args": ["<the real MCP/stdio invocation>"]
    }
  }
}
```
> ⚠️ [VERIFY with eng] the exact `agent-relay` MCP/stdio invocation + whether the dashboard server must be
> running. Do not ship a config that doesn't run. (wrai.th's primary mode is the localhost:8090 relay; confirm
> the client-connect story before any listing that shows config.)

**Repo:** https://github.com/Synergix-lab/WRAI.TH · **License:** AGPL-3.0
**Stack:** Go, SQLite (FTS5), MCP protocol · **Shipped:** v1.0.0 stable, API stable, 58 MCP tools.

**Proof line (real facts only):** v1.0 stable, one binary, 58 MCP tools, local-first/no-telemetry. No
customers/testimonials — pre-launch, don't invent any.

**Screenshot / asset list (capture from the running app or hand to design):**
1. The `/v2/` dashboard showing a fleet of agents + the shared task board.
2. Two agents exchanging a message / claiming tasks (the coordination model in action).
3. Terminal: `install.sh` finishing → relay up on localhost:8090.
4. Persistent memory surviving a `/clear` (the cross-session memory story).
5. Square icon / logo (lowercase `wrai.th` wordmark) for registry thumbnails.

---

## 2. Official MCP Registry — `registry.modelcontextprotocol.io`

**Why first (after the GitHub Release):** keystone. Feeds PulseMCP, Docker Hub, GitHub MCP Registry (VS Code),
Anthropic. Do it once, correctly.

**`server.json` (DRAFT — eng confirms the package type per §0 [VERIFY] before publishing):**
```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.Synergix-lab/wrai.th",
  "description": "Local Go binary: a fleet of AI agents with shared memory, messaging, and tasks over MCP.",
  "repository": {
    "url": "https://github.com/Synergix-lab/WRAI.TH",
    "source": "github"
  },
  "version": "1.0.0",
  "packages": [
    {
      "_comment": "[VERIFY §0] pick ONE real path: oci image, mcpb bundle, or move to a top-level 'remotes' entry for the hosted HTTP server. A bare Go binary is not a first-class package type.",
      "registry_type": "oci",
      "identifier": "<ghcr.io/synergix-lab/wrai-th OR the chosen artifact>",
      "version": "1.0.0",
      "transport": { "type": "stdio" }
    }
  ]
}
```
> `description` ≤100 chars (re-count after edits). `name` must be reverse-DNS matching the GitHub namespace
> the OIDC login verifies — resolve the [VERIFY] dot/case point first.

**Submission checklist (human runs):**
- [ ] Resolve the §0 package-type decision (a/b) + the exact server name. [BLOCKER]
- [ ] Add `server.json` to the WRAI.TH repo root; `version` matches the release tag.
- [ ] Install the publisher CLI `mcp-publisher` (per official docs).
- [ ] Authenticate: `mcp-publisher login github-oidc` (verifies ownership of `io.github.Synergix-lab/*`).
      Must be run by someone with rights on the org.
- [ ] Ensure the referenced artifact (OCI image / mcpb / GitHub release binary) actually exists + is pullable.
- [ ] `mcp-publisher publish` from the repo root.
- [ ] Verify the listing resolves at registry.modelcontextprotocol.io and the REST API returns it.
- [ ] (Recommended) Wire a GitHub Action with `id-token: write` (OIDC) to auto-publish on each tagged release,
      so the listing never goes stale (mirror trovex PR #52's pattern in the WRAI.TH repo).
- **Gotchas:** name MUST be reverse-DNS matching the GitHub namespace; description hard cap 100 chars;
  metadata-only (no code uploaded — the artifact lives on GHCR / GitHub Releases). Propagation to PulseMCP
  takes up to a week.

---

## 3. GitHub Release (do this FIRST — it's what every shelf points at)

**Why:** pkg.go.dev, awesome lists, and the installer's prebuilt-binary fallback all reference a tagged
release. Release notes are a marketing surface.

**Checklist (human/eng):**
- [ ] Tag a clean `v1.0.0` (or current) release; CI builds prebuilt binaries for the target platforms.
- [ ] Confirm `install.sh`'s prebuilt-binary fallback pulls from this release.
- [ ] Release notes: honest changelog, the one-line install, the 58-tools / local-first facts. No hype, no
      fabricated metrics. Lowercase `wrai.th`; no "Synergix" in the prose.
- **Gotcha:** a broken/missing release breaks every downstream shelf — verify the binary runs from a clean
  download before announcing anywhere.

---

## 4. pkg.go.dev — `pkg.go.dev`

**Why:** free Go-ecosystem shelf trovex can't have. Automatic — no form.

**Checklist (human):**
- [ ] Confirm the Go module path is clean + public (matches the repo).
- [ ] After a tagged release, request/confirm the page resolves at `pkg.go.dev/github.com/Synergix-lab/WRAI.TH`
      (visiting/fetching the module triggers indexing).
- [ ] Ensure the package doc comment / README renders usefully (it's the page's body).
- **Gotcha:** pkg.go.dev indexes the *module*, not "the product" — it's a credibility/discovery signal for the
  Go audience, not a primary install surface. Keep expectations right.

---

## 5. Glama — `glama.ai/mcp`

**Why:** large MCP directory, and a Glama listing now gates the awesome-mcp-servers PR. Do before awesome-mcp.

**Checklist (human):**
- [ ] Sign in at glama.ai with GitHub.
- [ ] Submit `https://github.com/Synergix-lab/WRAI.TH` via the add-server form.
- [ ] Ensure the repo builds/runs cleanly — Glama runs build validation. [VERIFY the Go build passes their check]
- [ ] Fill tagline, description, tags from §1.
- [ ] Once listed, grab the Glama badge (needed for the awesome-mcp PR) and add it to the README.
- **Gotcha:** if the build/validation check fails, the listing won't verify — confirm the cold-clone build
  first (Go 1.25+ / CGO requirement may trip their validator; check what they support).

---

## 6. awesome-mcp-servers — GitHub PR to `punkpeye/awesome-mcp-servers`

**Why:** high-visibility list, but a known bottleneck and now requires a Glama listing first.

**Entry copy (markdown list line — match their CURRENT legend + format exactly):**
```markdown
- [wrai.th](https://github.com/Synergix-lab/WRAI.TH) 🏎️ 🏠 - Local control plane for a fleet of AI agents: shared memory, inter-agent messaging, and a task board over MCP. One Go binary, 58 tools, local-first.
```
> 🏎️ = Go, 🏠 = local/self-hosted — **confirm the current legend in their README before submitting**; the
> emoji keys + categories change.

**Checklist (human):**
- [ ] Confirm the Glama listing exists (prerequisite).
- [ ] Read CONTRIBUTING + the category list; pick the right section (likely "Orchestration" / "Multi-Agent" /
      "Developer Tools" — match what's there).
- [ ] Fork, add ONE alphabetically-placed line in the correct category, match emoji legend + format exactly.
- [ ] Open a focused PR (one server, no unrelated changes); follow their PR template.
- [ ] Be patient — long maintainer queue; do not bump/spam.

---

## 7. mcp.so — `mcp.so`

**Why:** large human-browsable directory.

**Checklist (human):**
- [ ] Sign in at mcp.so with GitHub.
- [ ] Submit `https://github.com/Synergix-lab/WRAI.TH` via the submit form.
- [ ] Fill name, tagline, description, tags from §1; attach screenshots (§1 asset list).
- [ ] Confirm the README renders correctly in their preview.

---

## 8. awesome-go + other awesome lists — GitHub PRs

**Why:** Go-audience credibility ("one Go binary, SQLite FTS5, zero config" is a Go story).

**Targets:** awesome-go (STRICT criteria — only if it qualifies), awesome-mcp, awesome-ai-agents,
awesome-devtools.

**Checklist (human, per list):**
- [ ] Read each list's contribution criteria FIRST — awesome-go in particular rejects projects that don't meet
      its bar (tests, docs, stability, age). Don't PR if it won't qualify; a rejected PR is wasted goodwill.
- [ ] Match the list's exact line format + category.
- [ ] One focused PR per list; follow each template.
- **Gotcha:** awesome-go has automated checks (CI, coverage, golint). Confirm the repo passes before PRing.

---

## 9. Smithery — `smithery.ai`  (CONDITIONAL — needs a brand-neutral remote endpoint)

**Why more feasible than for trovex:** wrai.th runs as a server with an API key, so a hosted HTTP MCP endpoint
is a natural fit (Smithery expects hosted HTTP).

**Pre-req before listing:**
- [ ] Stand up / confirm a **brand-neutral** hosted MCP endpoint — NEVER a Synergix-branded host. [BLOCKER]
- [ ] Confirm a hosted multi-tenant wrai.th is actually desired (local-first is a core differentiator — listing
      a hosted version is a product call for cmo/eng, not a copy call).

**Checklist (human — only once the above is resolved):**
- [ ] Sign in at smithery.ai with GitHub.
- [ ] Add the server with the brand-neutral HTTP endpoint URL.
- [ ] Provide config schema / connection details; run their technical validation.
- [ ] Use master copy (§1), tags from §1.

---

## 10. Secondary directories (batch — same master copy, low effort)

| Directory | Submit method | Notes |
|---|---|---|
| mcpservers.org | web form / GitHub | general MCP list |
| Cline / Continue / Cursor MCP directories | per-client docs | high intent — these users run coding agents |
| Docker MCP Catalog (Hub) | auto from Official | confirm propagation, no separate submit |
| awesome-ai-agents / awesome-devtools | GitHub PR | see §8 |

**Checklist (human):**
- [ ] For each: confirm it's not already auto-fed by the Official Registry (avoid dupes).
- [ ] Submit master copy + repo URL + tags.
- [ ] Track each submission in a simple sheet (registry, URL, date submitted, live y/n).

---

## 11. Voice / brand QA (applies to every listing above)

- [ ] Lowercase `wrai.th` everywhere in prose.
- [ ] No banned words: revolutionary, seamless, supercharge, unlock, "AI-powered".
- [ ] No superlatives (fastest/first/best). "v1.0 stable" is allowed because it's true.
- [ ] Real facts only; **no fabricated stars, testimonials, or user counts** (pre-launch).
- [ ] **No "Synergix" in any brand prose** — only the unavoidable GitHub repo URL / reverse-DNS identifier
      (synergix-wraith-url-exception).
- [ ] No consulting pitch in listings (registries are not a sales surface; the tsukumo line stays a low-key
      README footnote, and only once tsukumo.ch is live).
- [ ] Every install line actually runs — verify with eng before any human submits.

---

## 12. Handoff summary (for the human who fires these)

1. **Eng first:** cut the GitHub Release with prebuilt binaries; resolve the §0 [VERIFY] points (package type,
   server name, stdio invocation); add `server.json`; (optionally) confirm a brand-neutral hosted endpoint.
2. **Then submit in order:** GitHub Release → Official Registry → (PulseMCP auto) → pkg.go.dev → Glama →
   awesome-mcp PR → mcp.so → awesome-go (if it qualifies) → secondary.
3. **Smithery only** after a brand-neutral hosted endpoint exists + a hosted-wrai.th decision is made.
4. These can fire **ahead of the tsukumo gate** (reversible/compounding — unfreeze-checklist §0); re-publish the
   Official Registry on each new release tag.

*All copy above is a draft. Nothing has been submitted.*
