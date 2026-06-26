# trovex — free-tool directory listing kit + per-directory submission checklists

**Status:** DRAFT. Nothing here is submitted live. A human runs each checklist and fires each submit.
**Owner:** launch-lead · **Reviewed against:** `.agents/product-marketing-context.md`, the `voice` memory, anti-ai-slop pass.
**Covers:** the two LIVE free, no-signup standalone web tools — `trovex.dev/audit` (5-minute self-audit, shipped #519) and `trovex.dev/savings` (token-savings calculator, live). Both run in the browser, no install, no email wall.
**Verified live (2026-06-25):** `trovex.dev/audit` returns the page "Is your coding agent burning tokens on docs? A 5-minute self-audit"; `trovex.dev/savings` returns "trovex — token-savings estimate for your coding agents". Neither has a trailing slash — `trovex.dev/audit/` and `trovex.dev/savings/` 404.

Scope: this is the **free-tools shelf** — directories where devs browse for free/standalone tools. It is **not** the MCP-registry kit (`mcp-registry-kit.md` — that lists the trovex *product* on the MCP shelf) and it is **not** a second Show HN (content-lead owns the social/forum copy for `/audit`; you only get one Show HN per launch — don't burn it here). Different shelf, different hook, same north star: qualified reach → install → consulting funnel.

---

## 0. Why a free-tools directory pass, and what these are

The product shelf is MCP registries (covered elsewhere). This is the other shelf: a developer who isn't yet looking for an MCP server but *is* looking for "a free thing that tells me if my agent setup is wasting money." Free-tool and AI-tool directories are where that search lands. The two tools travel on their own merit — "I built a free X" — and each one points quietly into the same funnel (run `uvx trovex`, star the repo) without a sales pitch.

Two things make these safe and worth listing:

- **They stand alone.** A dev gets value in five minutes whether or not they ever install trovex or talk to us. That's the bar a directory listing has to clear to not read as spam.
- **They're reversible and low-noise.** A directory listing isn't a launch event. Submit, get indexed, move on. No coordination, no one-shot burned.

### What to list, and in what order

Lead with **`/savings`** — a calculator is the more directory-native "tool" (it slots into a clean searchable category: "token cost calculator"). List **`/audit`** second as the checklist/assessment tool. Some directories take one tool per listing; a few allow a maker/profile with multiple tools — list both there.

**Submit order (best-fit first):**

1. Dev-tool launch directories (§2.1) — DevHunt, Uneed, Fazier, Microlaunch, Peerlist. The right audience (builders), free, fast.
2. AI-tool directories (§2.2) — There's An AI For That, Futurepedia, Future Tools, Toolify. The agent-token-cost angle fits the "AI tools" search.
3. Software / alternatives directories (§2.3) — AlternativeTo, SaaSHub. Broader, slower; **VERIFY** each takes a free standalone web tool (some are SaaS-only).

A directory that only lists paid SaaS, or that charges to list, is out of scope — skip it. The point is reach where free-tool seekers already are, not a paid placement.

---

## 1. Canonical listing copy (one block per tool — reuse, trim per directory)

Lowercase `trovex` in all prose. No superlatives, no banned words. Brand prose never names the company; the only org identifier is the unavoidable GitHub URL. The real ~60% number only — every listing makes the reader generate their *own* number; no fabricated proof.

### 1.A — `trovex /savings` (token-savings calculator)

**Name:** `trovex token-savings calculator` *(directories that want a short tool name: `trovex /savings`)*

**Tool URL (the listing's primary link — tagged per §3):** `https://trovex.dev/savings`

**Tagline (≤60 chars):**
> Estimate the tokens your coding agents waste rereading docs.
*(59 chars.)*

**One-liner (≤160 chars):**
> A free, no-signup calculator: see how many tokens your coding agents burn rereading your repo's markdown each session versus serving one canonical doc per query.
*(159 chars.)*

**Short description (~50 words):**
> Your coding agents reread your repo's markdown every session to guess which file is current, and you pay for it on every session, every agent, every teammate. This calculator estimates that cost from your own numbers — every input is an editable assumption. About 60% fewer tokens at the defaults. Open source, runs in the browser.

**Long description (~120 words):**
> Coding agents reread your repo's markdown each session to work out which file is current, then answer from a guess. That reread is most of the doc-lookup token bill — about 60% on our own repos.
>
> This calculator lets you put in your own numbers (repo size, how many docs, how often agents look things up) and shows the token cost of rereading versus serving one canonical doc per query. Every field is a labelled, editable assumption, so it's your estimate, not ours. The result is a shareable link, so "my repo would save X" travels on its own.
>
> No signup, no email wall. Open source (the math mirrors the trovex CLI). It's the discovery front-end for `trovex`, the local MCP server that does this for real.

**Category / tags:** `developer-tools`, `ai`, `llm`, `coding-agents`, `token-cost`, `calculator`, `cost-estimator`, `free`, `no-signup`, `open-source`

**One-line "what it does" (for directories with a single summary field):**
> Free calculator that estimates how many tokens your coding agents waste rereading docs, from your own repo numbers.

### 1.B — `trovex /audit` (5-minute self-audit)

**Name:** `trovex agent token-waste self-audit` *(short: `trovex /audit`)*

**Tool URL (primary link — tagged per §3):** `https://trovex.dev/audit`

**Tagline (≤60 chars):**
> 5-minute self-audit: are your agents wasting tokens on docs?
*(60 chars.)*

**One-liner (≤160 chars):**
> A free, no-signup checklist that scores whether your coding-agent setup wastes tokens rereading docs, then one command measures the real number on your repo.
*(156 chars.)*

**Short description (~50 words):**
> Score your coding-agent setup against a short checklist to find out whether your agents waste tokens rereading docs. Then run one command to measure the actual number on your own repo. The failing checks are the ones that get worse at team scale. Free, no signup, open source.

**The honest hook (use where a directory allows a longer pitch — straight from content-lead):**
> Most of the audit's failing checks are the ones that compound at team scale. A low score tells you to skip trovex; a high score means the cost is already compounding across your agents and teammates. Either way you leave with a number, not a pitch.

**Category / tags:** `developer-tools`, `ai`, `llm`, `coding-agents`, `token-cost`, `audit`, `checklist`, `free`, `no-signup`, `open-source`

**One-line "what it does":**
> Free 5-minute self-audit that scores whether your coding agents waste tokens rereading docs.

### Shared assets (both tools)

**Maker / org:** TsukumoHQ · **Repo (when a directory wants a source link):** `https://github.com/TsukumoHQ/trovex` · **Homepage:** `https://trovex.dev`
**License:** the underlying tool (trovex) is AGPL-3.0-or-later; the calculators run client-side.
**Pricing field (almost every directory asks):** **Free.** No paid tier on these tools. (If a directory forces a "freemium/paid" choice, pick **Free**.)
**Proof line (the only number):** about 60% fewer tokens per doc lookup, at the calculator's defaults / on our repos. No customers, testimonials, star counts, or logos — public beta. Don't invent any.

**Screenshots / OG to attach (grab from the live pages — `/savings` already ships a 1200×630 OG card at `trovex.dev/api/savings-card`):**
1. `/savings` — the calculator with the would-have-read vs. actual result and the ~60% line.
2. `/savings` — a shareable result link / receipt card.
3. `/audit` — the checklist mid-score.
4. Square `trovex` wordmark for directory thumbnails (design-lead has the asset).

---

## 2. Per-directory checklists

Every submit below is **drafts-only here** — a human signs in and fires. Each is flagged **VERIFY** where the exact submit path / fields can drift; confirm on the site before pasting.

### 2.1 Dev-tool launch directories (best fit — fire first)

| Directory | URL | Method | Free? | Notes / **VERIFY** |
|---|---|---|---|---|
| **DevHunt** | `devhunt.org` | GitHub sign-in → submit tool | Yes | Built for dev tools; weekly leaderboard. Best audience fit. Submit `/savings` as the tool, link repo as source. **VERIFY** current submit form. |
| **Uneed** | `uneed.best` | Account → submit product | Yes (queue) | Daily "tools" directory. Free listing joins a queue; paid skip exists — **do not pay**, the free slot is fine. Category: developer / AI tools. |
| **Fazier** | `fazier.com` | Account → submit | Yes | Launch + permanent directory. Takes free tools. **VERIFY** category list. |
| **Microlaunch** | `microlaunch.net` | Account → submit | Yes | Indie launch calendar + directory. Pick a launch day or list evergreen. **VERIFY** whether a launch date is required. |
| **Peerlist Launchpad** | `peerlist.io` | Peerlist account → Launchpad | Yes | Launch + a permanent project profile devs browse. Good for a maker profile listing both tools. **VERIFY** project vs. launch flow. |

**Checklist (human, per directory):**
- [ ] Sign in (GitHub where offered).
- [ ] Submit `/savings` first (cleaner tool-category fit); add `/audit` as a second tool where a maker profile allows it.
- [ ] Paste name, tagline, description, tags from §1; set pricing = **Free**.
- [ ] Use the §3 tagged URL as the tool link; attach a §1 screenshot / the `/savings` OG card.
- [ ] Confirm the link previews correctly (the `/savings` OG card renders the calculator).
- [ ] Log it (directory, URL, date, live y/n) for the §5 sheet.

#### 2.1.1 DevHunt launch-day run-sheet (drafts only; a human fires)

DevHunt is the best-fit shelf and the one where launch-day effort actually pays: each listing gets its own Google-indexed page, and a strong day keeps it on the homepage shortlist for months (learning-log #8). The listing is a GitHub PR + real user-login voting, so the day-of behaviour matters more than on a passive directory.

**Timing:** submit early in the week (Mon/Tue) so the listing rides the full week on the leaderboard. Have the repo README clean first; it's the click-through surface, and where a dev decides to install (#7).

**Launch-day cadence (this is the part that compounds):**
- Reply to every comment in your own voice within a few hours. Answer "how is this different from X" plainly, with the real number, no pitch.
- Support a couple of other makers' tools that day. Genuine, reciprocal. DevHunt's audiences merge when makers show up for each other.
- Don't: vote-beg, run sockpuppets, or paste the same comment twice. One real answer per thread.

**Comment-reply seeds** (developer-honest starting points — **FLAG: brand-copy, re-check against the brand lock when design's gap-list lands**):
- *"what's the catch?"* → "none on the tool — it's free, no signup, runs in your browser. the math mirrors the open-source trovex CLI, so you can check it. the number you get is your own, not ours."
- *"how is this different from just counting tokens?"* → "it's the before/after: what your agents burn rereading the repo to guess the right doc, versus serving one canonical doc per query. ~60% on our repos; yours will differ."
- *"does it phone home?"* → "no. the calculator is client-side; nothing leaves your browser."

**Cross-post:** hand the social cross-post to social-lead (their lane); don't write social copy here. One low-key "we listed trovex's free token-cost tools on DevHunt" is enough; link second.

**Success read:** judge it on the indexed page + referral over weeks, not the day-one rank (#8). A quiet day-one is not a dead listing.

### 2.2 AI-tool directories (the agent-token angle)

These index AI/LLM tools; "coding agent token cost" fits the search. Some are big enough to drive real traffic.

| Directory | URL | Method | Free? | Notes / **VERIFY** |
|---|---|---|---|---|
| **There's An AI For That** | `theresanaiforthat.com` | Submit form | Yes + paid skip | Largest AI-tool directory. Free submit joins a review queue; paid fast-track exists — **don't pay**. Tag as a developer / coding AI tool. **VERIFY** the free submit path still exists. |
| **Futurepedia** | `futurepedia.io` | Submit form | Yes (free tier) | Broad AI directory. **VERIFY** whether a free listing is still offered (it has shifted toward paid — skip if free is gone). |
| **Future Tools** | `futuretools.io` | Submit form | Yes | Curated AI tools. Submit `/savings`; expect editorial review. **VERIFY** submit link. |
| **Toolify** | `toolify.ai` | Submit form | Yes | Large AI tool index. **VERIFY** free vs. paid placement. |

**Relevance gate (apply before submitting any AI directory):** these lean toward consumer/generative-AI tools. `/savings` and `/audit` are *developer* tools about agent cost — list them only where a "developer tools" or "AI for coding / DevOps" category genuinely exists. If the directory has no dev category, skip it rather than mis-file (a mis-filed listing is spam and won't convert).

**Checklist (human, per directory):**
- [ ] Confirm a developer / coding-AI category exists; if not, skip.
- [ ] Submit via the **free** path only; never the paid fast-track.
- [ ] §1 copy + §3 tagged URL + screenshot; pricing = **Free**.
- [ ] Log it for the §5 sheet.

### 2.3 Software / alternatives directories (broad — optional, VERIFY fit)

Broader reach but a looser fit; only worth it if they accept a free standalone web tool (some are SaaS-only).

| Directory | URL | Method | Notes / **VERIFY** |
|---|---|---|---|
| **AlternativeTo** | `alternativeto.net` | Account → add application | Can list trovex as a free alternative to repomix / a CLAUDE.md-style setup. **VERIFY** it accepts a free web tool vs. only installable apps; this may fit the trovex *product* better than the free tools. |
| **SaaSHub** | `saashub.com` | Submit form | Software/alternatives index. **VERIFY** it takes a free no-signup tool. |
| **OpenAlternative** | `openalternative.co` | GitHub PR / submit | OSS-directory; better fit for the trovex *product* (AGPL repo) than the standalone calculators — consider routing this one to the MCP-registry / product kit instead. **VERIFY** scope before using here. |

**Checklist (human):**
- [ ] Confirm the directory accepts a free standalone tool (not SaaS-only) before submitting.
- [ ] For OpenAlternative / AlternativeTo, decide whether the *product* (repo) or a *tool* (URL) is the better listing — don't double-list the same thing two ways.
- [ ] §1 copy + §3 tagged URL; log for §5.

---

## 3. UTM scheme — tagged outbound links

Each directory link carries UTMs so directory-referred sessions show in analytics, separate from the `/savings` share loop (which already uses `utm_medium=referral&utm_campaign=savings-calculator`). Directory listings are an *acquisition* channel, so:

```
?utm_source=<directory-slug>&utm_medium=tool-directory&utm_campaign=free-tools
```

> **Flag → analytics-lead:** add these directory slugs to the `utm_source` → channel map (alongside `mcp-registry`, `newsletter` → referral) so `tool-directory` sessions attribute cleanly. Until mapped, the medium still shows as a distinct referrer in Plausible. (See the analytics source-map memory.)

| Directory | utm_source slug | `/savings` link to paste | `/audit` link to paste |
|---|---|---|---|
| DevHunt | `devhunt` | `https://trovex.dev/savings?utm_source=devhunt&utm_medium=tool-directory&utm_campaign=free-tools` | `https://trovex.dev/audit?utm_source=devhunt&utm_medium=tool-directory&utm_campaign=free-tools` |
| Uneed | `uneed` | `https://trovex.dev/savings?utm_source=uneed&utm_medium=tool-directory&utm_campaign=free-tools` | `https://trovex.dev/audit?utm_source=uneed&utm_medium=tool-directory&utm_campaign=free-tools` |
| Fazier | `fazier` | `https://trovex.dev/savings?utm_source=fazier&utm_medium=tool-directory&utm_campaign=free-tools` | `https://trovex.dev/audit?utm_source=fazier&utm_medium=tool-directory&utm_campaign=free-tools` |
| Microlaunch | `microlaunch` | `https://trovex.dev/savings?utm_source=microlaunch&utm_medium=tool-directory&utm_campaign=free-tools` | `https://trovex.dev/audit?utm_source=microlaunch&utm_medium=tool-directory&utm_campaign=free-tools` |
| Peerlist | `peerlist` | `https://trovex.dev/savings?utm_source=peerlist&utm_medium=tool-directory&utm_campaign=free-tools` | `https://trovex.dev/audit?utm_source=peerlist&utm_medium=tool-directory&utm_campaign=free-tools` |
| There's An AI For That | `theresanaiforthat` | `https://trovex.dev/savings?utm_source=theresanaiforthat&utm_medium=tool-directory&utm_campaign=free-tools` | `https://trovex.dev/audit?utm_source=theresanaiforthat&utm_medium=tool-directory&utm_campaign=free-tools` |
| Futurepedia | `futurepedia` | `https://trovex.dev/savings?utm_source=futurepedia&utm_medium=tool-directory&utm_campaign=free-tools` | `https://trovex.dev/audit?utm_source=futurepedia&utm_medium=tool-directory&utm_campaign=free-tools` |
| Future Tools | `futuretools` | `https://trovex.dev/savings?utm_source=futuretools&utm_medium=tool-directory&utm_campaign=free-tools` | `https://trovex.dev/audit?utm_source=futuretools&utm_medium=tool-directory&utm_campaign=free-tools` |
| Toolify | `toolify` | `https://trovex.dev/savings?utm_source=toolify&utm_medium=tool-directory&utm_campaign=free-tools` | `https://trovex.dev/audit?utm_source=toolify&utm_medium=tool-directory&utm_campaign=free-tools` |
| AlternativeTo | `alternativeto` | `https://trovex.dev/savings?utm_source=alternativeto&utm_medium=tool-directory&utm_campaign=free-tools` | `https://trovex.dev/audit?utm_source=alternativeto&utm_medium=tool-directory&utm_campaign=free-tools` |
| SaaSHub | `saashub` | `https://trovex.dev/savings?utm_source=saashub&utm_medium=tool-directory&utm_campaign=free-tools` | `https://trovex.dev/audit?utm_source=saashub&utm_medium=tool-directory&utm_campaign=free-tools` |

Note: some directories strip query strings or pull the URL from a preview fetch. Where a free-text URL field exists, paste the tagged link; where it doesn't survive, the plain referrer still shows in Plausible. Never add a trailing slash — `trovex.dev/savings/` and `trovex.dev/audit/` 404; the `?utm_…` goes straight after the path.

---

## 4. Voice and honesty QA (applies to every listing above)

- [ ] Lowercase `trovex` everywhere in prose.
- [ ] No banned words: revolutionary, seamless, supercharge, unlock, "AI-powered"; no superlatives (fastest / first / best).
- [ ] The real ~60% number only, framed as *at the calculator's defaults / on our repos* — the tool makes the reader produce their own number. No fabricated logos, testimonials, user counts, or stars (public beta).
- [ ] No company name in brand prose. Only org identifier is the GitHub URL.
- [ ] Consulting stays off the listings entirely — the low-key "working with a team?" door lives on the tool page, not in the directory copy.
- [ ] Pricing = **Free** on every listing; never submit via a paid fast-track.
- [ ] Relevance gate honoured: skip any directory with no genuine developer / coding-AI category rather than mis-filing.
- [ ] Both tool URLs are slash-less and resolve before submitting.

---

## 5. Handoff summary (for the human who fires these)

1. **No eng blocker** — both tools are live and free; this is a paste-and-submit pass, unlike the MCP-registry kit.
2. **Submit order:** dev-tool launch directories (§2.1) → AI-tool directories (§2.2, relevance-gated) → software/alternatives (§2.3, fit-gated).
3. **Lead with `/savings`** (cleaner tool category); add `/audit` as a second tool where a maker profile allows it.
4. **Free path only** — never pay for a fast-track or placement.
5. **Track every submission** (directory, URL, date, live y/n) in a sheet and hand it to analytics-lead; ask analytics-lead to add the `tool-directory` slugs to the source map.
6. **Read the payoff as evergreen.** A free-tool directory listing is an SEO and backlink asset, not a launch-day event. A DevHunt page is indexed by Google, and a winning listing stays on the homepage shortlist for months, so the return is slow indexed traffic plus a permanent backlink, measured over weeks. Tell analytics-lead to read `tool-directory` sessions as a compounding line, not a day-one chart. Don't write a listing off because the first day was quiet.
7. **Reciprocal "featured-on" badge (optional, low effort).** Where a directory hands you a "featured on X" badge, the human can drop it in the `/savings` or `/audit` footer. It's a cheap two-way backlink, the same durable-backlink family as the savings README badge (Variant F, receipt-variants doc `d488d8cd`).

### Things flagged VERIFY
- The current free submit path for There's An AI For That, Futurepedia (free tier may be gone), Future Tools, Toolify (§2.2).
- Exact submit forms / categories for DevHunt, Fazier, Microlaunch, Peerlist (§2.1).
- Whether AlternativeTo / SaaSHub / OpenAlternative accept a free standalone web tool, and whether the trovex *product* (repo) is the better listing there than the free tools (§2.3).
- analytics-lead confirms the `tool-directory` medium + directory slugs in the `utm_source` map (§3).

*All copy and checklists above are drafts. Nothing has been submitted to any directory.*
