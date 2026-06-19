# Suite + trovex — public-launch un-freeze checklist (DRAFT)

**Status:** DRAFT / runbook. Do NOT fire until cmo signals go. Today: staged, nothing live.
**Owner:** launch-lead · **Reviewed against:** mission, gtm-model, public-launch-blockers, mcp-registries.md, wraith-kit.md, suite-positioning.md, voice, no-synergix-mention
**Use:** the ordered steps for the COORDINATED suite launch + the trovex public-launch flip. Each `[ ]` has an owner.

> **Copy state (audited 2026-06-19, launch-lead):** the public-launch kit is **already written in public
> mode** — show-hn.md, product-hunt.md, mcp-registries.md, registry-variants.md, faq-bank.md, outreach.md,
> community-plan.md, free-tool-spec.md all link the **repo** + use real install (`uvx trovex` / `git clone`),
> with trovex's tracks gated on *repo+PyPI public*, not on a waitlist. The beta-waitlist framing lives ONLY
> in the separate `beta-*` driver files (beta-reframe / beta-sequence / beta-onboarding / beta-outreach),
> which are this phase's waitlist drivers — NOT reframed copies of the public assets. So **there is no
> beta→public copy-flip to do on the public kit** (an earlier draft of step 4 implied there was — corrected
> below). The real launch-day copy work is: fill the `[bracketed]` founder/eng technical answers, fold real
> beta proof once it exists, and retire the `beta-*` drivers. See the per-asset audit in step 4.

---

## 0. Coordinated suite-launch plan (cmo decision — the master sequence)

**Decision (cmo):** do NOT fire piecemeal. wrai.th is public + stable (our widest top-of-funnel), but firing
the one-shots (Show HN / Product Hunt) before the funnel destination exists wastes them. Launch the suite
**once, coordinated.** Owner fires the one-shots; cmo signals go.

### Launch-readiness gate (all true before any one-shot)
- [ ] **tsukumo.ch live** — the agency site (the funnel destination) is up. Without it, launch traffic has nowhere to convert.
- [ ] **trovex waitlist working** — `/api/waitlist` off 503 (storage env set by owner). Beta capture works.
- [ ] **Design assets ready** — OG cards + galleries for wrai.th (+ trovex when public) in the locked brand.
- [ ] **cmo signals go** + owner available to fire the one-shots.

### What can go FIRST (reversible / compounding — ahead of the gate, when owner fires)
- [ ] **wrai.th registries** — MCP Official + Glama + mcp.so + Go-ecosystem (pkg.go.dev, awesome-go). Reversible,
      compounding discovery; safe to seed before the big day. (wraith-kit.md §2)
- [ ] **trovex registries** — only after the trovex repo is public + on PyPI (trovex track below). Reversible.

### Coordinated launch day (once the gate is green — owner fires)
- [ ] Registries already live + propagating (above).
- [ ] **wrai.th Show HN** — the lead one-shot (widest TOF). Links repo; cross-links the suite + tsukumo. (wraith-kit.md §1)
- [ ] **Product Hunt** (wrai.th or the suite) — separate day, not stacked. (product-hunt.md pattern)
- [ ] **Suite story everywhere** — each tool's copy cross-references the suite per suite-positioning.md;
      trovex framed as the context layer that pairs with wrai.th, not a rival.
- [ ] **Community + newsletters** — value-first, spaced (community-plan.md, outreach.md), pointing at the live funnel.
- [ ] yoru: mention only once it's public; until then no claims (suite-positioning.md).

### Order rationale
Registries (reversible, compounding) → seed early. One-shots (HN/PH, non-repeatable) → fire only when
tsukumo.ch + waitlist + assets are ready, so the click has somewhere to land. Trovex's public flip (below)
slots into this once its beta produces proof + the repo goes public.

---

## TROVEX TRACK — beta → public flip (sub-sequence of the coordinated launch)

## 0a. trovex go-decision gate (cmo) — don't start until all true

- [ ] Beta produced real proof: ≥a few activated testers with real savings numbers + ≥1 permissioned quote.
- [ ] The tool is solid enough for cold installs (a stranger can `index` + `serve` without hand-holding).
- [ ] cmo explicitly lifts the trovex public hold. Until then the trovex steps stay frozen.

---

## 1. Make it installable + public (eng) — the hard blockers

Per public-launch-blockers memory:
- [ ] Publish `trovex` to **PyPI** (v matches server.json). Confirm `uvx trovex serve` runs from the published wheel.
- [ ] Add the ownership marker to the package long-description/README: `mcp-name: io.github.synergix-lab/trovex`.
- [ ] Flip the **repo public** (github.com/Synergix-lab/trovex). Verify README, license, issues are presentable.
- [ ] Confirm no secrets / internal hosts in git history before going public (trovex.prod.synergix.ch etc.).
- [ ] Configure PyPI **Trusted Publishing** for the repo + `publish-mcp.yml` workflow.

## 2. Publish to the MCP Official Registry (launch-lead + eng)

