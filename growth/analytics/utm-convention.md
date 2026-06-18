# Trovex — UTM Convention (every controlled link)

*Owner: analytics-lead · Status: v1 · Last updated: 2026-06-16*

The canonical reference every lead uses to tag outbound links to `trovex.dev`. Under the
private-beta GTM, **waitlist signup is the primary conversion**, so getting `utm_*` on the
links we control is what makes "signups by source" real. UTMs are also the only reliable
AI-engine signal (those referrers get stripped). Pairs with referrer-host fallback in
`geo-attribution.md` for links we *don't* control.

> One rule: **if you place a link to trovex.dev anywhere you control, it carries these
> params.** Lowercase, no spaces, closed `utm_source` list.

---

## 1. The four parameters

| Param | Meaning | Rule |
|-------|---------|------|
| `utm_source` | where the click physically comes from | closed list below; must match `web/src/analytics.ts`. Unmapped → silently `referral`/`unknown`. |
| `utm_medium` | kind of placement | closed: `ai_answer`, `organic`, `social`, `community`, `registry`, `referral`, `email`, `dm` (1:1 direct message), `paid`. |
| `utm_campaign` | the initiative | kebab-case, reuse names: `private-beta`, `geo-seed`, `comparison-pages`, `newsletter`, `agency-launch` (the tsukumo/agency launch push), `launch-hn`, `launch-ph`, `lead-nurture` (post-capture nurture sequence), `reengage` (re-engagement series). |
| `utm_content` | which variant/placement of the link | distinguishes A/B variants & placements: `cta-hero`, `cta-footer`, `post-1`, `thread-tweet-3`, `vs-mem0`, `card-a`. Powers per-variant attribution. |

`utm_content` is the new one: it's how we tell apart two versions of the same campaign
(e.g. an A/B on the "request beta access" copy → `utm_content=cta-a` vs `cta-b`) and which
specific post/placement drove a signup.

## 2. `utm_source` closed list (matches `analytics.ts`)

| Surface | `utm_source` | → `geo_source` |
|---------|-------------|----------------|
| ChatGPT answer/citation | `chatgpt` | `chatgpt` (ai_engine) |
| Perplexity | `perplexity` | `perplexity` (ai_engine) |
| Claude | `claude` | `claude` (ai_engine) |
| Gemini | `gemini` | `gemini` (ai_engine) |
| Google (organic / AI Overviews) | `google` | `search` |
| Bing / Copilot | `bing` / `copilot` | `bing` / `copilot` |
| Hacker News / Reddit / Lobsters / X / LinkedIn | `hackernews` / `reddit` / `lobsters` / `x` / `linkedin` | `social` |
| Product Hunt | `producthunt` (alias `ph`) | `social` |
| MCP registry / directory | `mcp-registry` (or specific slug) | `referral` |
| Newsletter / Discord | `newsletter` / `discord` | `referral` / `social` |

> Need a source not listed? **Ping analytics-lead to add it to the `analytics.ts` map
> first** — otherwise it degrades to `referral`/`unknown` and that channel's ROI vanishes.

## 3. Ready-to-use templates (per lead)

Base: `https://trovex.dev/?utm_source=…&utm_medium=…&utm_campaign=…&utm_content=…`

| Lead / channel | Example |
|----------------|---------|
| geo-lead — comparison page seeded in a Perplexity answer | `?utm_source=perplexity&utm_medium=ai_answer&utm_campaign=comparison-pages&utm_content=vs-mem0` |
| geo-lead — AEO/answers page | `?utm_source=chatgpt&utm_medium=ai_answer&utm_campaign=geo-seed&utm_content=answers` |
| social-lead — X thread | `?utm_source=x&utm_medium=social&utm_campaign=private-beta&utm_content=thread-1` |
| social-lead — LinkedIn post | `?utm_source=linkedin&utm_medium=social&utm_campaign=private-beta&utm_content=post-1` |
| launch-lead — registry listing (when public phase opens) | `?utm_source=mcp-registry&utm_medium=registry&utm_campaign=launch&utm_content=listing` |
| launch-lead — Product Hunt launch | `?utm_source=producthunt&utm_medium=social&utm_campaign=agency-launch&utm_content=ph-tagline` |
| content-lead — newsletter | `?utm_source=newsletter&utm_medium=email&utm_campaign=private-beta&utm_content=issue-1` |
| social — lead-nurture email (to tsukumo `/engagements`) | `?utm_source=trovex&utm_medium=oss-suite&utm_campaign=lead-nurture&utm_content=nurture-e<N>` (waitlist) · `?utm_medium=email&utm_campaign=lead-nurture&utm_content=nurture-e<N>` (contact) — see `retention-cohort-spec.md` |
| community — Discord drop | `?utm_source=discord&utm_medium=community&utm_campaign=private-beta&utm_content=mcp-server` |

Ownership: geo-lead tags GEO/SEO + comparison/answers links; social-lead tags social;
launch-lead tags registry/launch (held until public phase); content-lead tags
newsletter/blog; analytics-lead owns the `utm_source` map.

## 4. Capture at the waitlist (so signups are attributed)

The web layer reads `utm_*` into closed-enum session props (`deriveSession()` /
`getAttribution()` in `analytics.ts`). On signup, the form **POSTs `getAttribution()` with
the request**, and the waitlist endpoint **persists it next to the email**:

```
{ email, created_at,
  geo_source, channel,
  utm_source, utm_medium, utm_campaign, utm_content,
  referrer }   // host only
```

Now every signup is traceable to a source — even for AI-engine/dark-social clicks that
stripped the UTM, via the `referrer`-host fallback (`geo-attribution.md`).

**Privacy:** the email lives only in the first-party waitlist store; it is **never** sent
to analytics. `utm_*` and `referrer` carry no PII (host-only, closed enums). See
`waitlist-tracking.md` §3.

## 5. Into the north-star report

`north-star-report-template.md` leads with **`waitlist_submitted` by source**. UTM
coverage (% of signups carrying a known `utm_source`) is itself a tracked health metric —
low coverage means leads aren't tagging links, and AI-engine ROI decays into `direct`.

## 6. Acceptance

- [x] Four-param convention (incl. `utm_content`) with closed lists.
- [x] `utm_source` list matches `analytics.ts`; per-lead ready-to-use templates.
- [x] Waitlist capture spec — persist attribution with each signup; referrer fallback for stripped UTMs.
- [x] Privacy: email never in analytics; UTM/referrer carry no PII.
- [x] Wired into the north-star report (signups by source + UTM-coverage health metric).
