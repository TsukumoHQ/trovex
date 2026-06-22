# wrai.th — MCP registry listing kit + per-registry submission checklists

**Status:** DRAFT. Nothing here is submitted live. A human runs each checklist and fires each submit.
**Owner:** launch-lead · **Reviewed against:** the wraith store packages (doc `44706328`), listings+checklists (`6d88ba01`), `wraith-registry-decided`, the `voice` memory, anti-ai-slop pass.
**Separate from trovex.** wrai.th is a different product (multi-agent coordination relay), never merged into the trovex registry kit (`growth/launch/mcp-registry-kit.md`). Different listing, different positioning.
**Verified against repo (2026-06-22):** `github.com/TsukumoHQ/WRAI.TH` (public). Latest release **v1.3.0** (2026-06-19) ships 4 platform binaries + `install.sh`/`install.ps1` + `SHA256SUMS`. Binary name: `agent-relay`.

Scope: this is the registry/directory play for wrai.th — listings only. It is independent of the trovex registry play and of the Show HN / Product Hunt one-shots.

---

## 0. Why registries first, the locked package decision, and the one real blocker

MCP registries are wrai.th's shelf. The people most likely to install are devs already running multiple coding agents who browse for orchestration/MCP servers — that's where they look. Listings compound and they're reversible, so they're safe to seed before the noisier one-shots.

