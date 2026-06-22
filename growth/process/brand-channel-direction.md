# Brand & Channel Direction — canonical (anti-drift SSOT)

**Status:** v1, owner-called crisis fix (2026-06-22). Chaired by cmo, synthesized by content-lead
(scribe), reviewed by social-lead / design-lead / geo-lead / tech-copywriter, locked by cmo.
**This is canonical.** Before any social, content, or asset work, route here first. Deviations
need cmo sign-off. The canonical copy lives in the trovex store (SSOT); this on-disk file mirrors it.

Why this exists: output drifted (cadence revised three times, formats shifting, "je comprends plus
la strategy"). Root cause was no single direction, so each lead improvised. One doc fixes it.

## Brand architecture

- **tsukumo** = the umbrella, the agency, the consulting business. The north-star end: qualified
  reach becomes consulting leads.
- **trovex / wrai.th / yoru** = products under tsukumo. They are proof-of-competence magnets that
  feed the funnel. Products demonstrate; tsukumo converts.

## The ladder-up rule (portfolio level, not per post)

Every surface ladders up to tsukumo consulting in aggregate. The ladder applies at the
account/portfolio level, **not to each post**. A per-post "sell consulting or die" filter would
kill the reach content that builds the audience consulting later closes, which is how we got the
thin, salesy feed in the first place.

A funnel needs a top. So the mix ladders up, not each piece.

## The three post-roles

Every piece serves exactly one role. The weekly mix must contain all three.

1. **REACH** — founder POV, build-in-public, contrarian take, cited blog, AI-engine citation. No
   CTA on purpose. On-strategy *because* it feeds the top of funnel.
2. **ACTIVATION** — proof, the savings receipt, clone-and-run. Drives install + GitHub star.
3. **CONVERT** — authority into the consulting wedge. Company account and internal links to
   /consulting.

## The on-strategy filter

> Does this piece serve REACH, ACTIVATION, or CONVERT — and does the **week's mix** hit the ratio?

If a piece serves none of the three roles, cut it. Tag every scheduled piece with its role so the
balance is visible and enforceable.

### Portfolio ratio (locked — the enforceable "ladder up" test)

One number, per account, per week:

| Role | Share |
|---|---|
| REACH | **60%** |
| ACTIVATION | **30%** |
| CONVERT | **10%** |

We are pre-launch with ~0 audience, so the mix is reach-heavy on purpose: build the top of funnel
first. This ratio IS the "does the week's mix ladder up" test. Revisit it only with data, never on
weekly vibes.

## Cross-domain anti-dupe lock (hard guardrail)

The convert layer is **tsukumo.ch**. The discovery and product surfaces are **trovex.dev**.
"Every surface ladders to tsukumo" must **never** become:

- a redirect from a trovex.dev surface to tsukumo,
- a primary CTA to tsukumo on a trovex.dev page, or
- a cross-domain canonical (trovex.dev page canonicalized to tsukumo).

The ladder from a trovex surface is **one soft, non-cannibalizing link** (the endplate), full stop.
No 301s, no cross-domain canonical, no tsukumo CTA as the primary action on a trovex page. (This
reflex caused the 06-22 dupe / soft-404 incident; fullstack #353 stopped the bleed.)

## Account roles (stop mixing)

| Account | Role | What it carries |
|---|---|---|
| **@LoicMancino** (X) | Founder / human | Build-in-public, technical takes, ship-log, opinion. Primary dev reach + consulting credibility. |
| **@heliosmarket** (LinkedIn + Threads) | Founder / human | Carousels + build-in-public for the team-lead/consulting audience (highest consulting-funnel value). |
| **@tsukumohq** (LinkedIn + X + Threads) | Institutional | Product, launch, proof, releases. Carousels/docs. |

## Channel + owned-search mandate

| Surface | What it's for | Role | Owner | Link placement |
|---|---|---|---|---|
| X (founder @LoicMancino) | Technical takes, ship-log, threads; dev reach | REACH | social-lead | link in **reply**, not the hook |
| LinkedIn @heliosmarket | Carousels + BIP, consulting audience | REACH + CONVERT | social-lead + design-lead | **native / no link** while we A/B the first-comment penalty |
| Threads (founder) | Casual, reply-bait, native | REACH | social-lead | link **in-body** |
| LinkedIn @tsukumohq | Institutional carousels/docs + launches | CONVERT | social-lead + design-lead | native / no link (as above) |
| Newsletter (Resend, biweekly) | Owned audience, repurposed proof + cornerstones | ACTIVATION | content-lead | direct links OK |
| **Owned pages** (blog, /answers, /vs, glossary) | Google + AI-citation authority | REACH / authority | content-lead + tech-copywriter + geo-lead | internal links to /consulting (one soft endplate, per anti-dupe lock) |
| **AI-citation + off-site seed** (ChatGPT / Perplexity / Google AIO via Reddit / Quora / HN) | Discovery at buying intent | DISCOVERY → install | geo-lead (social fires seeds) | **product-honest only — see constraint** |
| Discord (tsukumo umbrella) | Community, post-launch, one server, products as categories | ACTIVATION | social-lead | n/a |
| GitHub | Product surface, not social | ACTIVATION | n/a | n/a |

**AI-citation / seed constraint (hard):** on /answers pages and in seed snippets the ladder is
**product-honest only**. A consulting CTA or promo line kills the citation — AI engines and dev
communities penalize promo, and the seed kit is the P0 that earns the citation. These surfaces
ladder by proving competence → install → authority. Never by selling.

## Voice (verbal SSOT)

- **Verbal SSOT owner: tech-copywriter.** Owns the voice + anti-slop gate across every surface;
  the locked voice wins verbal disputes.
- **Voice:** owner-writing-voice — patio11 / Stripe register, founder first-person, contrarian
  thesis delivered with warm-mentor tone. Evidence over adjectives. One thesis per piece.
- **Canonical one-liner, used verbatim:** «trovex — one canonical doc for your coding agents, ~60% fewer tokens.»
- **anti-slop gate is mandatory on every piece** (no exceptions, even at the cadence floor).
- **Proof rule:** the only first-party number is the real ~60% fewer tokens per lookup. Zero
  fabricated proof, zero client names on public surfaces.

## Visual system (visual SSOT)

- **Visual SSOT owner: design-lead.** The locked visual system wins visual disputes.
- **System:** data-editorial (memory `visual-system-locked`) — Archivo display, Fira body/mono,
  the data is the design, real-source footer.
- **Accent + property rule:**
  - **Product content** (trovex/wrai.th/yoru BIP, proof, launch) wears the **product's** accent and
    wordmark. The tsukumo ladder appears only as a small fixed **endplate on the CTA card**
    ("a tsukumo product · tsukumo.ch"), never by recoloring the deck.
  - **Institutional @tsukumohq** and anything consulting-led wears the **tsukumo house** base.
  - **Auto-post = GREEN** uniformly. **wrai.th VIOLET** is site-only (never auto-post). **yoru AMBER**
    is held. (memories `suite-accent-palette`, `autopost-green-antislop`.)

## Format priority

Carousels + build-in-public + proof are the highest-performing formats; weight the floor toward
them, not text filler (memory `social-format-priority`).

1. **Carousels** — abuse them, especially founder LinkedIn (document/multi-image gets the most
   reach). Generator `growth/assets/_tools/gen_carousel.mjs`.
2. **Build-in-public** — ship-log, what-broke, this-week-in-numbers, dogfood meta. Real numbers,
   founder-led.
3. **Proof** — the savings receipt (real figures, ~60% public floor), earned-evidence studies.

X / Threads text takes are the support and amplification layer, never the main course. Every
founder LinkedIn slot should aim to be a carousel or a proof visual, never naked text.

## Cadence floor (one number, committed — stop revising)

Floor to hit per brand per day (memory `social-cadence-daily` v4). This is a floor, not a slop
license.

| Brand | Floor / day | Split |
|---|---|---|
| Founder **@heliosmarket** | ~6–8 | 2 LinkedIn + ~3 Threads + ~3 X |
| Company **@tsukumohq** | ~3–4 | 1 LinkedIn carousel/doc + ~2 X + ~1 Threads |

Every post still: anti-slop PASS + channel-native visual (LinkedIn always visual; X/Threads strong
text OK for a sharp take) + green + no client names + UTM. Source the volume from **real** material
(operator-news feed, repurposed published blog atoms, BIP artifacts/carousels, the savings receipt).
If a day can't hit floor with strong material, fill what you can and flag cmo. Never pad with slop.
This floor is frozen; revisit only with data, never weekly.

## Posting matrix (the enforceable grid)

Every scheduled piece resolves to one row: **brand/account × channel/surface × role × format ×
cadence × link-placement × visual(accent + wordmark + ladder-cue) × owner.** The channel table
above is that grid; the cadence and visual columns lock the two axes that previously drifted. If a
piece can't be placed in a row, it's off-strategy.

## Ownership summary (tie-breaks)

- **cmo** — chairs strategy; locks this doc and any change to it.
- **content-lead** — scribe of this doc; authors blog / newsletter / landing.
- **tech-copywriter** — verbal SSOT (voice + anti-slop gate, cross-surface).
- **design-lead** — visual SSOT (the locked visual system).
- **social-lead** — captions / social copy authorship + scheduling.
- **geo-lead** — owned-search + AI-citation + off-site seed.

Changes to this direction go through cmo. One canonical direction, routed-to before any post.
