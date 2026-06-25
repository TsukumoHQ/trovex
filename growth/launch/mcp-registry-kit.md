# trovex — MCP registry listing kit + per-registry submission checklists

**Status:** **Official MCP Registry = ✅ LIVE** (`io.github.TsukumoHQ/trovex` @ 0.11.2, published 2026-06-25; PyPI `trovex` 0.11.2 carries the matching `mcp-name` marker). The remaining web-form directories (§2.3–2.7) are still DRAFT/human-fire. Install is `uvx trovex` / `pip install trovex`.
**Owner:** launch-lead · **Reviewed against:** `.agents/product-marketing-context.md`, the `voice` memory, anti-ai-slop pass.

> **🔥 FIRE SEQUENCE (the human runs, in order, the moment PyPI is live):**
> 0. **FIRE GATE — ✅ GREEN:** PyPI `trovex` 0.11.2 live, `uvx trovex` resolves + runs.
> 1. **Official MCP Registry — ✅ DONE / LIVE (2026-06-25):** `io.github.TsukumoHQ/trovex` @ 0.11.2 resolves at `registry.modelcontextprotocol.io/v0/servers?search=trovex`. Published via the tag-triggered OIDC workflow (`publish-mcp.yml`), not the interactive CLI. Now auto-feeds PulseMCP (~1wk) / GitHub-MCP-Registry (VS Code) / Docker. CONTRACT for any re-publish: `server.json` `name` == the README `mcp-name:` marker, **byte-for-byte incl. case** (`io.github.TsukumoHQ/trovex`); a case mismatch 403s (cost us the 0.11.0→0.11.1→0.11.2 recovery).
> 2. **Glama** (§2.3) → **awesome-mcp-servers PR** (§2.4, needs the Glama badge) → **mcp.so** (§2.5).
> 3. **Fire-now directories** (§2.6): MCPMarket.com, mcp.directory (+ `/submit-skill`), mcpserverfinder — all now take the clean `uvx` install.
> 4. Verify each resolves; log each (registry, URL, date, live y/n). Then ping cmo.
> **Voice/brand:** lowercase `trovex`, no superlatives, no "Synergix", real ~60% number. Drafts→human-fires; nothing auto-submits.
**Verified against README:** repo `github.com/TsukumoHQ/trovex`, install `uvx trovex` / `pip install trovex` (PyPI `trovex` 0.11.0), landing `trovex.dev`. (2026-06-24 — flipped from git-install on PyPI publish)
**Supersedes:** the older `mcp-registries.md` that lived here before the trovex-store migration (#238). It used the old `Synergix-lab` repo and the old `git clone + uv run` install. Both are corrected here.

Scope: this is Play 1 — registry/directory listings only. The Show HN and Product Hunt one-shots are a separate play; do not fire them from this kit.

---

## 0. Why registries first, and the one real blocker

MCP registries are trovex's shelf. The people most likely to install are devs already running coding agents who browse for MCP servers, and that's where they look. Listings compound and they're reversible, so they're safe to fire before the noisier one-shots.

The one with the most reach is the official registry. Publish once and it propagates to PulseMCP, the GitHub MCP Registry (which renders in VS Code's MCP view), the Docker MCP Catalog, and other downstream consumers. One submit, several shelves.

Being listed is not the same as getting installs. The install signal is verified ownership, a versioned release, a one-line install that actually runs, and a number a reader can reproduce. trovex has the number (~60% fewer tokens per lookup) and the one-line install. The gap is below.

### The package blocker — CLEARED (PyPI)

The official registry hosts metadata, not code: your server points at a package in a registry it supports (PyPI, npm, NuGet, Docker/OCI, or MCPB). **trovex 0.11.0 is published to PyPI as `trovex`** — so the registry_type is **`pypi`**, identifier **`trovex`** (the §2.1 `server.json` is ready to publish). No MCPB / hosted-endpoint detour needed.

> **🔥 FIRE GATE — ✅ GREEN (2026-06-24):** PyPI returns 200, **trovex 0.11.0 is LIVE** (`name: trovex`, `requires_python >=3.11`), and `uvx trovex` resolves + runs from PyPI. The package blocker is cleared — the official-registry publish + every directory below is fireable now. (registry-presence-monitor `136` also flips trovex/pypi → LIVE on its daily run.)

### Submit order (most reach first)

1. Official MCP Registry — once the package blocker is cleared. Feeds PulseMCP / VS Code / Docker for free.
2. PulseMCP — auto-ingests from the official registry; only touch the form if it doesn't appear.
3. Glama — web form; a Glama listing gates the awesome-mcp PR, so do it before #4.
4. awesome-mcp-servers — GitHub PR; needs the Glama listing first.
5. mcp.so — submit form / GitHub issue.
6. mcpservers.org and the secondary directories — batch pass, same copy.
7. cursor.directory + the per-client directories — same copy, install-config focused.

---

## 1. Canonical listing copy (the master block — reuse, then trim per registry)

Lowercase `trovex` in all prose. No superlatives. Brand prose never names the company; the only place the org identifier appears is the unavoidable GitHub URL and the reverse-DNS name in `server.json`.

**Name:** `trovex`

**Reverse-DNS name (official registry only):** `io.github.TsukumoHQ/trovex`
*(a technical identifier the registry requires, not brand copy. Case MUST match the GitHub org login EXACTLY — `TsukumoHQ`, not lowercase. The github-OIDC grant is scoped to `io.github.TsukumoHQ/*`; a lowercase name 403s the publish. This matches the published root `server.json`. Lesson learned the hard way on the v0.11.1 → v0.11.2 recovery.)*

**Tagline (≤60 chars):**
> One canonical doc for your coding agents, ~60% fewer tokens.

*(58 chars. Variant if a registry strips the tilde or the comma reads oddly: `One canonical doc per query for your coding agents.` — 50 chars.)*

**Short description (≤100 chars — official registry hard cap):**
> Serves agents the one current doc for a query instead of a reread of your repo's markdown.

*(90 chars.)*

**One-liner (≤160 chars — most directories):**
> trovex indexes your repo's markdown and returns the single current doc that answers a query: a `path:line` pointer with a freshness marker, not a reread.

**Short description (~50 words — directories with a summary field):**
> Your coding agents reread the repo every session to guess which `.md` is current, then answer from a guess. trovex indexes the markdown and returns the one canonical doc for a query as a `path:line` pointer with a freshness marker. About 60% fewer tokens per lookup. Runs locally.

**Long description (~150 words — directories that take prose):**
> Your coding agents reread your repo's markdown every session to work out which file is current, then answer from a guess. You pay for that on every session, every agent, every teammate.
>
> trovex indexes the markdown and exposes one MCP tool. Your agent asks a question; trovex returns the single current doc that answers it as a `path:line` pointer with a freshness marker (canonical, stale, or duplicate), and serves just the section that answers instead of the whole file. Agents also write what they learn back through one shared point, so every agent and teammate reads the same source of truth instead of re-deriving it.
>
> About 60% fewer tokens on doc lookups, same context quality. Runs locally: vectors in SQLite, embeddings via ONNX, no cloud and no API keys. Public beta, AGPL-3.0.

**Install (PyPI — trovex is published, `trovex` on PyPI):**
```bash
uvx trovex index /path/to/your/repo    # run with no install (uvx), ~1 min
uvx trovex serve                        # MCP at /mcp, dashboard at /savings
```
*Prefer a persistent install? `pip install trovex` or `uv tool install trovex`, then `trovex index … && trovex serve`. No `uv`? `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`.*

**MCP client config — what a user pastes into their agent (HTTP, after `trovex serve`):**
```json
{
  "mcpServers": {
    "trovex": {
      "transport": "http",
      "url": "http://localhost:8765/mcp"
    }
  }
}
```
**Per-client quick-install (copy-paste — paste the same one server into each client's config):**
- **Claude Code (CLI):** `claude mcp add --transport http trovex http://localhost:8765/mcp` (after `trovex serve`). Stdio variant: `claude mcp add trovex -- uvx trovex serve --stdio` — **VERIFY the `--stdio` flag with eng** before publishing.
- **Cursor:** Settings → Tools & Integrations → New MCP Server → paste the `mcpServers` JSON above.
- **VS Code:** add to `.vscode/mcp.json` (the same `mcpServers` block); `@mcp` gallery auto-detects it.
- **Windsurf / Cline / Zed / Roo:** same `mcpServers` JSON in each client's MCP config.

Full per-client setup also lives at `trovex.dev/for/`.

**MCP tools exposed (6 — 3 read-only, 3 mutate; for registries that list tools):**
- `trovex(q)` — *(read)* route a question to the right on-disk `.md`; returns `path:line` pointers with freshness markers, not a pile of files to rank.
- `trovex_read(query | doc_id, section?)` — *(read)* read a trovex-owned doc back, optionally just one section.
- `trovex_search(query, k?, tags?)` — *(read)* passage-level retrieval across the store, for when you want top chunks rather than one canonical doc.
- `trovex_write(content, kind?, doc_id?, tags?)` — *(write)* store a record (an incident, a decision, what worked) inside trovex's own doc store.
- `trovex_tag(...)` — *(write)* tag/retag a stored doc.
- `trovex_delete(...)` — *(write)* soft-delete a stored doc.

**Tool-safety (the trust signal devs check):** writes are **confined to trovex's own doc store** — no shell-exec, and trovex never writes to your source files. Read-only by default; the 3 mutating tools only touch the trovex store.

**Category / tags:** `developer-tools`, `code`, `context`, `memory`, `rag`, `documentation`, `coding-agents`, `claude-code`, `cursor`, `local-first`, `python`

**Transport:** stdio (local) and HTTP (`/mcp` after `trovex serve`). Local-first; no hosted endpoint listed.

**Links (raw — tagged versions in §3):**
- Repo: `https://github.com/TsukumoHQ/trovex`
- Homepage: `https://trovex.dev`
- Per-client setup: `https://trovex.dev/for/`
- Savings dashboard: local at `http://localhost:8765/savings` after `trovex serve` (this is a local page, not a public URL — don't link it as if it were).

**License:** AGPL-3.0-or-later (CLIs MIT).

**Proof line (the real number only):** about 60% fewer tokens per doc lookup; the local dashboard shows would-have-read vs. actual. Public beta. No customers, testimonials, or star counts yet — don't invent any.

**Screenshots to capture (hand to design, or grab from the running app):**
1. Terminal: `trovex index` finishing with a one-line "indexed N docs".
2. The savings dashboard at `/savings` — would-have-read vs. actual, the ~60% line.
3. An agent calling `trovex(q)` and getting one `path:line` + freshness result.
4. The `/doc/{id}` rendered reader.
5. Square `trovex` wordmark for registry thumbnails.

---

## 2. Per-registry checklists

### 2.1 Official MCP Registry — `registry.modelcontextprotocol.io` — ✅ LIVE (2026-06-25)

**Status:** DONE. `io.github.TsukumoHQ/trovex` @ 0.11.2 is published and resolves. The steps below are the kept-for-the-record method + the re-publish runbook for each future release (the workflow `publish-mcp.yml` runs it on a version tag). **Why it was the keystone:** feeds PulseMCP, the GitHub MCP Registry (VS Code's MCP view), the Docker MCP Catalog — one publish, several shelves.

**Method:** add a `server.json` at repo root, then publish with the `mcp-publisher` CLI using GitHub auth (the `io.github.TsukumoHQ/*` namespace verifies ownership via the org).

**`server.json` — publish the canonical one at the repo root; do NOT hand-author a copy here.**
The validated manifest already lives at [`/server.json`](../../server.json) (schema `2025-12-11`) and the PR#52 workflow runs `mcp-publisher publish ./server.json` against it. Maintaining a second copy in this kit only invites drift, so this is a read-only summary of what's in the real file (validated 2026-06-25):

- `name`: `io.github.TsukumoHQ/trovex` (EXACT GitHub org-login case — the github-OIDC grant is `io.github.TsukumoHQ/*`; lowercase 403s).
- `repository.url`: `https://github.com/TsukumoHQ/trovex`.
- `version`: `0.11.0` (bump in `pyproject.toml` + `server.json` together each release).
- `packages[0]`: `registryType: pypi`, `identifier: trovex`, `version: 0.11.0`, `runtimeHint: uvx`, `transport: streamable-http` at `http://localhost:8765/mcp` (trovex runs `uvx trovex serve`, an HTTP MCP server, not stdio).
- `description`: the tight ~60% one-liner, under the 100-char registry cap.

> **PRE-PUBLISH GATE (the two ways the publish fails — both hit on the v0.11.1 attempt):** the github-oidc publish checks the PyPI package long-description (= README) for the ownership marker `mcp-name: io.github.TsukumoHQ/trovex`, and it must match `server.json` `name` **byte-for-byte, case included**. (1) trovex 0.11.0 carried no marker at all. (2) v0.11.1 carried a *lowercase* marker/name → the registry 403'd because the OIDC grant is scoped to the exact org case `io.github.TsukumoHQ/*`. Recovery each time = a new immutable PyPI version (0.11.0→0.11.1→0.11.2). So before tagging: marker in README == `server.json` `name` == `io.github.TsukumoHQ/trovex` (exact case), bump pyproject + server.json versions together, republish, then tag. → eng/CTO release lane.

**Checklist (human + eng) — fire after the §0 FIRE GATE (PyPI 200) is green:**
- [ ] **FIRE GATE:** `https://pypi.org/pypi/trovex/json` returns 200 + `uvx trovex --help` runs clean (§0).
- [ ] Add `server.json` to repo root; `version` = `0.11.0` (the release tag).
- [ ] Install `mcp-publisher` per the official docs.
- [ ] `mcp-publisher login github` (must be someone with rights on the `TsukumoHQ` org).
- [ ] Tag the release and push the tag.
- [ ] `mcp-publisher publish` from repo root.
- [ ] Confirm it resolves at `registry.modelcontextprotocol.io` and the REST API returns it.
- [ ] Optional: a GitHub Action with `id-token: write` to auto-publish on each tagged release so the listing never goes stale.

**Gotchas:** name must be reverse-DNS matching the GitHub namespace; description capped at 100 chars; the registry stores metadata only (no code upload); propagation downstream can take up to a week.

---

### 2.2 PulseMCP — `pulsemcp.com`

**Why:** hand-reviewed directory (~19k servers); curates a newsletter editors actually read.

**Method:** none for the listing itself — it auto-ingests from the official registry. There's a submit/correct form for gaps.

**Checklist (human):**
- [ ] After the official listing is live, wait up to a week; confirm trovex appears.
- [ ] If it's missing after a week, use the submit/correct form with the §1 copy.
- [ ] Once live with a working install and the savings number, a short value-first note to the editor is worth it (the token-cost angle, no hype). Draft that as separate outreach if cmo wants it — not part of this kit.

**Gotcha:** don't submit the form before giving the auto-ingest a week, or you risk a duplicate.

---

### 2.3 Glama — `glama.ai/mcp`

**Why:** broad automated coverage (~44k listings) and a Glama listing gates the awesome-mcp PR, so do it before #2.4.

**Method:** web form, GitHub sign-in. Glama runs a build check, so the repo has to build from a cold clone.

**Checklist (human):**
- [ ] Sign in at `glama.ai` with GitHub.
- [ ] Submit `https://github.com/TsukumoHQ/trovex` via the add-server form.
- [ ] Confirm a fresh install runs (`uvx trovex --help` / `pip install trovex`) — Glama validates.
- [ ] Fill tagline, description, tags from §1.
- [ ] Once listed, grab the Glama badge (needed for the awesome-mcp PR) and, if cmo agrees, add it to the README.

**Gotcha:** Glama favours servers with a real README and a working install over a raw git URL — the README already covers this, so point the listing at it. If the build check fails, the listing won't verify; fix the cold-clone path first.

---

### 2.4 awesome-mcp-servers — GitHub PR to `punkpeye/awesome-mcp-servers`

**Why:** very high visibility, but a slow maintainer queue, and it now wants a Glama listing first.

**Method:** GitHub PR. One server, one line, alphabetical within the right category, matching their emoji legend.

**Entry line (confirm the current legend in their README before submitting — categories and emoji keys drift):**
```markdown
- [trovex](https://github.com/TsukumoHQ/trovex) 🐍 🏠 - Returns the one canonical doc per query (path:line + freshness marker) instead of a ranked pile of chunks. ~60% fewer tokens per lookup. Local, AGPL.
```
> 🐍 = Python, 🏠 = local/self-hosted — **VERIFY** against their current legend.

**Checklist (human):**
- [ ] Confirm the Glama listing exists (prerequisite).
- [ ] Read CONTRIBUTING and the category list; pick the right section (likely "Knowledge & Memory" or a developer-tools bucket — match what's there).
- [ ] Fork, add one alphabetically-placed line in the correct category, match the legend and format.
- [ ] Open a focused PR (one server, no unrelated changes) and follow their PR template.
- [ ] Don't bump or chase the maintainer; the queue is long.

---

### 2.5 mcp.so — `mcp.so`

**Why:** large, human-browsable directory.

**Method:** the "Submit" button in the nav, or their GitHub issues, with name, description, features, and connection info.

**Checklist (human):**
- [ ] Sign in at `mcp.so` (GitHub).
- [ ] Submit `https://github.com/TsukumoHQ/trovex` via Submit or the GitHub issue.
- [ ] Fill name, tagline, short description, tags from §1; attach the §1 screenshots.
- [ ] Confirm the README renders correctly in their preview.

---

### 2.6 mcpservers.org and the secondary directories (batch)

Same §1 copy + repo URL for each. One human pass after the top five land.

| Directory | Submit method | Notes |
|---|---|---|
| mcpservers.org | GitHub PR / web submit | confirm the current path on the site — **VERIFY** |
| MCPMarket.com | web submit | large human-browsable directory (~10k servers, 23+ categories); plain repo + §1 copy — **VERIFY** submit path |
| Docker MCP Catalog (Hub) | auto from the official registry | confirm propagation; no separate submit |
| GitHub MCP Registry | auto from the official registry | renders in VS Code's MCP view; confirm propagation |
| mcp-get / registry CLIs | per their docs | inherits from official where applicable |
| awesome-mcp.tools | per the site | aggregator indexing Claude/Cursor/Cline/Windsurf — **VERIFY** submit path |
| mcp.directory | web form — `mcp.directory/submit` (confirmed live 2026-06-24) | large human-browsable index (3,000+), one-click install for Cursor/VS Code/Claude Desktop/Claude Code/Codex/ChatGPT. Also `/submit-skill` for an agent-skill listing (cross-list trovex as a skill too). **VERIFY** the `/submit` fields |
| mcpserverfinder.com | per the site — **VERIFY** submit path | curated directory w/ descriptions/features/integration details; confirm it takes author submissions vs. crawl-only |

**Checklist (human):**
- [ ] For each, check it isn't already auto-fed by the official registry (avoid duplicates).
- [ ] Submit the §1 copy + repo URL + tags.
- [ ] Log each one (registry, URL, date, live y/n) in a simple sheet.

---

### 2.7 Per-client directories — Cursor, Windsurf, Cline, Zed, Claude Code

There is no central per-client submission store for these. Each client installs an MCP server from a config file (`.cursor/mcp.json`, the Windsurf/Cline/Zed equivalents, or `claude mcp add`), not from a vetted in-app catalog you submit to. So "coverage" here means two things: the community aggregator each client's users browse, and a clean copy-paste config so an install is one step.

| Client | Where its users browse | Submission method | Action |
|---|---|---|---|
| Cursor | `cursor.directory` (community rules + MCP) | submit via the site | submit repo + §1 copy; **VERIFY** the exact form path on cursor.directory |
| Windsurf | the shared aggregators (Glama, mcp.so, awesome-mcp) | no separate store | covered by §2.3–2.5; ensure `trovex.dev/for/` has the Windsurf config |
| Cline | the shared aggregators | no separate store | covered by §2.3–2.5; ensure the Cline config is on `/for` |
| Zed | the shared aggregators | no separate store | covered by §2.3–2.5; ensure the Zed config is on `/for` |
| Claude Code | the official + GitHub MCP registries | covered by §2.1 | `claude mcp add --transport http trovex http://localhost:8765/mcp` |

**Checklist (human):**
- [ ] Submit trovex to `cursor.directory` with the §1 copy. **VERIFY** the submit path.
- [ ] Confirm `trovex.dev/for/` carries a copy-paste config for each client (the README says it does — spot-check Cursor, Windsurf, Cline, Zed).
- [ ] Don't double-list where a client reads straight from the official registry.

---

## 3. UTM scheme — tagged outbound links

Every outbound link in a listing carries UTMs so registry-referred sessions show up in Plausible. Pattern:

```
?utm_source=<registry-slug>&utm_medium=mcp-registry&utm_campaign=launch
```

Use these exact tagged URLs in each listing's homepage / `/for` links. The repo link stays a plain GitHub URL (GitHub strips query params and they don't help). The savings dashboard is local, so it's never an outbound link.

| Registry | utm_source slug | Homepage link to paste | /for link to paste |
|---|---|---|---|
| Official MCP Registry | `mcp-registry-official` | `https://trovex.dev/?utm_source=mcp-registry-official&utm_medium=mcp-registry&utm_campaign=launch` | `https://trovex.dev/for/?utm_source=mcp-registry-official&utm_medium=mcp-registry&utm_campaign=launch` |
| PulseMCP | `pulsemcp` | `https://trovex.dev/?utm_source=pulsemcp&utm_medium=mcp-registry&utm_campaign=launch` | `https://trovex.dev/for/?utm_source=pulsemcp&utm_medium=mcp-registry&utm_campaign=launch` |
| Glama | `glama` | `https://trovex.dev/?utm_source=glama&utm_medium=mcp-registry&utm_campaign=launch` | `https://trovex.dev/for/?utm_source=glama&utm_medium=mcp-registry&utm_campaign=launch` |
| awesome-mcp-servers | `awesome-mcp` | `https://trovex.dev/?utm_source=awesome-mcp&utm_medium=mcp-registry&utm_campaign=launch` | `https://trovex.dev/for/?utm_source=awesome-mcp&utm_medium=mcp-registry&utm_campaign=launch` |
| mcp.so | `mcp-so` | `https://trovex.dev/?utm_source=mcp-so&utm_medium=mcp-registry&utm_campaign=launch` | `https://trovex.dev/for/?utm_source=mcp-so&utm_medium=mcp-registry&utm_campaign=launch` |
| mcpservers.org | `mcpservers-org` | `https://trovex.dev/?utm_source=mcpservers-org&utm_medium=mcp-registry&utm_campaign=launch` | `https://trovex.dev/for/?utm_source=mcpservers-org&utm_medium=mcp-registry&utm_campaign=launch` |
| Docker MCP Catalog | `docker-mcp` | `https://trovex.dev/?utm_source=docker-mcp&utm_medium=mcp-registry&utm_campaign=launch` | `https://trovex.dev/for/?utm_source=docker-mcp&utm_medium=mcp-registry&utm_campaign=launch` |
| awesome-mcp.tools | `awesome-mcp-tools` | `https://trovex.dev/?utm_source=awesome-mcp-tools&utm_medium=mcp-registry&utm_campaign=launch` | `https://trovex.dev/for/?utm_source=awesome-mcp-tools&utm_medium=mcp-registry&utm_campaign=launch` |
| cursor.directory | `cursor-directory` | `https://trovex.dev/?utm_source=cursor-directory&utm_medium=mcp-registry&utm_campaign=launch` | `https://trovex.dev/for/?utm_source=cursor-directory&utm_medium=mcp-registry&utm_campaign=launch` |
| mcp.directory | `mcp-directory` | `https://trovex.dev/?utm_source=mcp-directory&utm_medium=mcp-registry&utm_campaign=launch` | `https://trovex.dev/for/?utm_source=mcp-directory&utm_medium=mcp-registry&utm_campaign=launch` |
| mcpserverfinder | `mcpserverfinder` | `https://trovex.dev/?utm_source=mcpserverfinder&utm_medium=mcp-registry&utm_campaign=launch` | `https://trovex.dev/for/?utm_source=mcpserverfinder&utm_medium=mcp-registry&utm_campaign=launch` |

Note: some registries auto-fill the homepage from the repo's metadata and strip query strings. Where a registry takes a free-text homepage field, paste the tagged URL; where it pulls from GitHub automatically the UTM won't survive, which is expected, and the repo-referral still shows in Plausible as a plain referrer.

---

## 4. Voice and honesty QA (applies to every listing above)

- [ ] Lowercase `trovex` everywhere in prose.
- [ ] No banned words: revolutionary, seamless, supercharge, unlock, "AI-powered", and no superlatives (fastest/first/best).
- [ ] The real ~60% number only. No fabricated logos, testimonials, user counts, or star counts — public beta.
- [ ] No company name in brand prose. The only org identifier is the GitHub URL and the reverse-DNS `server.json` name.
- [ ] Consulting stays off the listings entirely. Registries are not a sales surface; the low-key "working with a team?" line lives on the site, not here.
- [ ] Every install line actually runs — eng confirms before any human submits.

---

## 5. Handoff summary (for the human who fires these)

1. **Eng first:** clear the package blocker (§0) — PyPI publish is the clean path. Add `server.json`. Confirm the stdio invocation.
2. **Then submit in order:** Official → (PulseMCP auto) → Glama → awesome-mcp PR → mcp.so → mcpservers.org + secondary → cursor.directory + per-client.
3. **Track every submission** (registry, URL, date, live y/n) and hand the sheet to analytics-lead.
4. **Re-publish the official registry** on each new release tag so listings don't go stale.

### Things flagged VERIFY
- The exact stdio invocation `mcp-publisher` should run for trovex (§2.1).
- The current emoji legend and category list in `punkpeye/awesome-mcp-servers` (§2.4).
- The current submit path for mcpservers.org and awesome-mcp.tools (§2.6).
- The exact submission form path on cursor.directory (§2.7).

*All copy and checklists above are drafts. Nothing has been submitted to any registry.*
