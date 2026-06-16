# Directory listings — AI tool + agency directories submission plan (DRAFT)

**Status:** DRAFT / copy only. Nothing submitted live. A human runs each checklist; owner-gated.
**Owner:** launch-lead · **Reviewed against:** product-marketing-context.md, voice, no-synergix-mention, mcp-registries.md, agency-positioning, agency-icp
**Covers:** general AI/dev **tool** directories for trovex + the OSS suite (separate from the MCP-registry shelf, which lives in `mcp-registries.md`), and **agency** directories for the consulting business (tsukumo).

> Why this is separate from `mcp-registries.md`: registries are the *MCP app-store shelf* (high-intent, install-ready). The directories here are broader top-of-funnel — AI-tool aggregators and software-comparison sites for trovex, and agency/consulting directories for tsukumo. Lower install-intent each, but cheap, compounding discovery + GEO/AEO surface area (AI engines cite these aggregators).
>
> **Routing note:** the agency (tsukumo) lives in its own repo (`Synergix-lab/tsukumo`). The agency listing copy here is a **draft plan** for cmo/owner to route there — this PR ships the plan, not a tsukumo change.

---

## 0. Principles (read before submitting anything)

- **Quality over quantity.** A handful of reputable, traffic-real listings beat 50 SEO-spam farms. Spam directories can *hurt* (low-quality backlinks, scammy neighbors). The "skip these" list below is as important as the submit list.
- **Free first.** Submit the free, credible ones. Paid placements only if cmo decides the agency pipeline justifies it (Clutch/GoodFirms paid tiers) — flagged, not auto.
- **GEO/AEO value is real.** AI engines (ChatGPT, Perplexity, Google AI Overviews) cite aggregators like AlternativeTo / TAAFT / Clutch when asked "what's a tool/agency for X." Being listed = being citable. This is a discovery lever, not just a backlink.
- **No fabricated proof anywhere.** Pre-launch, zero customers → no invented user counts, ratings, or testimonials. Agency outcomes stay qualitative until the owner gives numbers (agency-proof).
- **Brand rules apply to every field.** Lowercase `trovex`; no "Synergix" in prose (only the unavoidable GitHub-org identifier); no banned words; real ~60% only.

---

## 1. trovex — canonical listing copy (reuse across all AI/tool directories)

*(Mirrors the master in `mcp-registries.md §1` — keep them in sync if either changes.)*

**Name:** `trovex`
**Category:** Developer tools / AI coding / context-memory infrastructure (MCP server + CLI)
**Tagline (≤60 chars):**
> One canonical doc for your coding agents — ~60% fewer tokens.

**Short (≤100 chars):**
> Indexes your repo's markdown and serves agents the one current doc, not a reread of the repo.

**One-paragraph:**
> Your coding agents reread `.md` files every session to guess which one is canonical, burning tokens
> each time. trovex indexes your repo's markdown and serves the single doc that answers a query — a
> `path:line` pointer with a freshness marker (canonical / stale / duplicate) — so the agent reads just
> the relevant section. Agents can also write what they learn back through one shared store, so every
> agent and teammate works from the same source of truth. Runs locally: SQLite + on-device ONNX
> embeddings, no cloud, no API keys. ~60% fewer tokens per lookup, with a dashboard that shows what you
> stopped spending.

**Tags:** `developer-tools`, `ai-coding`, `mcp`, `coding-agents`, `context`, `memory`, `token-efficiency`, `local-first`, `open-source`, `cli`, `python`, `claude-code`, `cursor`
**Pricing field:** Free / Open source (AGPL-3.0 core, MIT CLI)
**Links:** repo `github.com/Synergix-lab/trovex` · site `trovex.dev`
**Proof line (real only):** ~60% fewer tokens per doc lookup; a local savings dashboard shows would-have-read vs actual. No customers/testimonials yet — pre-launch.
**Assets:** reuse the screenshot set from `mcp-registries.md §1` (index finishing, savings receipt, single `path:line` result, rendered reader, square logo).

---

## 2. AI / developer tool directories — submit table

> Reputable + currently active in 2026. Free unless noted. Audience-fit graded for an OSS dev CLI. See §6 for what to skip.

