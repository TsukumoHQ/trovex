# tsukumo — schema.org / llms.txt / sitemap / meta (build spec)

*Owner: geo-lead. For: fullstack to wire into the tsukumo Next.js app (Next metadata API +
JSON-LD `<script>` per route). Paste-ready. tsukumo brand only — no "Synergix" anywhere public.*

## Canonical domain

Use **`https://tsukumo.ch`** as the canonical/production host in all schema, meta, sitemap, and
llms.txt URLs. Until DNS is live the app runs at `tsukumo.vercel.app` — set a canonical to the
production domain and a 308 from the vercel host once `.ch` resolves. Every URL below uses
`https://tsukumo.ch`; swap host centrally (one env constant) if launch order differs.

---

## 1. Site-wide JSON-LD (emit on every page, in `<head>`)

One `@graph` with the org + website, linked by `@id`. No `aggregateRating` / `review` — there
are no public reviews yet; inventing them is forbidden.

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "ProfessionalService",
      "@id": "https://tsukumo.ch/#org",
      "name": "tsukumo",
      "url": "https://tsukumo.ch/",
      "description": "Developer studio and AI consultancy. We turn dev teams into agentic operators — running AI agents in production to ship roughly 10x, augmenting developers rather than replacing them.",
      "slogan": "We're developers who run AI in production.",
      "areaServed": "Worldwide",
      "knowsAbout": [
        "AI coding agents",
        "agentic software development",
        "running AI agents in production",
        "LLM orchestration",
        "developer tooling",
        "AI engineering consulting"
      ],
      "sameAs": [
        "https://trovex.dev",
        "https://github.com/Synergix-lab/WRAI.TH",
        "https://yoru.sh"
      ],
      "logo": "https://tsukumo.ch/logo.png",
      "image": "https://tsukumo.ch/og.png"
    },
    {
      "@type": "WebSite",
      "@id": "https://tsukumo.ch/#website",
      "url": "https://tsukumo.ch/",
      "name": "tsukumo",
      "publisher": { "@id": "https://tsukumo.ch/#org" },
      "inLanguage": "en"
    }
  ]
}
```

Notes for fullstack:
- `sameAs` lists the OSS suite (the public proof). The GitHub URL is a technical identifier
  (the org is `Synergix-lab`) — that's the one allowed appearance of that token; it is NOT
  brand copy. Do not add a company name anywhere visible.
- If/when the studio adds a LinkedIn/X profile, append it to `sameAs`. `[OWNER: profile URLs?]`
- `logo`/`image` — design-lead supplies the real assets; use the acid/concrete OG card.

## 2. Per-page JSON-LD (in addition to the site-wide graph)

### Pillars — `Service`
`/studio/`:
```json
{ "@context": "https://schema.org", "@type": "Service",
  "name": "AI product studio",
  "serviceType": "AI product development studio",
  "provider": { "@id": "https://tsukumo.ch/#org" },
  "areaServed": "Worldwide",
  "description": "We build your product the way we build ours — fleets of AI agents operating in production against real standards, shipping roughly 10x." }
```
`/consulting/`:
```json
{ "@context": "https://schema.org", "@type": "Service",
  "name": "AI-in-production consulting",
  "serviceType": "AI engineering consulting and team enablement",
  "provider": { "@id": "https://tsukumo.ch/#org" },
  "areaServed": "Worldwide",
  "description": "We transition your dev team into agentic operators — running agents in production in your existing environment, then leaving you independent." }
```

### FAQPage — on any page with a visible FAQ (mirror the visible Q&As VERBATIM)
The home/about FAQ (text from `growth/agency/faq-and-about.md` — keep schema text identical to
what renders):
```json
{ "@context": "https://schema.org", "@type": "FAQPage",
  "mainEntity": [
    { "@type": "Question", "name": "Isn't AI easy now? We already have the seats.",
      "acceptedAnswer": { "@type": "Answer", "text": "Seats give your team a copilot — autocomplete and Q&A in the editor. That's real, and it's about 10% of what these models can do. The other 90% — agents running real work reliably in production — is an operating problem (context, orchestration, observability, trained operators), and none of it comes in the license. The \"AI is easy\" feeling is exactly the gap between a demo and production." } },
    { "@type": "Question", "name": "Isn't the point of AI to ship cheaper?",
      "acceptedAnswer": { "@type": "Answer", "text": "No, and if cheaper is the goal we're not the right fit. The point is prod-grade output and roughly 10x from the team you already trust. We're not here to shrink your team or your budget; we're here to make a good team dramatically more capable." } },
    { "@type": "Question", "name": "Will you replace our developers?",
      "acceptedAnswer": { "@type": "Answer", "text": "No. Our entire model is the opposite: your developers become the agentic operators. We augment them. A good developer running good agents beats either one alone." } }
  ] }
