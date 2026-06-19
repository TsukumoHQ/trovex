# trovex — per-registry listing variants (copy-paste, DRAFT)

**Status:** DRAFT / copy only. A human pastes each into the registry form. Nothing submitted live.
**Owner:** launch-lead · **Reviewed against:** voice, no-synergix-mention, copy-gate · **Pairs with:** mcp-registries.md (master copy + submission checklists)
**Repo:** github.com/Synergix-lab/trovex · **Landing:** trovex.dev

> This file is the field-by-field text to paste, tuned to each registry's shape and tone. The mechanics
> (how to submit, auth, server.json) live in mcp-registries.md. Master copy lives there too; this trims it
> per venue. Verify every field against the live form before pasting — limits and field names change.

Shared facts (don't drift between venues):
- Name: `trovex` · Tools: `trovex(q)`, `trovex_write`, `trovex_read`
- Stack: MCP server, Python, local-first (SQLite + on-device embeddings), no cloud/keys
- License: AGPL-3.0 core / MIT CLI · Number: ~60% fewer tokens per .md lookup (measured, repo-dependent)

---

## 1. Glama — `glama.ai/mcp` (web form; build-validated)

Glama runs a build check and shows a README-style page. Lead with the one-liner, keep it technical.

- **Name:** `trovex`
- **Repository URL:** `https://github.com/Synergix-lab/trovex`
- **One-liner (short):**
  `One canonical doc for your coding agents — path:line + freshness, ~60% fewer tokens.`
- **Description:**
  ```
  trovex indexes your repo's markdown and serves a coding agent the single current doc that answers a
  query (a path:line pointer with a freshness marker: canonical / stale / duplicate), instead of letting
  it reread a pile of .md files each session to guess which is canonical. The agent reads one section,
  not six files. A write path (trovex_write / trovex_read) lets agents share one store, so a second agent
  or teammate doesn't re-derive what's already known. Local-first: vectors in SQLite, on-device
  embeddings, no cloud or API keys. ~60% fewer tokens per .md lookup on doc-heavy repos, with a savings
  view to check the number on yours.
  ```
- **Tags:** `mcp`, `developer-tools`, `documentation`, `context`, `memory`, `rag`, `coding-agents`, `local-first`, `python`
- **Checklist:** confirm a clean `uv sync` from a fresh clone (build validation); after listing, grab the
  Glama badge → add to README (it gates the awesome-mcp PR). [see mcp-registries.md §4]

---

## 2. mcp.so — `mcp.so` (web form + GitHub login)

Human-browsable, renders your README/preview. Slightly warmer one-liner is fine; keep the body factual.

- **Name:** `trovex`
- **Repo:** `https://github.com/Synergix-lab/trovex`
- **Tagline:**
  `Stop your coding agents rereading the repo's docs — serve the one current doc instead.`
- **Description:**
  ```
  Your coding agents reread .md files every session to work out which doc is canonical, burning tokens
  and sometimes still picking the stale one. trovex indexes the markdown and returns one answer: a
  path:line pointer plus a freshness marker, so the agent reads just the relevant section. Agents can
  also write what they learn back through one shared store (trovex_write / trovex_read), so your fleet
  and your teammates work from the same source of truth. Runs locally: SQLite + on-device embeddings,
  no cloud, no keys. ~60% fewer tokens per lookup on doc-heavy repos; ships a view so you can verify it.
  ```
- **Tags:** `mcp-server`, `developer-tools`, `documentation`, `context`, `coding-agents`, `local-first`
- **Assets:** attach the screenshots from mcp-registries.md §1 (savings view + one-doc result).
- **Checklist:** confirm the README renders cleanly in their preview.

---

## 3. awesome-mcp-servers — GitHub PR (one markdown line)

Match their exact format + emoji legend (verify in their README before submitting). Requires a Glama
listing first. Place alphabetically in the right category (likely "Knowledge & Memory" or "Developer Tools").

- **List line:**
  ```markdown
  - [trovex](https://github.com/Synergix-lab/trovex) 🐍 🏠 - Local MCP server that returns the one canonical doc per query (path:line + freshness marker), not a ranked list of chunks. ~60% fewer tokens per lookup. AGPL, on-device.
  ```
- **Legend used:** 🐍 Python · 🏠 local/self-hosted — confirm these are still the current keys.
- **Checklist:** Glama listing exists; one server, one alphabetical line, no unrelated changes; follow
  their PR template; don't bump the queue. [see mcp-registries.md §5]

---

## 4. PulseMCP — `pulsemcp.com` (auto-ingest; editorial)

No form submission — PulseMCP auto-ingests from the Official Registry weekly. So the "listing" is whatever
the Official Registry server.json carries; the lever here is the editorial/newsletter pickup.

- **Inherited listing:** matches the Official Registry (name, ≤100-char description, repo). [server.json in mcp-registries.md §2]
- **If a correction is needed** (form), use the mcp.so tagline + description above.
- **Editorial outreach note (for the newsletter — value-first, short; a human sends):**
  ```
  trovex is a local-first MCP server that cuts what coding agents spend rereading a repo's .md docs: it
  serves the one current doc (path:line + freshness) instead of a full reread, ~60% fewer tokens on
  doc-heavy repos, with a savings view to verify. Open source, AGPL core / MIT CLI. If it fits a future
  issue: github.com/Synergix-lab/trovex — happy to answer anything.
  ```
- **Checklist:** confirm trovex appears within a week of the Official Registry listing going live; only
  use the correction form if it doesn't. [see mcp-registries.md §3]

---

## 5. Consistency QA (before any paste)

- [ ] Same name (`trovex`), same tool names, same ~60% framing across all four.
- [ ] Lowercase `trovex`; no banned/hype words; no superlatives.
- [ ] No "Synergix" in any prose field — repo URL identifier only.
- [ ] Every field within the live form's character limit (re-check on the form).
- [ ] ~60% always paired with "doc-heavy repos" + "verify on yours" — never a bare guarantee.
- [ ] Install line / config verified to run before any listing that shows one.

*All copy above is a draft. Nothing has been submitted.*