| Directory | URL | Submission | Free/Paid | Fit + note |
|---|---|---|---|---|
| **Awesome lists (GitHub)** | github.com/topics/awesome-* | GitHub PR | Free | **Best fit.** Pure OSS-dev audience, high-trust durable backlinks. Target lists matching the niche (awesome-mcp-devtools, awesome-ai-coding, awesome-developer-tools). Clean, focused PR. |
| **AlternativeTo** | alternativeto.net | Web form (community-edited) | Free | **High value.** High-DR comparison SEO + AI-citation surface. Add trovex as an *alternative to* CLAUDE.md / repomix / context-hub to capture intent (ties to geo-lead comparison pages). Community-moderated → can be edited by others. |
| **DevHunt** | devhunt.org | GitHub PR + GitHub-login voting | Free | **Strong fit.** "Product Hunt for devs," GitHub-auth voting (low spam), exact ICP. Has a launch-spike model — pair with the launch-day runbook. |
| **LibHunt** | libhunt.com | Auto-indexes GitHub; can submit | Free | **Good fit.** Genuine OSS-dev audience, language-ranked. Largely auto-populated from GitHub activity — traction surfaces you. |
| **OpenAlternative** | openalternative.co | Web form / submit | Free | **On-brand.** Positions trovex as the OSS alternative to commercial SaaS. Growing DR, OSS audience. |
| **Product Hunt (permanent profile)** | producthunt.com | Free account + launch | Free | Launch = the event (see product-hunt.md); the permanent profile is a durable, high-DR backlink. |
| **SaaSHub** | saashub.com | Web form | Free (paid promo optional) | Decent "alternatives to" capture, low effort. |
| **Futurepedia** | futurepedia.io | Web form (+ paid promo) | Free tier | The one broad AI directory that demonstrably sends dev-adjacent traffic (~20% outbound to Programming/Developer software). Free tier worth it; skip paid. |
| **AI Agents Directory** | aiagentsdirectory.com | Web form | Free (+ paid) | On-theme for the agent angle (DR ~71). Free listing worth submitting. |
| **TopDevelopers / dev-tool dirs** | — | Web form | Free | Lower priority; do in the batch pass. |
| **StackShare** | stackshare.io | Web form (free account) | Free | Maintenance-mode since FOSSA acquisition (2024) — claim it, low effort, modest traffic. |
| **Slant** | slant.co | Community web form | Free | Diluted beyond software now — only if cheap on time. |

**Per-directory checklist (applies to each row):**
- [ ] Confirm the directory is live + reputable (not a parked SEO farm) before submitting.
- [ ] Use the §1 canonical copy; trim to each field's length limit.
- [ ] Set pricing = Free / Open source; link repo + trovex.dev.
- [ ] Attach the §1 asset set where images are accepted.
- [ ] **No consulting CTA** — these are tool listings, not a sales surface (keep the consulting door on the site only).
- [ ] Log it (directory, URL, date submitted, live y/n) in the tracking sheet.

---

## 3. tsukumo (agency) — canonical listing copy (for agency directories)

*(Draft for cmo/owner to route to the tsukumo repo/owner. Reflects agency-positioning, agency-icp, agency-proof, agency-fact-founded.)*

**Name:** tsukumo
**Tagline:** Turn your dev team into agentic operators — prod-grade AI, not seat licenses.
**Short:** Boutique AI-engineering studio + consulting. We help scale-up dev teams run AI coding agents at prod quality — augmenting developers, not replacing them.
**One-paragraph:**
> tsukumo is a Switzerland-based AI-engineering studio and consulting practice (est. 2026). We work with
> startups and scale-up engineering teams (≈30 devs) that don't want to miss the AI shift but are stuck:
> real existing dev standards to respect, shallow AI use, devs who are wary of it. We turn that team into
> agentic operators — augmenting developers, ~10x output, prod-grade — through hands-on engagements:
> agentic-dev training, agentic process setup, and building agentic-first systems. Two doors: studio
> (build my product) and consulting (my team struggles with AI). Tools and seats aren't capability; we
> install the capability.
**Services / categories:** AI consulting · AI development · Software development · Generative AI · AI agents / agentic systems · Developer enablement / training
**Location:** Switzerland · **Founded:** 2026
**Proof (qualitative only — agency-proof):** Engagements include a quant/finance firm (agentic-dev training + CTO upskilling) and a real-estate company (agentic acquisition marketing + an agentic-first platform + GEO). No fabricated metrics or logos until the owner approves specifics.
**Links:** site `tsukumo.ch`
**Pricing field:** "Contact for scope" — **no public prices** (pricing-policy). Never enter $ figures, tiers, or "from $X."

> ⚠️ Brand: lowercase `tsukumo`; acid-lime `#c8ff00` on any visual asset (agency-identity); positioning = augment-not-replace (kills the fear objection). NOT the trovex voice/brand — the agency has its own bolder identity.

---

## 4. Agency / consulting directories — submit table

> Credible B2B/agency directories vs pay-to-play noise. Free claims first; paid tiers are an owner/cmo decision (flagged). Swiss/EU fit graded.

