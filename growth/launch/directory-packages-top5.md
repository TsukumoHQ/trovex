# Ready-to-submit directory packages — top 5 (DRAFT)

**Status:** DRAFT / copy-complete packages. Nothing submitted. A human fires each; owner-gated.
**Owner:** launch-lead · **Reviewed against:** directory-submissions.md (#154), mcp-registries.md, suite-positioning.md, voice, no-synergix-mention, pricing-policy, agency-* memories
**Repo:** github.com/Synergix-lab/trovex · **Landing:** trovex.dev

> The top-5 highest-ROI listings from `directory-submissions.md §5`, each as a **complete, paste-ready package**: every field filled, asset list, links, format rules, gotchas, and the exact human steps. Four are trovex (OSS); #5 (Clutch) is the **agency (tsukumo)** — its copy is a draft routed to owner/tsukumo repo, not a tsukumo change here.
>
> **Common pre-req for the four trovex packages:** repo public + on PyPI + clean history (unfreeze-checklist §1). Don't fire a trovex listing while the repo is private — a dead repo link burns the listing. Each package marks its own gate.

---

## 1. Awesome lists (GitHub PR) — `punkpeye/awesome-mcp-servers` (+ niche awesome-* lists)

**Type:** GitHub PR · **Cost:** free · **Pre-req:** repo public; (Glama listing first — see mcp-registries §5).

**Paste-ready list line** (match their format + legend exactly — confirm current legend in their README first):
```markdown
- [trovex](https://github.com/Synergix-lab/trovex) 🐍 🏠 - Indexes your repo's markdown and serves agents the one canonical doc (path:line + freshness) instead of a reread. ~60% fewer tokens. Local-first.
```
- 🐍 = Python, 🏠 = local/self-hosted — **verify the legend keys** in their README; they change.
- Category: likely **Knowledge & Memory** or **Developer Tools** — match an existing section; place **alphabetically**.

**Other awesome-* lists to target (one focused PR each):** awesome-mcp-devtools, awesome-ai-coding, awesome-claude / awesome-cursor, awesome-developer-tools. Same line, adjust to each list's format.

**Assets:** none (text line only).

**Human steps:**
- [ ] Confirm Glama listing exists (gates the punkpeye PR).
- [ ] Read CONTRIBUTING + legend; pick the right section.
- [ ] Fork → add ONE alphabetically-placed line → match emoji legend + format exactly.
- [ ] Open a focused PR (one server, no unrelated changes); follow their template.
- [ ] Be patient — long maintainer queue; do not bump/spam.

**Gotchas:** wrong emoji/section/format = rejected; bundling multiple changes = rejected; vote/bump-begging = ignored.

---

## 2. AlternativeTo — `alternativeto.net`

**Type:** web form (community-edited) · **Cost:** free · **Pre-req:** repo public + trovex.dev live.

**Package (field-by-field):**
- **Name:** `trovex`
- **Tagline:** One canonical doc for your coding agents — ~60% fewer tokens.
- **Description:**
  > trovex is an open-source MCP server + CLI that indexes your repo's markdown and serves a coding agent the single doc that answers a query — a `path:line` pointer with a freshness marker (canonical / stale / duplicate) — instead of rereading the repo every session. Agents read one section, not six files, and can write what they learn back through one shared store. Local-first: SQLite + on-device ONNX embeddings, no cloud, no API keys. ~60% fewer tokens per lookup.
- **License/Pricing:** Free / Open Source (AGPL-3.0 core, MIT CLI)
- **Platforms:** Mac, Windows, Linux, Self-Hosted
- **Links:** Homepage trovex.dev · Repo github.com/Synergix-lab/trovex
- **Tags:** mcp, ai-coding, coding-agents, developer-tools, context, token-efficiency, local-first, cli, open-source
- **Listed as an alternative to:** `CLAUDE.md` (concept), **repomix**, **context-hub / CTX** — capture the "alternative to" search intent (ties to geo-lead comparison pages).

**Assets:** square logo (lowercase `trovex` wordmark) + 2–3 screenshots (index finishing, savings receipt, single `path:line` result).

**Human steps:**
- [ ] Create/sign in; "Add application."
- [ ] Fill the fields above; set Free/Open Source + platforms.
- [ ] Add it as an *alternative to* the tools listed (the high-intent lever).
- [ ] Upload logo + screenshots.

**Gotchas:** community-moderated — others can edit; keep the description factual + non-promo or it gets trimmed. No superlatives.

---

## 3. DevHunt — `devhunt.org`

**Type:** GitHub PR + GitHub-login voting · **Cost:** free · **Pre-req:** repo public + working `uvx trovex` quickstart. Pair with the launch-day window (launch-teardown-playbook: it has a launch-spike model).

**Package:**
- **Tool name:** trovex
- **One-liner:** Give your coding agent one canonical doc (path:line + freshness) instead of rereading the repo — ~60% fewer tokens. Local-first.
- **Description:**
  > Your coding agents reread `.md` files every session to guess which is canonical, burning tokens. trovex indexes the markdown and returns the single current doc that answers a query, with a freshness marker, so the agent reads one section, not six files. Runs locally (SQLite + ONNX), no cloud or keys. Open source.
- **Tags/category:** Developer Tools / AI
- **Links:** repo + trovex.dev
- **Demo:** short gif/video of `index` → a `trovex(q)` result → the savings receipt (see assets).

**Assets:** logo, 1 short demo gif/video, 2–3 screenshots (reuse mcp-registries §1 set).

**Human steps:**
- [ ] Read their CONTRIBUTING (submission is a PR to the DevHunt repo).
- [ ] Fork → add the tool entry per their schema → include demo asset links.
- [ ] Open the PR; engage honestly with feedback. **Ask for feedback, never upvotes** (GitHub-auth voting flags rings).
- [ ] Time it with the coordinated launch window for the spike (don't stack with HN/PH same day).

**Gotchas:** schema/format mismatch = rejected; vote manipulation detected via GitHub auth; broken quickstart kills it.

---

## 4. Product Hunt (permanent profile) — `producthunt.com`

**Type:** launch + permanent profile · **Cost:** free · **Pre-req:** full launch readiness gate (launch-day-runbook §0); real gallery assets. **This is a one-shot — fire per the runbook, not ad-hoc.**

**Package:**
- **Name:** trovex
- **Tagline (≤60 chars):** One canonical doc for your coding agents — ~60% fewer tokens
- **Description:**
  > trovex is an open-source MCP server + CLI. It indexes your repo's markdown and serves your coding agent the one current doc that answers a query (a `path:line` pointer + freshness marker), instead of rereading the repo every session. Reads one section, not six files; shares a write path so agents stay on one source of truth. Local-first — SQLite + on-device embeddings, no cloud or keys. ~60% fewer tokens per lookup, with a dashboard that shows what you stopped spending.
- **Topics:** Developer Tools, Artificial Intelligence, Open Source, GitHub
- **Links:** repo + trovex.dev
- **Maker first comment (post at launch — personal-problem story, ends with a use-case question):**
  > I built trovex because my coding agent kept burning a chunk of every session rereading runbooks/ADRs/READMEs to work out which doc was current — and sometimes still grabbed the stale one. It indexes the markdown and returns the one canonical doc (path:line + freshness) so the agent reads one section, not six files. Local-first, no keys. It ships a savings view so you can check the number on your own repo (~60% fewer tokens on my doc-heavy ones; less on small doc sets — it's repo-dependent). What's the first repo you'd point it at?

**Assets (gallery — REAL runs only, no mockups):** logo, short demo video, `index` finishing, the savings receipt, a real `trovex(q)` result, the rendered reader.

**Human steps:**
- [ ] Meet the launch-readiness gate (runbook §0); assets ready.
- [ ] Schedule for 12:01am PT, a non-stacked day (not the HN day).
- [ ] Post the maker first comment at launch; answer every comment through the day.
- [ ] Notify the pre-built supporter list 1:1 — ask for *feedback*, never upvotes.

**Gotchas:** PH clears votes from new/low-engagement/same-IP accounts; vote-begging + same-city spikes + AI-generated comments are detected and discounted. The permanent profile is a durable free backlink regardless of rank — the rank is not the metric (north star = activation).

---

## 5. Clutch — `clutch.co` (AGENCY / tsukumo — route to owner/tsukumo)

**Type:** profile + verified reviews · **Cost:** free profile; sponsored $1.5–4k+/mo (skip) · **Pre-req:** owner decision; real contact; client reference(s) for verified reviews.

> ⚠️ This is **agency** copy for tsukumo (own repo per repo-routing). Shipped here as a draft package for cmo/owner to execute — not a tsukumo change. Uses agency brand (acid `#c8ff00`, lowercase `tsukumo`), **no public prices** (pricing-policy), qualitative proof only (agency-proof).

**Package:**
- **Company:** tsukumo
- **Tagline:** Turn your dev team into agentic operators — prod-grade AI, not seat licenses.
- **Description:**
  > tsukumo is a Switzerland-based AI-engineering studio and consulting practice (est. 2026). We help startups and scale-up engineering teams run AI coding agents at prod quality — augmenting developers, not replacing them. Two doors: studio (build my product) and consulting (my team struggles with AI). We install capability, not seat licenses: agentic-dev training, agentic process setup, and building agentic-first systems.
- **Service lines (Clutch taxonomy):** Artificial Intelligence · Generative AI · AI Consulting · Custom Software Development · IT Staff Augmentation (training/enablement)
- **Focus areas / tags:** AI agents, agentic development, developer enablement, LLM/coding-agents, AI strategy
- **Location:** Switzerland · **Founded:** 2026 · **Size:** [owner to set]
- **Min project size / rate:** **leave blank or "Inquire"** — no public prices (pricing-policy).
- **Links:** tsukumo.ch · real contact (owner).
- **Reviews:** **none fabricated.** Leave empty until real client reviews exist; Clutch verifies via client interview — owner arranges 2–3 references (agency-proof: clareo systems, CIL — only with their permission).

**Assets:** tsukumo logo (Operator Cursor mark, acid on ink), a brand banner; no client logos without permission.

**Human steps (owner):**
- [ ] Decide free-profile-only (recommended) vs sponsored (skip until deal size justifies).
- [ ] Claim/create the profile; fill the fields above; **no prices**.
- [ ] Pick service lines matching Clutch's taxonomy.
- [ ] Arrange 2–3 verified client reviews (client interview) — permissioned only.
- [ ] Confirm the profile renders; link tsukumo.ch.

**Gotchas:** rankings = review quality + sponsor spend (don't pay for rank early); verified reviews need real client contacts; no fabricated ratings; keep prices off.

---

## 6. Fire order + tracking

1. **AlternativeTo + Awesome lists** (free, compounding, citable) — first, alongside the registry push (mcp-registries.md).
2. **DevHunt** — time with the coordinated launch window (spike model).
3. **Product Hunt** — one-shot, per the launch-day runbook gate.
4. **Clutch (agency)** — owner-gated, route to tsukumo; free profile + verified reviews.
- [ ] Log each (directory, date submitted, live y/n, URL) in the tracking sheet.
- [ ] Re-verify each listing renders + links resolve after it's live.

## 7. Voice / brand QA (every field)

- [ ] trovex packages: lowercase `trovex`, no banned words, real ~60% only, no consulting CTA, no fabricated users, every link resolves.
- [ ] tsukumo package: lowercase `tsukumo`, augment-not-replace, **no prices**, qualitative proof only, no fabricated reviews.
- [ ] No "Synergix" in any prose (only the GitHub-org identifier for trovex).
- [ ] Assets on-brand (trovex green `#22c55e`; tsukumo acid `#c8ff00`).

*All packages above are drafts. Nothing has been submitted.*
