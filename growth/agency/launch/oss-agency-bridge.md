# OSS suite → tsukumo bridge copy (DRAFT, ready-to-PR per repo)

**Status:** DRAFT / copy. Nothing applied live. Per-repo blocks for owner/fullstack to PR into each suite repo.
**Owner:** launch-lead · **Reviewed against:** suite-positioning.md, voice, no-synergix-mention, pricing-policy, north-star, funnel-event-taxonomy, utm-taxonomy-contract, agency-positioning
**Builds on:** the suite cross-link kit (#119) + suite-positioning.md cross-reference rules.

> Goal (cro idea, cmo = GO): a tight, **low-key** "built and run by the team behind tsukumo" block + a one-liner footer for the trovex / WRAI.TH / yoru READMEs and their landing-page footers, linking the suite → tsukumo so a dev who likes the tools can find the consulting. Footnote, not a pitch.

---

## 0. Gates + rules (read first)

- **GATE — tsukumo.ch must be live** before any of these ship. Per suite-positioning cross-ref rules, the consulting line names tsukumo *only once the site exists*. Until then: hold (or use the no-name variant in §5).
- **No hard sell.** One quiet block + one footer line per surface. The OSS surface is not a sales page (voice, north-star).
- **Respect each repo's own voice** — trovex (plain/terminal-restraint), WRAI.TH (its orchestration voice), yoru (observability). Blocks below are tuned per repo; don't homogenize.
- **Lowercase wordmarks** (`trovex`, `wrai.th`, `yoru`, `tsukumo`). **No "Synergix" in prose.**
- **No fabricated proof.** No metrics/quotes here — it's a bridge, not a claim.
- **yoru is not public yet** — prepare its block but **apply only when yoru ships** (suite-positioning honesty rule).

---

## 1. Attribution spec (how the click is tagged + measured)

Two surfaces per tool, with an important engineering distinction:

| Surface | Link tag | Event |
|---|---|---|
| **GitHub README** (static markdown) | UTM on the link only — **GitHub can't run JS**, so no event fires here. Attribution = tsukumo.ch reads the `utm_*` on arrival. | none (static) |
| **Web property footer** (trovex.dev, wrai.th site, yoru site) | same UTM link **+** fire `suite_to_agency_click` onClick (JS available). | `suite_to_agency_click{ from_tool, link_location }` |

**UTM (cmo-specified, cross-property suite→tsukumo):**
```
https://tsukumo.ch/?utm_source=<tool>&utm_medium=oss-suite&utm_campaign=consulting
```
- `<tool>` = `wraith` | `trovex` | `yoru` (the source tool).
- `utm_medium=oss-suite`, `utm_campaign=consulting` (fixed for this bridge).
- Add `utm_content=readme` vs `utm_content=site-footer` to split the two surfaces.

> ⚠️ **Reconciliation flag for analytics-lead:** the canonical `utm-convention.md` closed lists govern links to **trovex.dev**. These links point to **tsukumo.ch** (a different property), so its taxonomy applies — and `utm_source=wraith|trovex|yoru` + `utm_medium=oss-suite` are NOT in the trovex.dev closed list by design. Please ratify these values on the **tsukumo** side (its `analytics.ts` / consulting-funnel.md) so `suite_to_agency_click` + `assessment_request{source:suite}` line up. North star = consulting leads where source=suite (utm-taxonomy-contract).

---

## 2. trovex README block

Voice: plain, cost-framed, terminal-restraint. Place near the bottom (after usage), above the license.

```markdown
## Who builds this

trovex is built and run by the team behind **[tsukumo](https://tsukumo.ch/?utm_source=trovex&utm_medium=oss-suite&utm_campaign=consulting&utm_content=readme)** — we help engineering teams run AI coding agents in production. trovex is one of the tools we use ourselves; it's free and open source (AGPL core, MIT CLI).

It pairs with the rest of the suite: **wrai.th** (orchestration) and **yoru** (observability).

> Running agents across a team and want a hand? That's what we do — [talk to us](https://tsukumo.ch/?utm_source=trovex&utm_medium=oss-suite&utm_campaign=consulting&utm_content=readme).
```

**One-liner footer:**
```markdown
*Built by the team behind [tsukumo](https://tsukumo.ch/?utm_source=trovex&utm_medium=oss-suite&utm_campaign=consulting&utm_content=footer) — consulting for teams running AI coding agents.*
```

---

## 3. WRAI.TH README block

Voice: orchestration / "mission control," a bit bolder. WRAI.TH is the widest TOF (public, v1.0) — keep the same low-key consulting footnote.

```markdown
## Who builds this

wrai.th is built and run by the team behind **[tsukumo](https://tsukumo.ch/?utm_source=wraith&utm_medium=oss-suite&utm_campaign=consulting&utm_content=readme)** — we help engineering teams run fleets of AI coding agents in production. wrai.th is the orchestration layer we run ourselves; free and open source (AGPL).

Pairs with **trovex** (one canonical doc per query, fewer tokens) and **yoru** (see what the fleet did).

> Standing up an agent fleet across a team? We do that hands-on — [talk to us](https://tsukumo.ch/?utm_source=wraith&utm_medium=oss-suite&utm_campaign=consulting&utm_content=readme).
```

**One-liner footer:**
```markdown
*Built by the team behind [tsukumo](https://tsukumo.ch/?utm_source=wraith&utm_medium=oss-suite&utm_campaign=consulting&utm_content=footer) — consulting for teams running AI agent fleets.*
```

---

## 4. yoru README block (APPLY ONLY WHEN yoru IS PUBLIC)

Voice: observability. Hold until yoru ships (suite-positioning honesty rule).

```markdown
## Who builds this

yoru is built and run by the team behind **[tsukumo](https://tsukumo.ch/?utm_source=yoru&utm_medium=oss-suite&utm_campaign=consulting&utm_content=readme)** — we help engineering teams run AI coding agents in production. yoru is how we see what our own agents did; free and open source (AGPL).

Pairs with **wrai.th** (orchestration) and **trovex** (context, fewer tokens).

> Running agents in production and flying blind? That's our work — [talk to us](https://tsukumo.ch/?utm_source=yoru&utm_medium=oss-suite&utm_campaign=consulting&utm_content=readme).
```

**One-liner footer:**
```markdown
*Built by the team behind [tsukumo](https://tsukumo.ch/?utm_source=yoru&utm_medium=oss-suite&utm_campaign=consulting&utm_content=footer) — consulting for teams running AI coding agents.*
```

---

## 5. No-name fallback (use ONLY if tsukumo.ch is NOT live yet)

If a README must ship before tsukumo.ch is live, do **not** name tsukumo or link a dead site. Use a holding line, swap in the §2–4 block when the site lands:

```markdown
*Built by a team that helps companies run AI coding agents in production. (Consulting details coming soon.)*
```

> Prefer to **hold** the bridge entirely until the site is live — a "coming soon" is weaker than waiting. This fallback is only for a repo that's already public and needs *something*.

---

## 6. Web-footer variant (trovex.dev / wrai.th site / yoru site — fires the event)

Same copy as the README footer, but as a site footer where JS runs. Hand to fullstack/frontend:

- Render the one-liner footer (§2–4) in the site footer.
- The tsukumo link carries the same UTM but with `utm_content=site-footer`.
- **onClick:** fire `suite_to_agency_click{ from_tool: '<tool>', link_location: 'site-footer' }` (funnel-event-taxonomy) before navigation.
- (Optional) a matching block in the landing page's "who builds this" / about section with `utm_content=about`.

---

## 7. Application checklist (owner / fullstack, per repo)

- [ ] **Confirm tsukumo.ch is live** (gate). If not → hold, or §5 fallback only for already-public repos.
- [ ] **trovex repo:** add §2 block + footer to README. (suite repo PR — not this growth repo.)
- [ ] **WRAI.TH repo:** add §3 block + footer to README.
- [ ] **yoru repo:** add §4 block — **only when yoru is public.**
- [ ] **Web footers:** apply §6 to trovex.dev (+ wrai.th / yoru sites when live); wire `suite_to_agency_click` + UTM `utm_content=site-footer`.
- [ ] **analytics-lead:** ratify the tsukumo-side `utm_source` values (§1 flag) so the suite→consulting funnel reconciles.
- [ ] Verify each link resolves to tsukumo.ch with the right `utm_*`; verify the event fires on the web footers (not the README).

## 8. Voice / brand QA

- [ ] Low-key footnote, no hard sell, one block + one footer per surface.
- [ ] Each block matches its repo's voice (trovex plain / wrai.th orchestration / yoru observability).
- [ ] lowercase wordmarks; **no "Synergix"** in prose; no fabricated proof.
- [ ] tsukumo named only when tsukumo.ch is live (else §5 / hold).
- [ ] No prices anywhere (pricing-policy).

*All copy above is a draft. Nothing has been applied to any repo or site.*