| Directory | URL | Submission | Free/Paid | Fit + note |
|---|---|---|---|---|
| **Clutch** | clutch.co | Web form + reviews via verification calls | Free profile; sponsored **$1,500–4,000+/mo** | **The credibility anchor** CTOs actually check. Free profile + 2–3 *verified* reviews is the smart minimum. Verified reviews need client phone/email interviews (owner arranges). Sponsorship only worth it at high deal size — skip for now. |
| **Sortlist** | sortlist.com | Web form / profile | Free basic; paid from ~$300/mo | **Best EU fit.** Brief-based matching → pre-qualified leads (budget/timeline scoped). Strongest in Europe — good for a Swiss firm. Paid test only if pipeline justifies. |
| **TechBehemoths** | techbehemoths.com | Web form | Free (generous tier) | **Do it.** Strong country/category coverage incl. Switzerland/EU. Genuinely useful free listing, low effort. |
| **GoodFirms** | goodfirms.co | Web form | Free plan; paid from ~$300/mo | Solid DR, transparent pricing data, mid-market. Free + reviews fine to start; lower stakes than Clutch. |
| **The Manifest** | themanifest.com | Web form (tied to Clutch) | Free | Clutch sister site — extends the Clutch profile. Free, low effort if doing Clutch. |
| **DesignRush** | designrush.com | Web form / editorial | Free to list; sponsored upsell | Free basic listing; the "top 10 AI agencies" PR rankings are a citation/backlink win. Expect a sponsorship pitch. |
| **TopDevelopers.co** | topdevelopers.co | Web form | Free listing; paid promo | Has explicit AI-consulting / AI-agent-development categories (on-theme). Free listing worth it; paid low priority. |
| **UpCity** | upcity.com | Web form | Free; paid Certified Partner | **Weak fit** — US-local/marketing-agency-centric. Deprioritize/skip for a Swiss B2B AI-engineering firm. |

**Per-directory checklist (applies to each row):**
- [ ] Owner/cmo decides free-listing-only vs paid tier (Clutch/GoodFirms upsell hard).
- [ ] Use §3 copy; pick service categories matching the directory's taxonomy.
- [ ] **No prices** (pricing-policy); "contact for scope."
- [ ] **No fabricated reviews/ratings** — leave review fields empty until real client reviews exist (some directories require a verification call / client reference; owner handles that).
- [ ] Provide tsukumo.ch + a real contact; confirm the listing renders before considering it done.
- [ ] Log it in the tracking sheet (directory, plan free/paid, date, live y/n, claimed y/n).

---

## 5. Sequencing + ROI (the order to actually do this)

1. **Free, high-credibility, GEO-cited tool directories for trovex first** (top of §2) — cheap, compounding, citable. Do alongside the MCP-registry push (`mcp-registries.md`).
2. **AlternativeTo / comparison sites** — position trovex against CLAUDE.md / repomix / context-hub (ties to geo-lead's comparison-page work). High-intent: people searching alternatives.
3. **Agency directories (§4) — owner-gated.** These need real contact + sometimes a verification call; the owner runs them when the agency pipeline warrants. Free claims first; paid tiers only on a cmo decision.
4. **Skip the spam (§6).** Don't dilute the brand with low-quality directory backlinks.

**Top-5 highest-ROI listings (all free, audience-correct, durable):**
1. **Awesome lists (GitHub PR)** — purest dev audience, high-trust durable backlinks.
2. **AlternativeTo** — high-DR comparison/intent traffic; capture "alternative to CLAUDE.md / repomix."
3. **DevHunt** — dev-native launch + listing, GitHub-gated (low spam), exact ICP.
4. **Product Hunt** — coordinated launch spike + permanent high-DR profile.
5. **Clutch (free profile + 2–3 verified reviews)** — the one credibility anchor for the agency that CTOs check; skip sponsorship until deal size justifies.

_Honorable mentions: Futurepedia (broad AI dir that actually sends dev traffic) for trovex; Sortlist + TechBehemoths (EU agency leads) for tsukumo._

---

## 6. Skip these (low-quality / pay-to-play / spam)

- **Volume dumps / bulk-submit farms** — FutureTools, AllThingsAI, AI Tools Planet, Toolfolio, poweredbyai.app, "submit to 200+ sites" services, listmyai-style bulk submitters. Any directory listing 50k+ tools with no curation is a backlink dump, not traffic; bulk auto-submit services create a spammy-link footprint that can hurt.
- **TAAFT paid fast-track ($347)** for a dev CLI — consumer-skewed audience, weak dev ROI for the price. Use the free queue or skip.
- **UpCity** (agency) — US-local/marketing focus, poor fit for a Swiss B2B AI-engineering firm.
- **Paid "high-authority AI directory" link packages** (press-release link farms) — pay-to-play, brand-diluting.

---

## 7. Voice / brand QA (every field, both products)

- [ ] **trovex** listings: lowercase `trovex`, no banned words (revolutionary/seamless/supercharge/unlock/AI-powered), real ~60% only, no consulting CTA, no fabricated users.
- [ ] **tsukumo** listings: lowercase `tsukumo`, augment-not-replace framing, **no public prices**, qualitative proof only, no fabricated reviews.
- [ ] No "Synergix" in any prose field (only the unavoidable GitHub-org identifier for trovex).
- [ ] Every link resolves; every asset on-brand (trovex green `#22c55e`; tsukumo acid `#c8ff00`).
- [ ] Each submission logged in the tracking sheet.

---

## 8. Handoff summary

1. **trovex (this colony):** submit the free §2 directories with §1 copy, alongside the registry push. launch-lead can run the reversible/free ones when credentialed (autonomy-rules); a human verifies each lands.
2. **tsukumo (route to owner/tsukumo repo):** §3 copy + §4 directories are a plan; cmo/owner decides free-vs-paid and runs the agency submits (verification calls, contact).
3. **Track everything** in one sheet; re-check listings render; never fabricate proof or enter prices for the agency.

*All copy above is a draft. Nothing has been submitted.*
