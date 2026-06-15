# trovex — MCP registry listings + per-registry submission checklists

**Status:** DRAFT / copy only. Nothing here is submitted live. A human runs each checklist.
**Owner:** launch-lead · **Reviewed against:** product-marketing-context.md, voice, no-synergix-mention
**Repo:** github.com/Synergix-lab/trovex · **Landing:** trovex.dev

---

## 0. Why registries first (the leverage)

MCP registries are trovex's app-store shelf — where the people most likely to install
(MCP early adopters who already run coding agents) browse. Research findings that shape this plan:

- **The Official MCP Registry is the keystone.** Submit once and it auto-propagates to
  PulseMCP (weekly auto-ingest), Docker Hub, the GitHub MCP Registry (renders natively in
  VS Code's Extensions view), and Anthropic-named consumers. One submit, many shelves.
- **Being listed ≠ getting installs.** The install signal is verified ownership + versioned
  releases + editorial/newsletter pickup (PulseMCP curates). So: ship a clean release, a real
  one-line install, and a savings number people can repro.
- **Submit order (do in this sequence):**
  1. Official Registry (`server.json` + `mcp-publisher`) → unlocks PulseMCP / VS Code / Docker free
  2. Glama (web form; now gates the awesome-mcp-servers PR)
  3. awesome-mcp-servers (GitHub PR; requires a Glama listing first)
  4. mcp.so (web form + GitHub login)
  5. Smithery — **only after** a brand-neutral hosted endpoint exists (see §6)

### Blockers / dependencies for a human or eng (flagged, not mine to ship)
- [ ] **`server.json` does not exist in the repo yet.** Official Registry needs it at repo root.
      Draft schema in §2. → eng/geo-lead.
- [ ] **Package is not published to PyPI.** Today install is `uv run trovex` from source. A
      `pip install trovex` / `uvx trovex` path makes every listing's install line one line.
      Recommend publishing to PyPI before the Official submit. → eng.
- [ ] **Hosted endpoint is branded `trovex.prod.synergix.ch`.** Per the no-synergix-mention
      brand rule, do NOT surface that host in any listing. Stand up a brand-neutral host
      (e.g. `mcp.trovex.dev`) before any *remote* listing (Smithery). Until then list as
      local-first/stdio only. → eng.

---

## 1. Canonical listing copy (the master — reuse, then trim per registry)

Keep the lowercase wordmark `trovex`. No superlatives. Brand prose never names the company.

**Name:** `trovex`
**Reverse-DNS name (Official Registry):** `io.github.Synergix-lab/trovex`
  *(technical identifier only — not brand copy; acceptable per the exception in no-synergix-mention)*

**Tagline (≤60 chars):**
> One canonical doc for your coding agents — ~60% fewer tokens.

**Short description (≤100 chars — Official Registry hard limit):**
> Indexes your repo's markdown and serves agents the one current doc, not a reread of the repo.

**One-paragraph description (directories that allow prose):**
> Your coding agents reread `.md` files every session to guess which one is canonical, burning
> tokens each time. trovex indexes your repo's markdown and exposes one MCP tool that returns the
> single doc answering a query — a `path:line` pointer with a freshness marker (canonical / stale /
> duplicate) — so the agent reads just the relevant section. Agents can also write what they learn
> back through one shared store, so every agent and teammate works from the same source of truth.
> Runs locally: SQLite + local ONNX embeddings, no cloud, no API keys. ~60% fewer tokens per lookup,
> with a dashboard that shows what you stopped spending.

**Tags / categories:** `mcp-server`, `developer-tools`, `code`, `context`, `memory`,
`rag`, `documentation`, `coding-agents`, `claude-code`, `cursor`, `token-efficiency`, `local-first`, `python`

**Install (local / stdio — the default):**
```bash
# clone + run from source (today)
git clone https://github.com/Synergix-lab/trovex && cd trovex
uv sync
uv run trovex index /path/to/your/repo
uv run trovex serve            # MCP at /mcp, UI at /
```
*(Once on PyPI, collapse to: `uvx trovex index <repo>` / `uvx trovex serve`.)*

**MCP client config (stdio) — what a user pastes into their agent:**
```json
{
  "mcpServers": {
    "trovex": {
      "command": "uv",
      "args": ["run", "trovex", "serve", "--stdio"],
      "cwd": "/path/to/trovex"
    }
  }
}
```
> ⚠️ Verify the exact stdio invocation against the CLI before publishing — confirm `serve --stdio`
> (or the real flag) with eng. Do not ship a config that doesn't run.

**MCP tools exposed (for registries that list tools):**
- `trovex(q)` — route a query to the right on-disk `.md`; returns pointers (`path:line` + freshness).
- `trovex_write(content, kind?, doc_id?)` — store a record/memory/decision inside trovex.
- `trovex_read(query|doc_id, section?)` — read a trovex-owned doc back, optionally one section.

**Repo:** https://github.com/Synergix-lab/trovex · **License:** AGPL-3.0-or-later (CLI: MIT)
**Homepage:** https://trovex.dev

**Proof line (use the real number only):** ~60% fewer tokens per doc lookup; local savings
dashboard shows would-have-read vs. actual. No customers/testimonials yet — pre-launch, don't invent any.

**Screenshot / asset list to capture (hand to design or capture from the running app):**
1. Terminal: `trovex index` finishing + a one-line "indexed N docs" result.
2. The savings dashboard / receipt (tokens would-have-read vs. actual, ~60% reduction).
3. An agent calling `trovex(q)` and getting a single `path:line` + freshness marker result.
4. The `/doc/{id}` rendered reader (human view of a trovex-owned doc).
5. Square icon / logo (lowercase `trovex` wordmark) for registry thumbnails.

---

## 2. Official MCP Registry — `registry.modelcontextprotocol.io`

**Why first:** keystone. Feeds PulseMCP, Docker Hub, GitHub MCP Registry (VS Code Extensions view),
Anthropic. Do this once, correctly.

**`server.json` to add at repo root** (DRAFT — eng confirms package coordinates before publish):
```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.Synergix-lab/trovex",
  "description": "Indexes your repo's markdown and serves agents the one current doc, not a reread.",
  "repository": {
    "url": "https://github.com/Synergix-lab/trovex",
    "source": "github"
  },
  "version": "0.11.0",
  "packages": [
    {
      "registry_type": "pypi",
      "identifier": "trovex",
      "version": "0.11.0",
      "transport": { "type": "stdio" }
    }
  ]
}
```
> `description` is ≤100 chars (counted: ok). `packages` assumes a published PyPI package named
> `trovex` — if not published, use a `github` release package type or hold until PyPI exists.

**Submission checklist (human runs):**
- [ ] Publish `trovex` to PyPI (or decide on the GitHub-release package type). [BLOCKER]
- [ ] Add `server.json` (above) to repo root; bump `version` to match the release tag.
- [ ] Install the publisher CLI: `mcp-publisher` (per official docs).
- [ ] Authenticate: `mcp-publisher login github-oidc` (uses the GitHub org namespace → verifies
      ownership of `io.github.Synergix-lab/*`). Must be run by someone with rights on the org.
- [ ] Tag the release: `git tag v0.11.0 && git push --tags`.
- [ ] `mcp-publisher publish` from the repo root.
- [ ] Verify the listing resolves at registry.modelcontextprotocol.io and the REST API returns it.
- [ ] (Optional, recommended) Wire a GitHub Action with `id-token: write` (OIDC) to auto-publish
      on each tagged release, so listings never go stale.
- **Gotchas:** name MUST be reverse-DNS matching the GitHub namespace; description hard cap 100 chars;
  metadata-only (no code uploaded — package lives on PyPI/GitHub Releases). Propagation to PulseMCP
  takes up to a week.

---

## 3. PulseMCP — `pulsemcp.com`

**Submission:** none required — auto-ingests from the Official Registry weekly. Listing copy inherits.

**Checklist (human):**
- [ ] After the Official Registry listing is live, wait up to 1 week; confirm trovex appears on PulseMCP.
- [ ] If not present after a week, use their "submit/correct a server" form with the canonical copy (§1).
- [ ] PulseMCP curates an editorial newsletter — once live with a working install + the savings number,
      it's worth a short, value-first note to their editor (no hype, just the token-cost angle). Draft
      that as a separate outreach asset if cmo wants it.

---

## 4. Glama — `glama.ai/mcp`

**Why:** ~19k listings, and a Glama listing now gates the awesome-mcp-servers PR. Do before awesome-mcp.

**Listing copy:** master copy (§1). Glama runs build validation — the server must actually build/run.

**Checklist (human):**
- [ ] Sign in at glama.ai with GitHub.
- [ ] Submit the repo URL `https://github.com/Synergix-lab/trovex` via their add-server form.
- [ ] Ensure the repo builds cleanly from a fresh clone (`uv sync` succeeds) — Glama validates.
- [ ] Fill tagline, description, tags from §1.
- [ ] Once listed, grab the Glama badge (needed for the awesome-mcp PR) and add it to README.
- **Gotcha:** if the build check fails, the listing won't verify — fix the cold-clone path first.

---

## 5. awesome-mcp-servers — GitHub PR to `punkpeye/awesome-mcp-servers`

**Why:** 83k+ stars, high visibility, but a known bottleneck and now requires a Glama listing first.

**Entry copy (markdown list line — match their existing format exactly):**
```markdown
- [trovex](https://github.com/Synergix-lab/trovex) 🐍 🏠 - Indexes your repo's markdown and serves agents the one canonical doc (path:line + freshness) instead of a reread. ~60% fewer tokens. Local-first.
```
> Use their legend emojis (🐍 = Python, 🏠 = local/self-hosted) — confirm the current legend in
> their README before submitting; categories and emoji keys change.

**Checklist (human):**
- [ ] Confirm the Glama listing exists (prerequisite).
- [ ] Read CONTRIBUTING + the category list; pick the right section (likely "Knowledge & Memory"
      or "Developer Tools" — match what's there).
- [ ] Fork, add ONE alphabetically-placed line in the correct category, match emoji legend + format.
- [ ] Open a focused PR (one server, no unrelated changes); follow their PR template.
- [ ] Be patient — maintainer queue is long; do not bump/spam.

---

## 6. mcp.so — `mcp.so`

**Why:** ~18k servers, popular human-browsable directory.

**Listing copy:** master copy (§1). They render a README/preview — keep it clean.

**Checklist (human):**
- [ ] Sign in at mcp.so with GitHub.
- [ ] Submit `https://github.com/Synergix-lab/trovex` via their submit form.
- [ ] Fill name, tagline, description, tags from §1; attach screenshots (§1 asset list).
- [ ] Confirm the README renders correctly in their preview.

---

## 7. Smithery — `smithery.ai`  (CONDITIONAL — needs a remote endpoint)

**Why deferred:** Smithery expects a hosted **HTTP** MCP endpoint. trovex's default is local
stdio. A hosted endpoint exists internally but it is branded `trovex.prod.synergix.ch` — **do not
list that** (brand rule). 

**Pre-req before listing:**
- [ ] Stand up a brand-neutral hosted MCP endpoint (e.g. `mcp.trovex.dev/mcp`). [BLOCKER]
- [ ] Decide whether a hosted multi-tenant trovex is even desirable, or whether to skip Smithery
      and stay local-first. (Local-first is a core differentiator — listing a hosted version is a
      product decision for cmo/eng, not a copy decision.)

**Checklist (human — only once the above is resolved):**
- [ ] Sign in at smithery.ai with GitHub.
- [ ] Add the server with the brand-neutral HTTP endpoint URL.
- [ ] Provide config schema / connection details; run their technical validation.
- [ ] Use master copy (§1), tags from §1.

---

## 8. Secondary directories (batch — same master copy, low effort)

Each takes the §1 copy + repo URL. Do after the top 5 land. One human pass, ~an afternoon.

| Directory | Submit method | Notes |
|---|---|---|
| mcpservers.org | web form / GitHub | ~4k listings |
| mcp-get.com / registry CLIs | per their docs | inherits from Official where applicable |
| Cline / Continue / Cursor MCP directories | per-client docs | high intent — these users run coding agents |
| Docker MCP Catalog (Hub) | auto from Official | confirm propagation, no separate submit |

**Checklist (human):**
- [ ] For each: confirm it's not already auto-fed by the Official Registry (avoid dupes).
- [ ] Submit master copy + repo URL + tags.
- [ ] Track each submission in a simple sheet (registry, URL, date submitted, live y/n).

---

## 9. Voice / brand QA (applies to every listing above)

- [ ] Lowercase `trovex` everywhere in prose.
- [ ] No banned words: revolutionary, seamless, supercharge, unlock, "AI-powered".
- [ ] No superlatives (fastest/first/best) — registries and HN both penalize hype.
- [ ] Real ~60% number only; **no fabricated logos, testimonials, or user counts** (pre-launch).
- [ ] **No "Synergix" in any brand prose** — only the unavoidable GitHub-org / reverse-DNS identifier.
- [ ] Consulting angle absent from listings (registries are not a sales surface; keep it to the site).
- [ ] Every install line actually runs — verify with eng before any human submits.

---

## 10. Handoff summary (for the human who fires these)

1. **Eng first:** publish to PyPI, add `server.json`, confirm the stdio invocation, (optionally)
   stand up `mcp.trovex.dev`.
2. **Then submit in order:** Official → (PulseMCP auto) → Glama → awesome-mcp PR → mcp.so → secondary.
3. **Smithery only** after a brand-neutral hosted endpoint exists and a hosted-trovex decision is made.
4. Track every submission; re-publish the Official Registry on each new release tag.

*All copy above is a draft. Nothing has been submitted.*
