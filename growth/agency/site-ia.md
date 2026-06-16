# tsukumo — agency site IA, page structure & conversion flow

*Owner: cro-lead (Conversion). The structural layer for the consulting site. Slots into
content-lead's [`positioning-copy.md`](./positioning-copy.md) and the locked
[`design-direction.md`](./design-direction.md) (Tsukumo · "01 Concrete & Acid" · acid-lime
`#c8ff00` · tsukumo.ch). Build target: incoming `Synergix-lab/tsukumo` (Next.js). This
doc defines **what goes where and how a visitor becomes an inquiry** — not the copy and
not the visuals.*

## 1. Goal & conversion hierarchy

The site exists for **one** business outcome: a qualified team books a conversation about
running their agent fleet. Everything else is in service of, or subordinate to, that.

- **Primary conversion:** consulting inquiry — a booked call / qualified contact. This is
  the money action; it gets the most weight, the most entry points, and the lowest
  friction.
- **Secondary:** "see what we've shipped" (work/proof) — for the not-yet-ready visitor;
  it *feeds* the primary, never competes with it above the fold.
- **Tertiary:** explore the OSS suite (trovex / WRAI.TH / yoru) — credibility + a
  cross-funnel; lives lower and in the footer, links out to each tool.
- **Anti-goal:** do not optimize for newsletter signups, generic "contact", or vanity
  traffic. One bullseye.

**The one metric:** qualified consulting inquiries. (Coordinate with analytics-lead to
instrument `inquiry_started` → `inquiry_submitted`, plus source attribution incl.
suite→agency referrals.)

## 2. Audience (who the IA is built for)

Primary: the **eng leader / CTO / founder** of a team that has AI as a *copilot* and
senses it should be more — feeling the "bought the seats, getting 10%" gap
(per positioning-copy). Secondary: a **senior dev** who'll champion it internally.
Both are technical, allergic to hype and corporate-consulting cliché. The IA must let a
skeptic self-qualify fast and reach the inquiry with proof in hand.

## 3. Global nav & footer

**Nav (minimal, brutalist — type-led, ≤5 items + 1 CTA):**
`tsukumo` (wordmark → home) · `Work` · `Approach` · `Suite` · **`Talk to us` (primary CTA, persistent)**

- The CTA is always visible (sticky or pinned); it is the only button in the nav.
- "Services/Studio+Consulting" is folded into the home + Approach rather than its own
  nav item, to keep nav to one bullseye. (If a dedicated Services page ships, it slots
  before Approach.)
- Mobile: wordmark + `Talk to us`; the rest in a menu. The CTA never collapses behind the
  menu.

**Footer:** wordmark + one-line positioning · nav repeat · **the suite** (trovex / WRAI.TH
/ yoru, each linking to its own site) · contact email · legal. The suite in the footer is
the always-on cross-funnel.

## 4. Sitemap / page inventory

Recommended v1 — a strong long-form **home** plus a few deep pages (brutalist one-pagers
work, but consulting buyers want a real Work page and a frictionless contact):

| Page | Route | Job | Conversion role |
|------|-------|-----|-----------------|
| **Home** | `/` | The whole argument, scannable in one scroll | Carries the primary CTA in ≥3 places |
| **Work / proof** | `/work` | Case studies (honest, see case-studies.md) | Secondary → feeds inquiry; CTA at end |
| **Approach** | `/approach` | How we work (in-prod, augment-not-replace, the method) | De-risks; CTA at end |
| **Suite** | `/suite` | The OSS tools as proof + method; links out to each | Tertiary + credibility; CTA at end |
| **Contact / book** | `/talk` | The conversion surface | **Primary** |
| (later) About | `/about` | The people / studio | Trust; CTA at end |

Every page ends with the **same single CTA block** → `/talk`. No page is a dead end.

## 5. Home — section-by-section IA

Order = the argument. Each section: its job, the content slot (copy owned by content-lead),
and its conversion role. Brutalist "breath" sections between (design-direction §principles).

1. **Hero** — *id `hero`*
   - Job: state who we are + the gap in <5s. Copy slot: positioning-copy Hero
     ("We run AI in production. Most teams are still running demos.").
   - Conversion: **primary CTA** ("Talk to us about your team") + secondary text link
     ("See what we've shipped" → scrolls to Work/Proof). One button only.
2. **The gap** — *id `gap`*
   - Job: name the pain the CTO has felt (copilot vs operators). Copy: positioning "The gap".
   - Conversion: none (build recognition); ends pointing into "What we do".
3. **What we do — two doors** — *id `what`*
   - Job: Studio (we build it) + Consulting (we transition your team). Copy: positioning
     "What tsukumo does".
   - Conversion: consulting is the emphasized door; its sub-CTA → `/talk`.
4. **How we work** — *id `approach`*
   - Job: the differentiators (in production not a deck; augment never replace; measured).
   - Conversion: link → `/approach` for depth; inline CTA.
5. **Proof / the suite** — *id `proof`*
   - Job: WRAI.TH (orchestration) · trovex (context, the measured ~60%) · yoru
     (observability) as *evidence we run our own fleets*. Real product, real method.
   - Conversion: each tool links to its site (cross-funnel); section CTA → `/talk`.
   - Honesty: the suite is real and shippable; no fabricated adoption numbers.
