# trovex — launch gallery asset-spec (for design)

**Status:** DRAFT / spec only. **HOLD building until trovex flips public** (see below). A human captures real
screens; design composites; a human fires the one-shots. Nothing posted live.
**Owner:** launch-lead → **hand-off:** design-lead · **Reviewed against:** product-hunt.md §B4, show-hn.md §B, mcp-registries.md §1, wraith-gallery-asset-spec.md (sibling), voice, no-synergix-mention
**Purpose:** the production gallery spec for the trovex Show HN / Product Hunt one-shot, mirroring the wrai.th
spec (#203). Ready so that the moment trovex goes public, design builds and the one-shot needs only owner go.

> **HOLD gate (read first):** trovex is private beta. Its one-shots (show-hn.md §B, product-hunt.md §B) are
> FROZEN until: repo public + on PyPI, a stranger can `uvx trovex index/serve` cleanly, AND real beta proof
> exists (savings numbers + ≥1 permissioned quote). See unfreeze-checklist TROVEX TRACK. **Design: do not build
> these yet** — this spec is staged for the flip. The proof/savings slides MUST use a real run, captured then.

> **Brand note:** trovex's own identity — brand green **`#22c55e`** on a dark bg, lowercase wordmark `trovex`.
> NOT tsukumo acid `#c8ff00`, NOT wrai.th emerald `#4ade80`. No "Synergix" in any pixel (repo URL only).
> Honesty gate: every number + screen is a **real run** — no fabricated savings, dashboards, logos, or quotes.

---

## 0. Asset manifest + dimensions

| Asset | Dimensions / format | Used for | Count |
|---|---|---|---|
| Gallery images | **1270×760 px**, PNG (first = thumbnail) | Product Hunt gallery | 5 (+ optional) |
| Optional demo video | ≤30s, MP4/loop, 1270×760 | PH gallery slide 0 | 0–1 |
| Product thumbnail / logo | **240×240 px**, PNG | PH listing thumbnail | 1 |
| Social / OG card | **1200×630 px**, PNG | Show HN link unfurl + X/LinkedIn/Slack shares of the repo | 1 |

> The savings-receipt slide (slide 2) is the most persuasive asset trovex has — it's the proof. Build it from a
> real run; it's the whole pitch in one image.

---

## 1. Gallery slides (exact order + on-slide copy + what's shown)

On-slide copy is **verbatim** — short, legible at thumbnail size. Visuals are **real captures** from a running
trovex (the savings view, a `trovex(q)` result, the `/doc/{id}` reader).

### Slide 1 — HOOK (also the PH thumbnail; reads in ~2s)
- **On-slide copy:** `one current doc, not a repo reread`
- **Shows:** split before/after — left: an agent reading ~6 `.md` files, a token counter ticking up; right:
  trovex returning ONE `path:line` pointer + a green `canonical` freshness marker.
- **Layout:** clean split; the contrast (pile-of-files vs one-pointer) is the hook.

### Slide 2 — PROOF / THE SAVINGS RECEIPT (the differentiator)
- **On-slide copy:** `~60% fewer tokens per doc lookup — measured on your repo`
- **Shows:** the trovex savings view — would-have-read vs actual tokens, ~60% reduction. **Real run.**
- **Layout:** the receipt dominant; the number legible at thumbnail. No invented figure — capture from a real repo.

### Slide 3 — HOW IT WORKS (10s read)
- **On-slide copy:** `index your repo → agent asks trovex(q) → one doc + freshness`
- **Shows:** a simple 3-step diagram (not a screenshot).
- **Layout:** clean 3-node flow; small line: `local: SQLite + on-device embeddings, no cloud, no keys`.

### Slide 4 — DEPTH / SOURCE OF TRUTH
- **On-slide copy:** `one shared store, so agents + teammates stop re-deriving`
- **Shows:** the write path — two agents reading/writing one trovex store (trovex_write / trovex_read).
- **Layout:** annotated; make "one source of truth across agents" concrete.

### Slide 5 — TRUST CLOSE
- **On-slide copy:** `runs on your machine · SQLite + on-device embeddings · no cloud/keys · AGPL core / MIT CLI`
- **Shows:** minimal/typographic — the install line + the facts. `uvx trovex index <repo>` shown; repo URL footer.

### Slide 0 — OPTIONAL ≤30s video
- **Content:** `trovex index` → an agent query → one-doc result → the savings view ticking the real number.
- **Note:** real capture only. If it can't be real + clean at flip, skip it.

---

## 2. Product thumbnail / logo (240×240)
- trovex wordmark/mark on the brand-green-on-dark background. Legible small. No tagline. Confirm canonical mark
  with design / the live README.

---

## 3. Social / OG card (1200×630)
- **Headline:** `trovex — one canonical doc for your coding agents`
- **Subline:** `~60% fewer tokens per lookup. local-first, open source.`
- **Visual:** the savings-receipt crop or the mark; readable at small unfurl size.
- **No** company name, no fabricated stats. trovex green, lowercase wordmark.

---

## 4. Copy bank (use verbatim — from show-hn §B / product-hunt §B / mcp-registries §1)
- Tagline (≤60, PH limit): `One canonical doc for your coding agents, ~60% fewer tokens` (57)
- One-liner: `indexes your repo's markdown and serves agents the one current doc, not a reread`
- Facts (true): `local-first · SQLite + on-device ONNX embeddings (fastembed) · no cloud, no API keys · AGPL core / MIT CLI · MCP-native`
- Proof: `~60% fewer tokens per .md lookup, measured; ships a savings view to check on your own repo` (repo-dependent — never a flat claim)
- Install (post-PyPI): `uvx trovex index <repo>` / `uvx trovex serve`
- Repo: `github.com/Synergix-lab/trovex`

---

## 5. Handoff checklist (at the trovex public flip)
- [ ] **GATE:** trovex repo public + PyPI live + cold `uvx trovex` runs + beta proof exists (unfreeze-checklist TROVEX TRACK).
- [ ] design confirms canonical trovex brand (green `#22c55e` + wordmark) from the live README.
- [ ] Capture real screens: the savings view (slide 2), a `trovex(q)` result (slide 1), the write-path/`/doc` reader (slide 4).
- [ ] 5 gallery images @1270×760 (slide 1 = thumbnail) + 240×240 thumb + 1200×630 OG card.
- [ ] (Optional) ≤30s real demo capture.
- [ ] launch-lead drops finished assets into product-hunt.md §B4 + notes the OG card on show-hn.md §B.
- [ ] Owner fires the one-shot (separate day from wrai.th's).

*All copy/specs above are a draft for a human + design to execute. Nothing has been posted or submitted.*