The keystone is the official registry: publish once and it propagates to PulseMCP, the GitHub MCP Registry (which renders in VS Code's `@mcp` view), the Docker MCP Catalog, mcpdirectory.app, and mcpservers.org. One submit, several shelves.

### The locked package decision (owner + cmo, 2026-06-22 — memory `wraith-registry-decided`)

- **Registry name:** `io.github.tsukumohq/wraith` (lowercase, no dot — schema-valid; namespace OIDC-verified via the org).
- **Display name:** `wrai.th` · **Binary:** `agent-relay`.
- **Package:** `mcpb` bundle — **not** OCI/GHCR. Owner killed the Docker dependency; it contradicts the one-binary, local-first model. The `.mcpb` wraps the per-platform GitHub-release binary + a manifest.
- **Transport:** `stdio` — registry norm, and the local-stdio model the `.mcpb` expects.

### The blocker a human or eng has to clear before the official registry

The binary is **HTTP-only today** (`agent-relay serve` → `:8090/mcp`). The `.mcpb` + the registry both need a **stdio** entrypoint, and there is no `.mcpb` asset on the release yet.

**Verified 2026-06-22:**
- [ ] **WRAI.TH PR #70 — `agent-relay mcp` stdio transport — is OPEN, not merged.** This adds the stdio mode the bundle's manifest runs. **[BLOCKER]** → cmo/owner GH-approve + merge. → eng.
- [ ] **No `.mcpb` bundle on the v1.3.0 release.** After #70, eng builds the universal `.mcpb` and attaches it to a tagged GitHub Release (must be downloadable), then fills the bundle URL + `file_sha256` in `server.json`. **[BLOCKER]** → eng.

Until both are true, the official-registry `server.json` in §2.1 is a draft you cannot publish. **Every other registry on the list accepts a plain GitHub repo URL + the binary install line and can go ahead now** (see fire-now below).

### Fire-now vs blocked-on-stdio

| Registry / surface | Status | Why |
|---|---|---|
| Official MCP Registry | **BLOCKED on #70 + `.mcpb`** | needs stdio entrypoint + a downloadable `.mcpb` |
| PulseMCP, VS Code `@mcp` gallery, Docker MCP Catalog, mcpdirectory.app | **BLOCKED (downstream)** | they auto-ingest from the official registry; nothing to submit until it's live |
| Glama | **FIRE-NOW** (README gate) | takes the repo URL; build-validates a cold clone; renders README |
| mcp.so | **FIRE-NOW** (README gate) | takes the repo URL; renders README |
| awesome-mcp-servers (PR) | **FIRE-NOW after Glama** | needs the Glama listing first |
| pkg.go.dev | **ALREADY AUTO** | populates from the tagged module; confirm it resolves |
| GitHub Release / awesome-go / awesome-ai-agents / awesome-devtools | **FIRE-NOW** | plain repo/release |
| MCPMarket.com | **FIRE-NOW** | ~10k-server human-browsable directory; plain repo + web submit |
| Smithery | **DEFERRED** | expects hosted HTTP; wrai.th is local `.mcpb`/stdio |

> **Soft gate on the README-rendering registries (Glama, mcp.so):** they render the repo README, so the README must be **launch-clean** first — scrub `Synergix-lab` → `TsukumoHQ` (fire-sequence doc `844bb5b8` STEP 0) or the verified listing shows the deprecated org. Open thread, owner/eng.

### Submit order (most reach first)

1. **ENG:** merge PR #70 (stdio) → build the `.mcpb` → attach to a tagged Release → add `server.json` at repo root.
2. **Official MCP Registry** — once #70 + `.mcpb` are done. Feeds PulseMCP / VS Code `@mcp` / Docker / mcpdirectory for free.
3. **Glama** — after the README is launch-clean; a Glama listing gates the awesome-mcp PR.
4. **mcp.so**.
5. **awesome-mcp-servers** — GitHub PR; needs the Glama listing first.
6. **Go ecosystem** — pkg.go.dev (auto on tag), GitHub Release, awesome-go (only if it qualifies).
7. **Other awesome-\*** — awesome-ai-agents, awesome-devtools (batch pass, same copy).

---

## 1. Canonical listing copy (the master block — reuse, then trim per registry)

Lowercase `wrai.th` in all prose. No superlatives. Brand prose never names the company; the only place the org identifier appears is the unavoidable GitHub URL and the reverse-DNS name in `server.json`.

**Display name:** `wrai.th` · **Binary:** `agent-relay`

**Reverse-DNS name (official registry only):** `io.github.tsukumohq/wraith`
*(a technical identifier the registry requires, not brand copy.)*

**Tagline (≤60 chars):**
> Mission control for your AI agents — memory, messaging, tasks.

*(56 chars.)*

**Short description (≤100 chars — official registry hard cap):**
> Local Go binary giving a fleet of AI agents persistent memory, messaging, and tasks over MCP.

*(93 chars.)*

**One-liner (≤160 chars — most directories):**
> wrai.th is a local Go binary that gives a fleet of AI agents shared memory, inter-agent messaging, and a task board over MCP — one binary, one SQLite file.

**Short description (~50 words — directories with a summary field):**
> Running one AI coding agent is easy; running several is where it breaks — no shared memory, no way to talk, no view of the work. wrai.th is a local Go binary (one binary, one SQLite file, zero required config) that gives a fleet of agents cross-session memory, messaging, and a shared task board over MCP.

**Long description (~150 words — directories that take prose):**
> Running one AI coding agent is easy. Running several is where it breaks: no shared memory between them, no way for them to talk, no single view of the work.
>
> wrai.th is a local Go binary — one binary, one SQLite file, zero required config — that gives a fleet of agents three things over MCP: persistent cross-session memory, inter-agent messaging, and a shared task board, all watched from one dashboard. Any MCP client plugs in (Claude Code, Cursor, Windsurf).
>
> It's 100% local by default — no cloud, no telemetry. An optional API key turns the same binary into a shared team server when more than one person needs in. Stable release, AGPL-3.0.

**Install (the one line — matches the repo):**
```bash
curl -fsSL https://raw.githubusercontent.com/TsukumoHQ/WRAI.TH/main/install.sh | bash
# Windows: iwr -useb https://raw.githubusercontent.com/TsukumoHQ/WRAI.TH/main/install.ps1 | iex
```
*Or grab a prebuilt binary from the GitHub Releases page (darwin/linux amd64+arm64, windows amd64).*

**MCP client config — what a user pastes into their agent.**
> **HTTP (today):** after `agent-relay serve` (defaults to `:8090/mcp`):
> ```json
> {
>   "mcpServers": {
>     "agent-relay": {
>       "transport": "http",
>       "url": "http://localhost:8090/mcp"
>     }
>   }
> }
> ```
> For Claude Code: `claude mcp add --transport http agent-relay http://localhost:8090/mcp`.
> **stdio (after PR #70 lands):** the `.mcpb` install wires `agent-relay mcp` over stdio automatically; VS Code's `@mcp` gallery writes the `.vscode/mcp.json` block for you. **[ENG: confirm the exact stdio command + the `claude mcp add` stdio form once #70 ships.]**

**Per-client quick-install (ship all three — adoption happens inside the client; a discoverer who can't paste a working config in <60s bounces):**
- **Claude Code:** `claude mcp add` (CLI) or Customize → point at the local relay (`http://localhost:8090/mcp`; stdio form after #70).
- **Cursor:** Settings → Tools & Integrations → New MCP Server → name `agent-relay`, the http URL (or stdio command post-#70).
- **VS Code:** `@mcp` in the Extensions gallery (auto-populates from the official registry once published) → writes `.vscode/mcp.json`; or hand-add the same block.

**MCP capability summary (for registries that list what it does):**
- Persistent **memory** — cross-session, shared across the fleet.
- Inter-agent **messaging** — agents talk instead of re-deriving each other's state.
- A shared **task board** — dispatch, claim, complete; one view of the work.
- One local **dashboard** to watch the colony.

**Category / tags:** `mcp`, `ai-agents`, `orchestration`, `multi-agent`, `developer-tools`, `go`, `golang`, `sqlite`, `claude-code`, `cursor`, `local-first`, `agent-memory`

**Transport:** HTTP today (`:8090/mcp` after `agent-relay serve`); stdio after PR #70. Local-first; no hosted endpoint listed.

**Links (raw — tagged versions in §3):**
- Repo: `https://github.com/TsukumoHQ/WRAI.TH`
- Homepage: `https://wrai.th` *(**VERIFY** it resolves to a real landing before pasting; if not, use the repo URL as the homepage field.)*
- Releases: `https://github.com/TsukumoHQ/WRAI.TH/releases`

**License:** AGPL-3.0 per the store doc — but `gh` reads no SPDX license on the repo. **VERIFY** the `LICENSE` file is a standard AGPL-3.0 text GitHub can detect before stating it in a listing.

**Proof line (the real facts only):** stable release (v1.3.0), API stable, local-first, one binary. Public, AGPL. No fabricated stars, users, or testimonials.

**Assets to capture (hand to design — brand violet `#6e6bf2`, client-safe, no client names):**
1. Square `wrai.th` logo for registry thumbnails.
2. Dashboard screenshot — the colony view (agents, memory, tasks).
3. A `register → coordinate → dashboard` diagram.
4. A short ≤30s capture: a demo colony of agents sharing memory + claiming tasks.

---

## 2. Per-registry checklists

### 2.1 Official MCP Registry — `registry.modelcontextprotocol.io`  **[BLOCKED on #70 + `.mcpb`]**

**Why first:** keystone. Feeds PulseMCP, the GitHub MCP Registry (VS Code `@mcp`), the Docker MCP Catalog, mcpdirectory.app, mcpservers.org.

**Method:** add a `server.json` at repo root, then publish with `mcp-publisher` using GitHub OIDC (the `io.github.tsukumohq/*` namespace verifies ownership via the org).

**`server.json` draft (eng fills the bundle identifier + `file_sha256` + version on build):**
```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.tsukumohq/wraith",
  "description": "Local Go binary giving a fleet of AI agents persistent memory, messaging, and tasks over MCP.",
  "repository": { "url": "https://github.com/TsukumoHQ/WRAI.TH", "source": "github" },
  "version": "1.3.0",
  "packages": [
    {
      "registry_type": "mcpb",
      "identifier": "<URL to the .mcpb bundle — e.g. https://github.com/TsukumoHQ/WRAI.TH/releases/download/v1.3.0/wraith.mcpb>",
      "version": "1.3.0",
      "file_sha256": "<sha256 of the .mcpb>",
      "transport": { "type": "stdio" }
    }
  ]
}
```
> `description` is 93 chars (under the 100 cap). `version` set to the latest release tag (v1.3.0 — bump to the real release at publish time). mcpb `identifier` = the bundle download URL; `file_sha256` = its checksum. The bundle's manifest runs `agent-relay mcp` over stdio. **VERIFY** the exact stdio invocation runs before publishing — ship nothing that doesn't run.

**Checklist (human + eng):**
- [ ] **[BLOCKER]** Merge PR #70 (`agent-relay mcp` stdio mode). — cmo/owner approve, eng.
- [ ] **[BLOCKER]** Build the universal `.mcpb`; attach to a tagged GitHub Release (downloadable). — eng.
- [ ] Add `server.json` at repo root; fill identifier + `file_sha256`; set `version` to the release tag.
- [ ] Install `mcp-publisher` per the official docs.
- [ ] `mcp-publisher login github` / OIDC (someone with rights on the `TsukumoHQ` org).
- [ ] `mcp-publisher publish` from repo root (or the CI/OIDC path).
- [ ] Confirm it resolves at `registry.modelcontextprotocol.io`, the REST API returns it, and it appears in VS Code `@mcp` within ~1 week.
- [ ] Optional: a tagged-release Action with `id-token: write` so the listing never goes stale.

**Gotchas:** name must be reverse-DNS matching the GitHub namespace; description capped at 100 chars; metadata-only (the bundle lives on GitHub Releases); downstream propagation can take up to a week.

---

### 2.2 PulseMCP / VS Code `@mcp` / Docker MCP Catalog / mcpdirectory.app  **[BLOCKED — downstream]**

**Method:** none — they auto-ingest from the official registry. Nothing to submit until 2.1 is live.

**Checklist (human):**
- [ ] After the official listing is live, wait up to a week; confirm wrai.th appears in each.
- [ ] If PulseMCP is missing after a week, use its submit/correct form with the §1 copy (don't submit early — you'll create a duplicate).

---

### 2.3 Glama — `glama.ai/mcp`  **[FIRE-NOW — README gate]**

**Why:** broad automated coverage and a Glama listing gates the awesome-mcp PR, so do it before §2.5.

**Method:** web form, GitHub sign-in. Glama runs a build check, so the repo has to build from a cold clone (Go 1.25+ + CGO).

**Checklist (human):**
- [ ] **PRE-REQ:** README is launch-clean — scrub `Synergix-lab` → `TsukumoHQ` first (fire-sequence `844bb5b8` STEP 0). Glama renders the README; a deprecated org shows otherwise.
- [ ] Sign in at `glama.ai` with GitHub.
- [ ] Submit `https://github.com/TsukumoHQ/WRAI.TH` via the add-server form.
- [ ] Confirm a fresh clone builds/runs (the install path succeeds) — Glama validates.
- [ ] Fill tagline, description, tags from §1; include the per-client quick-install block.
- [ ] Once listed, grab the Glama badge (needed for the awesome-mcp PR) and, if cmo agrees, add it to the README.

**Gotcha:** build-check fail = no verified listing; fix the cold-build/install path first.

---

### 2.4 mcp.so — `mcp.so`  **[FIRE-NOW — README gate]**

**Method:** the "Submit" button in the nav, or their GitHub issues, with name, description, features, and connection info.

**Checklist (human):**
- [ ] README launch-clean (same as 2.3).
- [ ] Sign in at `mcp.so` (GitHub); submit `https://github.com/TsukumoHQ/WRAI.TH` via Submit or the GitHub issue.
- [ ] Fill name, tagline, short description, tags from §1; attach the §1 assets + the per-client quick-install block.
- [ ] Confirm the README renders correctly in their preview.

---

### 2.5 awesome-mcp-servers — GitHub PR to `punkpeye/awesome-mcp-servers`  **[FIRE-NOW after Glama]**

**Why:** very high visibility, but a slow maintainer queue, and it wants a Glama listing first.

**Entry line (confirm the current legend in their README before submitting — categories and emoji keys drift):**
```markdown
- [wrai.th](https://github.com/TsukumoHQ/WRAI.TH) 🏎️ 🏠 - Local Go binary: persistent memory, inter-agent messaging, and a shared task board for a fleet of AI agents over MCP. One binary, one SQLite file.
```
> 🏎️ = Go, 🏠 = local/self-hosted — **VERIFY** against their current legend.

**Checklist (human):**
- [ ] Confirm the Glama listing exists (prerequisite).
- [ ] Read CONTRIBUTING and the category list; pick the right section (likely "Orchestration", a developer-tools bucket, or "Knowledge & Memory" — match what's there).
- [ ] Fork, add one alphabetically-placed line in the correct category, match the legend and format.
- [ ] Open a focused PR (one server, no unrelated changes) and follow their PR template.
- [ ] Don't bump or chase the maintainer; the queue is long.

---

### 2.6 Go ecosystem — pkg.go.dev + GitHub Release + awesome-go  **[FIRE-NOW]**

| Surface | Method | Notes |
|---|---|---|
| pkg.go.dev | automatic on a tagged release | confirm the module path is clean + the page resolves at `pkg.go.dev/github.com/TsukumoHQ/WRAI.TH` — **VERIFY** |
| GitHub Release | already cut (v1.3.0) | when `.mcpb` is built, attach it as a release asset; keep release notes honest, no hype |
| awesome-go | strict criteria, GitHub PR | only submit if wrai.th qualifies; match their format exactly |

**Checklist (human):**
- [ ] Confirm pkg.go.dev resolves the module (it auto-populates from the v1.3.0 tag).
- [ ] When the `.mcpb` exists, attach it to the GitHub Release.
- [ ] Assess awesome-go criteria before submitting; skip if it doesn't qualify.

---

### 2.7 Other awesome lists — awesome-ai-agents, awesome-devtools  **[FIRE-NOW, batch]**

Same §1 copy + repo URL. One human pass after the top surfaces land.

**Checklist (human):**
- [ ] For each list, read CONTRIBUTING; place wrai.th in the right category, alphabetical, matching format.
- [ ] One focused PR per list; same one-liner from §1.
- [ ] Log each (list, URL, date, live y/n).

---

### 2.8 MCPMarket.com — `mcpmarket.com`  **[FIRE-NOW]**

Large human-browsable directory (~10k servers, 23+ categories). Takes a plain repo URL + the §1 copy.

**Checklist (human):**
- [ ] Submit `https://github.com/TsukumoHQ/WRAI.TH` via the site's submit path — **VERIFY** the exact form/path.
- [ ] Fill name, tagline, short description, tags from §1; pick the right category (orchestration / multi-agent / developer-tools).
- [ ] Log it (date, URL, live y/n).

---

### 2.9 Smithery — `smithery.ai`  **[DEFERRED]**

Smithery expects a hosted HTTP endpoint; wrai.th's package is local `.mcpb`/stdio with no hosted endpoint. Revisit only if a hosted, multi-tenant wrai.th (brand-neutral endpoint) becomes a cmo/eng decision.

---

## 3. UTM scheme — tagged outbound links

Every outbound homepage link in a listing carries UTMs so registry-referred sessions show up in analytics. Pattern:

```
?utm_source=<registry-slug>&utm_medium=mcp-registry&utm_campaign=launch
```

Use these tagged URLs in each listing's homepage field. The repo link stays a plain GitHub URL (GitHub strips query params). **Homepage host = `wrai.th` — VERIFY it resolves; if not, use the repo URL as the homepage and skip the UTM (the repo referral still shows as a plain referrer).**

| Registry | utm_source slug | Homepage link to paste |
|---|---|---|
| Official MCP Registry | `mcp-registry-official` | `https://wrai.th/?utm_source=mcp-registry-official&utm_medium=mcp-registry&utm_campaign=launch` |
| PulseMCP | `pulsemcp` | `https://wrai.th/?utm_source=pulsemcp&utm_medium=mcp-registry&utm_campaign=launch` |
| Glama | `glama` | `https://wrai.th/?utm_source=glama&utm_medium=mcp-registry&utm_campaign=launch` |
| mcp.so | `mcp-so` | `https://wrai.th/?utm_source=mcp-so&utm_medium=mcp-registry&utm_campaign=launch` |
| awesome-mcp-servers | `awesome-mcp` | `https://wrai.th/?utm_source=awesome-mcp&utm_medium=mcp-registry&utm_campaign=launch` |
| Docker MCP Catalog | `docker-mcp` | `https://wrai.th/?utm_source=docker-mcp&utm_medium=mcp-registry&utm_campaign=launch` |
| awesome-ai-agents | `awesome-ai-agents` | `https://wrai.th/?utm_source=awesome-ai-agents&utm_medium=mcp-registry&utm_campaign=launch` |
| awesome-devtools | `awesome-devtools` | `https://wrai.th/?utm_source=awesome-devtools&utm_medium=mcp-registry&utm_campaign=launch` |

Note: some registries auto-fill the homepage from repo metadata and strip query strings — that's expected; the repo-referral still shows as a plain referrer.

---

## 4. Voice and honesty QA (applies to every listing above)

- [ ] Lowercase `wrai.th` everywhere in prose.
- [ ] No banned words: revolutionary, seamless, supercharge, unlock, "AI-powered", and no superlatives (fastest/first/best). "stable" is an honest fact, not a superlative.
- [ ] Real facts only — stable v1.3.0, local-first, one binary. No fabricated logos, testimonials, user counts, or star counts.
- [ ] No company name in brand prose. The only org identifier is the GitHub URL and the reverse-DNS `server.json` name.
- [ ] No `Synergix` anywhere — README launch-clean (`844bb5b8` STEP 0) before the README-rendering registries.
- [ ] No consulting CTA in registry listings. Registries are not a sales surface.
- [ ] Assets are brand violet `#6e6bf2`, client-safe (no client names).
- [ ] Every install line, `agent-relay mcp`, the cold build, and each per-client config actually run — eng confirms before any human submits.
- [ ] wrai.th and trovex listings stay strictly separate — never cross-reference or merge.

---

## 5. Handoff summary (for the human who fires these)

1. **Eng first (clears the two blockers):** merge PR #70 (stdio) → build the `.mcpb` → attach to a tagged Release → add `server.json` at repo root. Then scrub the README (`844bb5b8` STEP 0).
2. **Then submit in order:** Official → (PulseMCP / VS Code / Docker auto) → Glama → mcp.so → awesome-mcp PR (needs Glama) → Go ecosystem → other awesome lists.
3. **Fire-now without waiting on eng:** Glama + mcp.so (after README scrub), then the awesome-mcp PR + pkg.go.dev + the other awesome lists.
4. **Track every submission** (registry, URL, date, live y/n) and hand the sheet to analytics-lead.
5. **Re-publish the official registry** on each new release tag so listings don't go stale.

### Things flagged VERIFY
- **PR #70 status** — OPEN as of 2026-06-22; recheck before treating the official registry as unblocked (§0).
- **`.mcpb` asset** — not on the v1.3.0 release yet; eng builds it (§0, §2.1).
- **License** — store says AGPL-3.0 but `gh` detects no SPDX license on the repo; confirm the `LICENSE` file (§1).
- **Homepage** — does `wrai.th` resolve to a real landing? If not, use the repo URL in homepage fields (§1, §3).
- **pkg.go.dev** — confirm the module page resolves (§2.6).
- The current emoji legend and category list in `punkpeye/awesome-mcp-servers` (§2.5).
- The exact stdio invocation `mcp-publisher` / the `.mcpb` manifest runs (§2.1).

*All copy and checklists above are drafts. Nothing has been submitted to any registry.*
