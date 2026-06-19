# wrai.th — launch gallery asset-spec (for design)

**Status:** DRAFT / spec only. Design produces the assets; a human uses them at launch. Nothing posted live.
**Owner:** launch-lead → **hand-off:** design-lead · **Reviewed against:** wraith-kit.md §A4, product-hunt.md §A4, voice, synergix-wraith-url-exception
**Purpose:** the LAST thing gating the wrai.th one-shots (Show HN / Product Hunt). Once design builds from this
spec, the one-shots need only owner go.

> **Brand note (read first):** this is **wrai.th's own identity, NOT tsukumo.** Do NOT use the agency acid
> `#c8ff00` here. Pull wrai.th's palette/wordmark from its live README + site (design confirms the canonical
> wrai.th brand before producing). Lowercase wordmark `wrai.th` everywhere. No "Synergix" in any pixel — the
> repo URL is the only place that string may appear. Honesty gate: **every screen is a real run** — no
> fabricated metrics, logos, dashboards, or "trusted by." If a screen isn't real yet, capture it from the
> running app before producing the slide.

---

## 0. What's needed (asset manifest + dimensions)

| Asset | Dimensions / format | Used for | Count |
|---|---|---|---|
| Gallery images | **1270×760 px**, PNG (PH gallery standard; first = thumbnail) | Product Hunt gallery | 5 (+ optional) |
| Optional demo video | ≤30s, MP4/loop, 1270×760 or 16:9 | PH gallery slide 0 | 0–1 |
| Product thumbnail / logo | **240×240 px**, PNG, transparent ok | PH listing thumbnail | 1 |
| Social / OG card | **1200×630 px**, PNG | Show HN link unfurl + X/LinkedIn/Slack shares of the repo | 1 |

> Show HN itself shows no gallery (text + repo link), but the **OG card** renders when the repo/link is shared
> anywhere — so it's part of this set. PH is where the gallery does the work.

---

## 1. Gallery slides (exact order + on-slide copy + what's shown)

On-slide copy is **verbatim** — short, high-contrast, legible at thumbnail size. Each slide = one idea.
Visuals are **real captures** from the running app (dashboard at `/v2/`, relay on localhost:8090).

### Slide 1 — HOOK (this is also the PH thumbnail; must read in ~2s)
- **On-slide copy:** `mission control for your AI agent fleet`
- **Shows:** the `/v2/` dashboard — several agents listed live + their tasks. The hero screen.
- **Layout:** dashboard screenshot dominant; one-line caption bottom or top; `wrai.th` wordmark small corner.
- **Why:** widest-comprehension frame; the dashboard is the "oh, I get it" image.

### Slide 2 — COORDINATION (the depth)
- **On-slide copy:** `agents that message each other + share one task board`
- **Shows:** inter-agent messaging + the shared task board (claim → start → complete) across 2–3 agents.
- **Layout:** split or annotated screenshot; arrows showing a task claimed by one agent, a message to another.

### Slide 3 — MEMORY (the differentiator)
- **On-slide copy:** `persistent memory that survives /clear`
- **Shows:** the shared memory store agents read/write; context surviving across agents/sessions.
- **Layout:** before/after or a memory-entry view; make "survives /clear" concrete (e.g. a recalled fact).

### Slide 4 — HOW IT WORKS (10s read)
- **On-slide copy:** `register agents → they coordinate over MCP → one dashboard`
- **Shows:** a simple 3-step diagram (not a screenshot). MCP-native; any client plugs in.
- **Layout:** clean 3-node flow; small line: `works with Claude Code · Cursor · Windsurf`.

### Slide 5 — TRUST CLOSE
- **On-slide copy:** `one Go binary · one SQLite file · 58 MCP tools · 100% local · AGPL`
- **Shows:** minimal — the install line + the facts. No screenshot needed; typographic.
- **Layout:** the facts as a tight list; `curl … install.sh | bash` shown; repo URL footer.

### Slide 0 — OPTIONAL 30s video (strongest PH asset if time allows)
- **Content:** spin up 2–3 agents → watch them claim tasks + exchange a message + share memory, live.
- **Note:** real screen capture only. If it can't be real + clean by launch, skip it — a fake demo is worse
  than none.

---

## 2. Product thumbnail / logo (240×240)
- wrai.th wordmark/mark on the brand background. Legible at small size. No tagline (too small). Confirm the
  canonical mark with design / the live README.

---

## 3. Social / OG card (1200×630)
- **Headline:** `wrai.th — mission control for your AI agent fleet`
- **Subline:** `memory · messaging · tasks · one dashboard. local, open source.`
- **Visual:** a clean crop of the `/v2/` dashboard or the brand mark; readable at small unfurl size.
- **No** company name, no fabricated stats. wrai.th brand, lowercase wordmark.

---

## 4. Copy bank (so design doesn't rewrite — use these verbatim)
- Tagline (≤60, PH limit): `Run a fleet of AI coding agents from one control plane` (54)
- One-liner: `mission control for your AI agent fleet — memory, messaging, tasks`
- Facts (true, reuse anywhere): `v1.0 stable · one Go binary · one SQLite file · 58 MCP tools · 100% local, no telemetry · AGPL · MCP-native (Claude Code/Cursor/Windsurf)`
- Install: `curl -fsSL https://raw.githubusercontent.com/Synergix-lab/WRAI.TH/main/install.sh | bash`
- Repo: `github.com/Synergix-lab/WRAI.TH`

---

## 5. Handoff checklist (design → launch-lead → owner)
- [ ] design confirms the canonical wrai.th brand (palette + wordmark) from the live README/site (NOT tsukumo acid).
- [ ] 5 gallery images @ 1270×760, slide 1 doubles as thumbnail, real screens only.
- [ ] 240×240 product thumbnail + 1200×630 OG card.
- [ ] (Optional) ≤30s real demo capture.
- [ ] launch-lead drops the finished assets into the product-hunt.md §A4 slot + notes the OG card on show-hn.md.
- [ ] Owner fires the one-shots (separate days; per launch-day sequence). Nothing posted by an agent.

*All copy/specs above are a draft for a human + design to execute. Nothing has been posted or submitted.*
