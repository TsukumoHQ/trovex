# Free tool — build-ready brief: standalone agent token-cost calculator (DRAFT)

**Status:** DRAFT / build-ready brief + final landing copy. No build, no deploy — for cmo/eng to scope + build.
**Owner:** launch-lead · **Reviewed against:** free-tool-spec.md, voice, no-synergix-mention, north-star, utm-launch-link-sheet.md, funnel-event-taxonomy
**Builds on:** `free-tool-spec.md` (the math model + funnel logic). This is the **build-ready** version: scope locked, the standalone framing, deploy, share/SEO hooks, final copy, events, gates.

---

## 0. What's different from the spec — and from cro's `/context-cost`

- `free-tool-spec.md` proposed `trovex.dev/savings` (a route on the main landing). **cmo's bet #2 = make it STANDALONE.**
- **cro owns `/context-cost`** — the on-landing CRO calculator whose job is to convert landing visitors. **Do not duplicate or compete with it.**
- **This tool is a discovery magnet:** its own discoverable, shareable surface optimized for search + linking + dropping in a thread — top-of-funnel, not landing-conversion. It points *into* the funnel (repo + waitlist + the low-key consulting door); it doesn't try to win the landing's conversion.

**The delineation (give to cro to avoid overlap):**
| | cro's `/context-cost` | this standalone tool |
|---|---|---|
| Job | convert landing traffic | **acquire** new traffic (discovery) |
| Lives | on trovex.dev (landing route) | **own standalone surface** (see §1) |
| Optimized for | on-page conversion | **search + share** ("agent token cost calculator") |
| CTA weight | strong (it's the landing) | **low-key** (footnote to repo/waitlist) |

---

## 1. Standalone surface (the decision for cmo/eng)

Pick one (recommended first):
1. **A dedicated path optimized as its own indexable page** — e.g. `trovex.dev/tools/agent-token-cost` — built + meta'd to rank/share as a standalone tool, **separate from `/context-cost`** and not in the main nav as a CRO step. Cheapest; still "standalone" in SEO/share terms. *(recommended)*
2. **Own subdomain** — `calc.trovex.dev` or a dedicated micro-site. More "standalone," more setup; only if cmo wants a clearly separate property.
3. **Own repo + GitHub Pages** (`agent-token-cost`) — maximal standalone + an extra OSS surface, but splits maintenance.

> Recommend #1 unless cmo wants a distinct property. Whichever: it must be a **clean, single-purpose page** that reads as a tool, not a trovex ad — that's what makes it shareable + linkable.

---

## 2. Scope (locked v1 — keep it tiny, ~1–2 days)

- **Mode A only** (client-side sliders/fields → instant result). Mode B (paste/GitHub-tree) is v2 — out of scope now.
- Math model = `free-tool-spec.md §3` (don't re-derive). Every default labeled an editable assumption; **honest** — small doc set → "not much to save here."
- **No backend, no accounts, no email gate.** Result is free + instant. Shareable: encode inputs in the querystring so a result is linkable.
- Reuse the site's styles (coherent) but **no landing-CRO chrome** — it's a tool page, not a funnel step.

---

## 3. Final landing copy (passes anti-ai-slop — re-run before ship)

**H1:** `What do your coding agents spend rereading docs?`
**Sub:** `Estimate the tokens your agents burn rereading .md files each session — and what serving one canonical doc would save. Every assumption is editable. If the number's small, this tool will say so.`

**Result block:** big number (tokens + $/month saved) · the % · a "show the math" toggle revealing the `free-tool-spec §3` formula · one line: `An estimate from your inputs, not a measurement.`

**Below the result (low-key path — a footnote, not a wall):**
```
trovex measures the real number: it indexes your repo's markdown and serves your agent the one current
doc (path:line + freshness) instead of a reread, and shows the measured savings. Open source, runs on
your machine. → github.com/Synergix-lab/trovex
```
**Footer (the quiet consulting door, no company name):** `Running agents across a team? happy to talk.`

> Copy gate: lowercase `trovex`, no banned words, no hype, no company name, real framing. Re-run anti-ai-slop on the final page.

---

## 4. Share + SEO hooks (this is how a standalone tool earns discovery)

- **Querystring-encoded results** → "my repo would save $X/mo" links are shareable in the community venues (`venue-final-posts.md`) — a tool, not a pitch (low-spam).
- **Page SEO:** title/meta target real queries — "agent token cost calculator", "LLM context cost estimator", "coding agent token savings". Add `SoftwareApplication`/`WebApplication` + `FAQPage` JSON-LD (hand to geo-lead).
- **OG card** so shared links render well (design-lead).
- **GEO/AEO:** a clean, self-contained "how to estimate agent token cost" explainer on the page = citable by AI engines (community-participation-playbook §1).

---

## 5. Events (instrument from day 1 — hand to analytics-lead)

- `calc_run` (inputs hashed/bucketed, no PII), `calc_show_math`, `calc_repo_click`, `calc_consulting_click`, later `install_from_calc`.
- **Attribution:** the repo/waitlist links carry UTM per `utm-launch-link-sheet.md` (`utm_source=…&utm_content=calc-…`) so calc-driven activation shows up by source in the north-star report.
- Health check: does the calc actually feed activation? If runs don't convert to installs/waitlist, iterate or drop — don't keep a vanity toy.

---

## 6. Funnel fit + honesty (why it earns its keep)
- **Discovery:** independently searchable + linkable + shareable in-thread without being spam.
- **Activation bridge:** "you guessed $X — go see the real number on your repo" → cleaner install reason than a feature list.
- **North star:** a doc-heavy-team repo showing a big monthly number = the consulting-adjacent lead; the footer is the quiet door.
- **Where it won't help (state it):** tiny doc sets save little; a flattering-but-fake number poisons trust. Its whole value is being the honest version.

---

## 7. Handoff
- **cmo:** pick the standalone surface (§1); confirm it's distinct from cro's `/context-cost`; decide build slot (pairs with the community plan as a shareable asset).
- **eng/frontend:** build v1 (Mode A, client-side, querystring-shareable) per §2; reuse styles, no CRO chrome.
- **cro-lead:** align so this doesn't fight `/context-cost` (§0 table).
- **geo-lead:** JSON-LD + SEO meta (§4). **analytics-lead:** events + UTM (§5). **design-lead:** OG card.
- launch-lead: this brief + copy is ready; the build is eng's; nothing deploys without cmo's slot decision.

*Brief + copy only. Nothing built or deployed.*
