# The suite — positioning one-pager (DRAFT)

**Status:** DRAFT / copy only. Shared reference for every tool's launch copy. Nothing posted.
**Owner:** launch-lead · **Reviewed against:** mission, ecosystem, agency-identity, voice, no-synergix-mention, copy-gate
**Repos:** wrai.th (github.com/Synergix-lab/WRAI.TH, public v1.0) · trovex (private beta) · yoru.sh (early, not public yet)

> Purpose: one honest story for how the three OSS tools fit, so each tool's launch copy cross-references the
> suite instead of standing solo. The tools are the funnel; **Tsukumo** (tsukumo.ch) is the consulting agency
> they feed. Brand: lowercase wordmarks; no "Synergix" in prose (GitHub org / URL identifiers only).

---

## The one-line story

**Run a fleet of AI coding agents in production — and actually keep it under control.**
Three local-first, AGPL tools, one layer each:

- **wrai.th** — *orchestration.* Mission control for an agent fleet: persistent memory, inter-agent
  messaging, a shared task board, one dashboard. (public, v1.0 stable)
- **trovex** — *context.* The canonical doc store: serves each agent the one current doc (path:line +
  freshness) instead of a repo reread. ~60% fewer tokens. (private beta)
- **yoru** — *observability.* Know what your agents did overnight: see the runs, decisions, and outcomes.
  (early — not yet public)

They reinforce each other: a wrai.th fleet uses trovex for one shared source of truth and yoru to see what
happened. Use any one alone; together they're a way to run agents at scale without flying blind.

---

## The layers (how they fit)

```
            ┌─────────────────────────────────────────────┐
            │  yoru — observability                        │
            │  "what did the fleet actually do?"           │
            ├─────────────────────────────────────────────┤
            │  wrai.th — orchestration                     │
            │  memory · messaging · tasks · dashboard      │
            ├─────────────────────────────────────────────┤
            │  trovex — context / SSOT                     │
            │  one canonical doc per query, fewer tokens   │
            └─────────────────────────────────────────────┘
              your AI agents (Claude Code, Cursor, …) via MCP
```

- **trovex** answers "what's the current truth?" (context layer).
- **wrai.th** answers "who's doing what, and do they remember?" (coordination layer).
- **yoru** answers "what happened, and was it right?" (visibility layer).

All three are MCP-native, local-first, AGPL — same design values, different question.

---

## Why a suite, not one mega-tool (the honest framing)

Each tool is genuinely useful alone — that's the point, and the install pitch only works if it's true:
- Run wrai.th without trovex or yoru: you still get fleet orchestration.
- Run trovex without wrai.th: you still cut token cost on doc lookups for a single agent.
- They're not bundled or locked together. Pick the layer you need; add the next when the pain shows up.

This is the opposite of a monolith: small, composable, local tools that each earn their place, and compound
when combined.

---

## Cross-reference rules (apply to every tool's launch copy)

So the suite is discoverable without any tool's copy turning into an ad for the others:
- One **low-key suite line** near the top of each README / landing: e.g. trovex → "pairs with your
  orchestrator (wrai.th) and observability (yoru) — part of the suite." Keep it a footnote, not a pitch.
- **Comparison framing — important fix:** trovex *complements* orchestration tools, it is not always their
  competitor. On comparison pages, trovex = the context/SSOT layer that sits *under* an orchestrator. Don't
  frame trovex vs. wrai.th as rivals; frame them as adjacent layers.
- Each tool links the others by their honest one-liner (above), never with inflated claims.
- Consulting stays out of the OSS surfaces except a single quiet line, and only once tsukumo.ch is live:
  "running agent fleets across a team? we do that — [Tsukumo]." No company name until the site exists.

---

## The funnel (where this points)

```
dev finds wrai.th (HN / registries / Go ecosystem — biggest TOF)
   → discovers the suite (trovex, yoru) via the cross-links
   → runs agents better, sees the value
   → "this team clearly knows how to run agent fleets"
   → Tsukumo consulting lead  ← the business (north star)
```

- **wrai.th is the widest mouth** of the funnel (public + stable) — lead with it.
- **trovex** reinforces (context/token story) once its beta → public.
- **yoru** reinforces (visibility story) once it's public.
- The suite is the **proof of competence**; the agency is what's actually sold.

---

## Honesty + brand guardrails

- Real facts per tool only. wrai.th: v1.0 stable, real install. trovex: ~60% repo-dependent, private beta.
  yoru: early, not public — **do not imply it's shippable yet**; describe the intent, flag "coming."
- No fabricated stars/users/testimonials for any tool.
- Lowercase wordmarks (`wrai.th`, `trovex`, `yoru`). No "Synergix" in prose. Tsukumo only once its site is live.
- Run anti-ai-slop on any surface that uses this.

## Handoffs

- content-lead: this one-pager is the source for the suite line in each README/landing + the agency site's
  "the stack" section. Align wording.
- design-lead: a suite diagram asset (the layer stack above) for landings + the agency site.
- geo-lead: comparison pages should use the "trovex complements orchestration" framing, not rival framing.
- cmo: decide the public sequence — fire wrai.th first (widest TOF), or hold for the suite + agency story to
  land together.

*This is a draft reference. Nothing has been posted.*