6. **Work / case studies (teaser)** — *id `work`*
   - Job: 2–3 case teasers (own studio · quant fund anon · etc., per case-studies.md),
     honest placeholders until real numbers land. Link → `/work`.
   - Conversion: secondary; ends with primary CTA.
7. **Who it's for** — *id `fit`*
   - Job: qualify in/out (a fit: team using AI as copilot, real codebase & standards; not
     a fit: looking to replace devs / one-off demo). Honest self-selection raises lead
     quality.
   - Conversion: leads into the close.
8. **Close / contact** — *id `talk`*
   - Job: the inquiry. Mirrors `/talk`. Primary CTA + the booking/contact mechanic inline.

Rule: the **primary CTA appears in hero, mid-page (proof or work), and the close** — same
label, same destination. No competing CTAs in the same viewport (CRO-verified: one
primary action wins).

## 6. Conversion flow (visitor → inquiry)

```
land → recognize the gap → see proof (suite + work) → self-qualify (who it's for)
     → CTA "Talk to us" → /talk → inquiry form / booking → confirmation → human follow-up
```

**The inquiry surface (`/talk`):** keep it short and high-intent. Capture only what
qualifies + lets us reply:
- work email (required), company/team, one free-text "what are you trying to do with
  agents?" (the qualifier), optional team size / stack.
- Two paths, one form: **book a call** (calendar embed when a real booking link exists) OR
  **send a message**. Default to whichever the owner prefers; the form is the fallback.
- **Honesty / anti-pattern:** no fake urgency, no "limited slots", no chatbot theatre, no
  required phone number. A real person replies.
- **Failure UX:** like the trovex waitlist — graceful states, never a raw error; a plain
  fallback (email address) if submission fails.
- **Privacy:** business email is the only PII; no tracking beyond source attribution
  (coordinate analytics-lead). First-party capture, no third-party form SaaS (mirror the
  trovex `/api/waitlist` first-party pattern).

**Qualification (post-submit, human):** the free-text + team size route to a quick
fit-check before the call. Out-of-scope (replace-devs, no real codebase) gets an honest
"not us" rather than a sales call.

## 7. Suite ↔ agency cross-links (the funnel wiring)

The OSS suite is the top of the funnel; tsukumo is where it converts. Wire both directions,
quietly (never turn the OSS surfaces into sales pages — see trovex's earned, low-key
consulting line):

- **Suite → agency (inbound funnel):** each tool's site (trovex, WRAI.TH, yoru) carries
  one low-key, earned line → tsukumo "work with the team behind this" / "running this
  across a team? we help". trovex already has the consult-band + `CONSULT_URL` hook — point
  it at tsukumo.ch once live (currently in-page `#waitlist` during private beta). Same
  pattern for WRAI.TH and yoru.
- **Agency → suite (proof):** tsukumo's Proof/Suite section + footer link out to each tool
  as evidence ("the software we ship for ourselves"). These are *proof links*, not CTAs —
  they reinforce competence, then return the visitor to `/talk`.
- **Attribution:** tag suite→agency referrals (utm or referrer) so analytics-lead can show
  which OSS tool sources the most consulting inquiries — the actual ROI of the OSS funnel.
- **Shared thread:** the mono typeface is the one visual tell linking the bold agency brand
  back to the terminal-restraint suite (per design-direction) — different brands, same
  people.

## 8. Proof & trust IA (honest)

- Case studies follow the honest shape (Context → gap → what we did → outcome → quote);
  every number is a labelled placeholder until verified (see case-studies.md). **No
  fabricated logos, testimonials, or metrics** — pre-launch.
- The strongest honest proof is **self-proof**: we run our own fleets to ship the suite.
  Lead with that; it needs no client permission.
- The measured trovex `~60%` (see [`../cro/savings-methodology.md`](../cro/savings-methodology.md))
  is a real, reproducible number — the one hard figure we can stand behind today.

## 9. SEO / GEO & a11y (coordinate geo-lead)

- Each page: one `h1`, a clear title/meta, `Organization` + `Service` (and `Person` for
  founder) JSON-LD. The Approach/Suite pages are citable methodology surfaces — good GEO.
- Honest, extractable copy (no slop) earns AI-engine citations for "help running AI coding
  agents at scale / fleet ops".
- a11y: type-as-hero must still hit WCAG contrast (acid-lime on near-black — verify the
  pairing), real focus order, labelled form fields, `prefers-reduced-motion` respected
  (already in the design principles).

## 10. Open questions (owner / cmo)

1. **Contact mechanic:** calendar booking link (Cal.com / SavvyCal) vs. plain inquiry form
   for v1? IA supports either; need the real destination (mirrors the trovex `CONSULT_URL`
   human-TODO).
2. **v1 page set:** ship home + `/talk` only first, or home + Work + Approach + Suite
   together? (Recommend home + `/talk` live, Work/Approach/Suite fast-follow.)
3. **Naming the studio entity:** case-studies flags whether "Synergix" may be named as the
   studio, or stay "our studio". Affects About/Work copy.
4. **Suite cross-link timing:** point trovex/WRAI.TH/yoru consult lines at tsukumo.ch now,
   or after the agency site is live? (Recommend after, to avoid linking to a 404.)

---

*Build note: when `Synergix-lab/tsukumo` lands, this IA maps 1:1 to Next.js routes
(`/`, `/work`, `/approach`, `/suite`, `/talk`). Copy from positioning-copy.md, tokens from
design-tokens.css, conversion flow from §6 here.*