- [ ] Merge **PR #52** (`.github/workflows/publish-mcp.yml`) — the non-interactive OIDC publish path.
- [ ] `mcp-publisher validate ./server.json` passes (it already does).
- [ ] Push tag `v0.11.0` (or current) → workflow builds → PyPI → `mcp-publisher login github-oidc` → publish.
- [ ] Confirm listing: `https://registry.modelcontextprotocol.io/v0/servers?search=trovex`.
- [ ] Verify propagation over the following week: PulseMCP (auto), Docker, GitHub MCP Registry (VS Code), Anthropic.

## 3. Manual registry submits (human, after Official is live) — see mcp-registries.md + registry-variants.md

- [ ] Glama (web form; build-validated) → grab the badge → add to README.
- [ ] awesome-mcp-servers (PR; needs Glama listing first).
- [ ] mcp.so (web form + GitHub login).
- [ ] Smithery — only if a brand-neutral hosted HTTP endpoint exists (`mcp.trovex.dev`), else skip.
- [ ] Secondary directories (batch, same master copy).

## 4. Launch-day copy-readiness pass (launch-lead)

**Not a beta→public rewrite** — the public kit is already public-mode (see Copy state above). This is the
short final pass: fill the bracketed gaps, fold proof, retire the beta drivers, run the gates.

**Per-asset audit (2026-06-19) — verified mode + the only remaining work:**

| Asset | Current mode | Remaining launch-day work |
|---|---|---|
| show-hn.md | public (repo link, `uvx`/clone, ~60% measured) | Fill `[bracketed]` founder/eng answers in §A3/§A5 + §B; fold beta proof into §B3 |
| product-hunt.md | public (cold-install line, repo) | Fill bracketed gallery/maker copy; gallery from real runs + beta proof |
| mcp-registries.md / registry-variants.md | public (install = `uv run` from source today) | Swap install line to `uvx trovex` once PyPI is live (step 1); verify config |
| faq-bank.md | public (open-source / "installs in a minute") | Add real ~60% number + permissioned quote to the "does it really save 60%" answer |
| outreach.md | public (sends devs who install/index) | Use the public note (not the beta-tease); fold proof line where it fits |
| community-plan.md | public (real installs/indexes) | Use the public seed drafts, NOT the `beta-reframe.md §3` waitlist variants |
| free-tool-spec.md | public (install pitch off real number) | No copy flip; ship per its own scope when prioritised |

- [ ] Fill the `[bracketed]` founder/eng technical answers in show-hn.md (A3/A5, B3/B4) + product-hunt.md.
      These need real product internals — launch-lead can't fabricate them; owner/eng supplies.
- [ ] Fold **beta proof** in once it exists (step 0a gate): real savings numbers + ≥1 permissioned quote →
      PH gallery + HN/PH first comments + the FAQ "does it really save 60%" answer (real tester data, not my-repos).
- [ ] Swap any source-install line (`uv run trovex` from clone) → published `uvx trovex` after PyPI is live (step 1).
- [ ] **Retire the `beta-*` drivers:** stop the waitlist tease; switch community/outreach to the already-public
      versions (community-plan.md / outreach.md), not the `beta-reframe.md` waitlist variants.
- [ ] Re-run the **anti-ai-slop** gate on every asset that gets edited.
- [ ] Confirm no "Synergix" in any public prose (repo URL org identifier is the allowed exception); brand
      green `#22c55e` on any visual asset.

## 5. Fire the public launch (human; sequence + timing)

Order matters (registries first = the shelf is ready when the traffic hits):
- [ ] Registries live (steps 2–3) and propagating.
- [ ] **Show HN** — one-shot, weekday AM ET, founder free 2–3h to answer. Paste first comment immediately.
      No booster comments. (show-hn.md)
- [ ] **Product Hunt** — one-shot, 12:01am PT, gallery from real runs, maker comment ready. (product-hunt.md)
      Don't stack HN + PH the same day; space them.
- [ ] Community + outreach: switch beta drafts → public versions, keep the value-first ratio. (community-plan.md, outreach.md)
- [ ] Newsletters: send the public-version notes (outreach.md), 1:1, spaced.

## 6. Measure (hand to analytics-lead)

- [ ] Track installs/index runs + registry referrals + HN/PH → activation (savings number seen), not vanity rank.
- [ ] Watch the consulting-lead door (north star), not just stars.

---

## Quick blocker summary (so nobody re-discovers it)

- PyPI 404 today → must publish + add `mcp-name` marker. [step 1]
- mcp-publisher auth: OIDC via CI only (PR #52); interactive device-code won't run headless. [step 2]
- Repo private today → flip public + history scrub before any registry/HN/PH. [step 1]
- Public kit is ALREADY public-mode (repo + install) — no beta→public flip needed; only fill brackets +
  fold proof + retire the `beta-*` drivers. Beta-waitlist copy is isolated in `beta-*` files only. [step 4]

*This is a held runbook. Nothing here runs until cmo lifts the public hold.*