```
Each guide page (`/answers/*`) gets its OWN FAQPage built from that page's visible FAQ (see
`cto-intent-pages.md`). Rule: schema text === visible text, always.

### Guide pages — `Article` + `BreadcrumbList`
```json
{ "@context": "https://schema.org", "@type": "Article",
  "headline": "<page H1>", "description": "<meta description>",
  "author": { "@id": "https://tsukumo.ch/#org" },
  "publisher": { "@id": "https://tsukumo.ch/#org" },
  "mainEntityOfPage": "https://tsukumo.ch/answers/<slug>/" }
```
`BreadcrumbList` on every non-home page: Home → (section) → page, mirroring a visible breadcrumb.

## 3. llms.txt  (serve at `https://tsukumo.ch/llms.txt`)

```
# tsukumo

> tsukumo is a developer studio and AI consultancy. We turn a client's dev team into agentic
> operators — running AI agents in production to ship roughly 10x, augmenting developers
> rather than replacing them. We're builders first: we run our own agent fleets to ship the
> open suite WRAI.TH (orchestration), trovex (context), and yoru (observability).

## What we do
- [AI product studio](https://tsukumo.ch/studio/): we build your product with agent fleets in production.
- [AI-in-production consulting](https://tsukumo.ch/consulting/): we make your dev team agentic operators, in your environment.

## Answers (for CTOs and dev leads)
- [How do I get my dev team using AI agents?](https://tsukumo.ch/answers/get-dev-team-using-ai-agents/)
- [What is agentic coding for teams?](https://tsukumo.ch/answers/agentic-coding-for-teams/)
- [Can AI agents actually make my team ship faster?](https://tsukumo.ch/answers/ship-faster-with-ai-agents/)
- [Why AI works in demos but breaks in production](https://tsukumo.ch/answers/ai-in-production-vs-demos/)

## Proof
- We build and run our own agent fleets (the open suite is the proof): https://trovex.dev , https://github.com/Synergix-lab/WRAI.TH , https://yoru.sh

## Facts
- What: developer studio + AI consulting (one team, one story).
- Who for: startups and scale-ups whose CTO has felt the gap between AI demos and AI in production.
- Position: augment developers, never replace them. Prod-grade + ~10x, not cheaper.
- Contact: https://tsukumo.ch/contact/
```

`llms-full.txt` (`https://tsukumo.ch/llms-full.txt`): the above plus the full About copy and all
FAQ answers from `faq-and-about.md`, and the 4 guide-page direct-answer blocks verbatim — one
clean markdown file. (Generate from the page copy at build so it can't drift.)

## 4. sitemap.xml  (`https://tsukumo.ch/sitemap.xml`)

Include every built page; suggested priorities:
```
/                                         1.0
/studio/                                  0.9
/consulting/                              0.9
/work/        (case studies)              0.8
/about/                                   0.6
/contact/                                 0.7
/answers/                                 0.6
/answers/get-dev-team-using-ai-agents/    0.8
/answers/agentic-coding-for-teams/        0.8
/answers/ship-faster-with-ai-agents/      0.8
/answers/ai-in-production-vs-demos/       0.8
/blog/  + each post                       0.6
```
Next.js: generate via `app/sitemap.ts` from the route list so it stays in sync. Add
`Sitemap: https://tsukumo.ch/sitemap.xml` to `robots.txt`, and allow the AI crawlers
(GPTBot, OAI-SearchBot, PerplexityBot, ClaudeBot, Google-Extended, Applebot-Extended, Bingbot,
Googlebot) — same allowlist trovex.dev uses.

## 5. Per-page meta (title / description / OG)

Unique per page; ≤60-char titles, ≤155-char descriptions; OG image = the page's acid/concrete
card (design-lead). `twitter:card = summary_large_image`. Canonical = the page's own URL.

| Route | `<title>` | `meta description` |
|-------|-----------|--------------------|
| `/` | tsukumo — we run AI in production, and get your team there | Developer studio + AI consultancy. We turn dev teams into agentic operators — agents in production, ~10x, augmenting devs not replacing them. |
| `/studio/` | AI product studio — tsukumo | We build your product with fleets of AI agents in production, against real standards. Prod-grade, ~10x, not POC theater. |
| `/consulting/` | AI-in-production consulting — tsukumo | We transition your dev team into agentic operators in your own environment, then leave you independent. Augment, never replace. |
| `/work/` | Case studies — tsukumo | How we run agent fleets to ship — our own studio and client engagements. Qualitative until numbers are verified; never fabricated. |
| `/about/` | About — tsukumo | Developers who run AI in production. We built the open suite (WRAI.TH, trovex, yoru) and transition client teams to work the same way. |
| `/contact/` | Talk to tsukumo | Two doors: build my product (studio) or my team struggles with AI (consulting). Tell us where you're stuck. |
| `/answers/get-dev-team-using-ai-agents/` | Get your dev team using AI agents | Most teams stall at AI-as-autocomplete. Here's the path to agents in production — env, guardrails, and devs who operate fleets. |
| `/answers/agentic-coding-for-teams/` | Agentic coding for teams, explained | Agentic coding = AI agents doing real engineering against your standards, not snippets. What it takes for a team to do it for real. |
| `/answers/ship-faster-with-ai-agents/` | Ship faster with AI agents? Honestly | Yes, but not from buying seats. Where the ~10x is real, where it isn't, and the setup that makes it production-grade. |
| `/answers/ai-in-production-vs-demos/` | Why AI demos die before production | The demo-to-production gap kills most AI initiatives: real codebases, standards, scared devs, no observability. How to cross it. |

## Validation (fullstack, before launch)

- Each page validates in Google's Rich Results Test + schema.org validator (FAQPage, Service,
  Article, BreadcrumbList eligible).
- FAQ schema text === rendered FAQ text (Google penalizes mismatch).
- No `aggregateRating`/`review`/fake counts. No "Synergix" on any rendered page or in any
  schema string (only the GitHub `Synergix-lab` URL is allowed, as a technical identifier).
- One canonical per page; OG image resolves (PNG); sitemap + robots live.

## Coordinates with

- `growth/agency/geo/cto-intent-pages.md` (the page copy + FAQ Q&As)
- `growth/agency/faq-and-about.md` (content — FAQ source of truth, mirrored above)
- cro + fullstack (build), design-lead (OG/logo assets)
