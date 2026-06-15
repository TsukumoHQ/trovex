# Trovex — GEO / AI-Engine Attribution

*Owner: analytics-lead · Status: v1 · Last updated: 2026-06-15*

**Goal:** know which AI engine or referrer sent each session to `trovex.dev`, so the
GEO/AEO work (making trovex the cited answer in ChatGPT / Perplexity / Google AI
Overviews / Claude) has a measurable ROI instead of a vibe. This doc is the *approach +
spec*; the runtime derivation already shipped in `web/src/analytics.ts` (PR #9). The
new, cross-lead deliverable here is the **UTM taxonomy contract** in §4 — every lead who
seeds a link must follow it, or this attribution stays blind.

---

## 1. Why this is hard (state it before measuring it)

AI engines do not reliably pass a referrer. The honest reliability picture (2026):

| Engine | Typical referrer capture | Notes |
|--------|--------------------------|-------|
| Perplexity | ~80–90% | Usually sends `perplexity.ai`. The good case. |
| ChatGPT | ~60–70% | `chatgpt.com`; native-app / some clients strip it. |
| Claude | ~50–65% | `claude.ai`; often stripped. |
| Google AI Overviews | **~0% separable** | Renders inside `google.com`; no distinct referrer. Inseparable from organic Google by referrer alone. |
| Copilot / Bing Chat | variable | `copilot.microsoft.com` / `bing.com` when present. |

Consequence: a large share of AI-driven visits land in **Direct** (no referrer) or get
bucketed as generic **search**. So **referrer-only attribution is a floor, not a
census.** We raise the floor with UTM tags on the links *we* control, and we report the
`direct` / `unknown` share openly rather than pretending it's zero.

## 2. Detection model (precedence)

Per session, `geo_source` is resolved in this order (implemented in
`deriveSession()`, `web/src/analytics.ts`):

1. **Explicit UTM** — `?utm_source=` matches our known map (`chatgpt`, `perplexity`,
   `claude`, `gemini`, `copilot`, `bing`, `google`). **Most reliable** — this is a link
   *we* tagged, so it survives referrer stripping. Wins over everything.
2. **Referrer host** — closed regex map of engine/search/social hosts → source.
   Google (any TLD) → `search` (we do **not** invent `google_aio`, since AIO is not
   separable; only a UTM can promote it).
3. **Fallback** — no referrer → `direct`; UTM present but unknown → `unknown`.

`channel` is a coarse roll-up: `ai_engine | search | social | referral | direct`.
Both are closed enums; unknown values collapse so cardinality can't explode and no raw
string (potential PII) leaks into properties. Referrer is reduced to **host only**.

## 3. What gets captured per session

Attached to `landing_view` and every event (see tracking-plan.md §4):

- `geo_source` — `chatgpt | perplexity | claude | gemini | copilot | bing | search | social | referral | direct | unknown`
- `channel` — `ai_engine | search | social | referral | direct`
- `utm_source` / `utm_medium` / `utm_campaign` — lowercased, length-capped, `none` if absent

No IPs, no cookies, no fingerprinting, no per-user identifier. Country/device come from
the analytics provider as coarse aggregates only.

## 4. UTM taxonomy contract  ⚠️ all leads follow this

This is the only reliable AI-engine signal. **Any time a lead places a link to
`trovex.dev` somewhere we control or seed, it carries these params.** Referrer-based
detection is the safety net for everything we *don't* control.

### 4.1 Parameter rules

- `utm_source` — **where the click physically comes from.** Use the engine/platform
  slug from the closed list below. Lowercase, no spaces.
- `utm_medium` — **the kind of placement.** Closed list: `ai_answer` (cited/linked
  inside an AI engine's answer), `organic` (search/SEO page), `social`, `community`
  (forum/Discord/subreddit post), `registry` (MCP/registry listing), `referral`,
  `email`, `paid`.
- `utm_campaign` — **the initiative**, kebab-case. Free-ish but reuse names so they
  group: `launch-hn`, `launch-ph`, `geo-seed`, `comparison-pages`, `readme`, etc.

### 4.2 `utm_source` closed list (must match `analytics.ts`)

| Surface | `utm_source` | Resolves to `geo_source` |
|---------|-------------|--------------------------|
| ChatGPT answer/citation | `chatgpt` | `chatgpt` (`ai_engine`) |
| Perplexity answer/citation | `perplexity` | `perplexity` (`ai_engine`) |
| Claude answer/citation | `claude` | `claude` (`ai_engine`) |
| Google Gemini | `gemini` | `gemini` (`ai_engine`) |
| Google AI Overviews / Google organic | `google` | `search` |
| Bing / Copilot | `bing` / `copilot` | `bing` / `copilot` |
| HN / Reddit / Lobsters / X / LinkedIn | `hackernews` / `reddit` / `lobsters` / `x` / `linkedin` | `social` |
| MCP registry / directory | `mcp-registry` (or specific registry slug) | `referral` |

> If a lead needs a `utm_source` not in this list, **ping analytics-lead to add it to the
> map first** — an unmapped source silently degrades to `referral`/`unknown` and the GEO
> ROI for that channel disappears.

### 4.3 Examples

```
# trovex linked from a Perplexity answer we seeded via a comparison page
https://trovex.dev/?utm_source=perplexity&utm_medium=ai_answer&utm_campaign=comparison-pages

# trovex in an MCP registry listing
https://trovex.dev/?utm_source=mcp-registry&utm_medium=registry&utm_campaign=launch

# Show HN post link
https://trovex.dev/?utm_source=hackernews&utm_medium=community&utm_campaign=launch-hn
```

**Handoff:** geo-lead owns tagging the GEO/SEO + comparison-page links; launch-lead owns
registry + launch links; social-lead owns social links. analytics-lead owns the map.

## 5. Reporting — turning capture into GEO ROI

In Plausible (the recommended provider, pending cmo's tooling confirmation):

- **Custom-property breakdowns** on `geo_source` and `channel` for `landing_view`,
  `cta_clicked`, `github_clicked`, `command_copied`. This gives, per engine: sessions →
  CTA rate → GitHub-click rate (our intent proxy).
- **Goals**: mark `cta_clicked` / `github_clicked` / `command_copied` as goals so each
  `geo_source` shows a conversion rate, not just traffic.
- **The GEO ROI read:** for each AI engine, *sessions it sent × intent-conversion of
  those sessions*. An engine that sends few but high-intent sessions can beat a
  high-volume social spike — that's the number that should steer GEO effort, not raw
  visits. Always shown next to the `direct`/`unknown` share so the floor is visible.

## 6. Server-log signal (complementary, optional)

JS analytics only sees humans who execute scripts. AI engines also **crawl** the site
with named bots that never run JS and never show as a session:

- `GPTBot` / `OAI-SearchBot` (OpenAI), `PerplexityBot`, `ClaudeBot` /
  `anthropic-ai`, `Google-Extended` — identifiable by User-Agent in server/CDN logs.

These are a **crawl/citation-eligibility** signal (is the engine *reading* us), distinct
from the **referral** signal (is the engine *sending* us clicks). If/when we want it,
parse Vercel/CDN access logs by UA into a weekly count per bot. Not required for v1, and
**not** mixed into `geo_source` (which is human-session attribution only). Logged here so
the option isn't lost.

## 7. Honest limitations / what we will and won't claim

- We report AI-engine attribution as a **floor**. We never back-fill the gap with an
  estimate presented as real.
- Google AI Overviews are **not** broken out unless a UTM says so; otherwise `search`.
- `direct` includes genuine direct visits *and* referrer-stripped AI clicks — we show it
  as `direct`, not silently reassigned.
- No per-user identity is constructed, ever. Attribution is per-session and aggregate.

## 8. Acceptance

- [x] Approach doc: detection model, per-engine reliability, precedence, reporting.
- [x] Impl: `deriveSession()` / `geo_source` / `channel` shipped in `analytics.ts` (PR #9).
- [x] Cross-lead **UTM taxonomy contract** (§4) for geo / launch / social leads.
- [x] Server-log bot signal documented as optional complement.
- [ ] cmo confirms provider (Plausible) so the §5 dashboard can be wired.
- [ ] geo/launch/social leads adopt the §4 UTM scheme on seeded links.
