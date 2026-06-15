# Consulting page copy — "working with a team?"

*Owner: cro-lead · Conversion team · copy-gate. Implementation-ready page copy.*

Purpose: a low-key destination for the team-lead who's seen trovex work and wonders if
they can get help running coding agents well across their team. Feeds the consulting
funnel without turning the OSS into a sales page. **No hard sell. No Synergix brand.**
Founder-led, plain, competence-as-proof.

Where it lives: the landing's consulting line (`CONSULT_URL` in `web/src/App.tsx`) and
the README "Working with a team?" link should point here once it's a real page
(`/consulting` route or a static `consulting.html`). Until then this doc is the source
of truth for the copy. Wiring the page is a follow-up implementation task.

Voice: developer-honest, cost-framed, lowercase `trovex`, no hype. Banned words:
revolutionary, seamless, supercharge, unlock, "AI-powered". The number and the work do
the talking. No fake clients, no testimonials, no invented metrics (pre-launch).

---

## Page copy

### Hero
**H1:** Working with a team?

**Sub:** trovex is free to run yourself. If your team is rolling out coding agents on
real repos and wants it to actually pay off — fewer wasted tokens, one source of truth,
agents that don't re-derive each other's work — that's what the consulting is for.

**Primary CTA:** [Start a conversation →]  *(→ real contact: email / booking link)*
**Secondary (text link):** or just [use trovex](/) — it's yours, free.

### What this is
One person who builds this stuff, helping your team run AI coding agents well. Not a
platform, not a retainer you can't leave, not a rebrand of your stack. Hands-on, scoped,
and done when it's done.

### What help looks like
- **Rolling trovex out across a team** — shared source of truth, the write path wired so
  agents and teammates stop re-deriving the same things.
- **Cutting the token bill** — finding where your agents burn context (rereading docs,
  stale files, oversized prompts) and fixing the expensive parts first.
- **Agent workflows that hold up** — MCP setup, context hygiene, and conventions so a
  fleet of agents on one repo stays consistent instead of drifting.
- **Embedding/hosting trovex privately** — if you want to run a modified trovex inside
  your company without the AGPL's copyleft obligations, there's a commercial path. This
  is the natural reason most teams reach out.

### How it works
1. **A short call.** You describe your setup and what's hurting. If it's not a fit, you'll
   hear that — no pitch.
2. **A scoped plan.** What to change, in what order, what it should save. Fixed scope, not
   open-ended hours.
3. **The work.** Hands-on, with your team, until the agreed thing is done.

### Who it's for / not for
**A fit if:** a small-to-mid team runs coding agents on doc-heavy repos and the cost or
inconsistency is real. **Probably not yet if:** you're a solo dev with a tiny doc set —
trovex on its own already covers you, free.

### Pricing
No public price list — scope drives it, and a 20-person rollout isn't a 3-person fix.
The first call is free and tells you whether it's worth a number at all. Honest scope
over a fake "from $X" anchor.

### Close
**Heading:** See if it's worth a conversation.
**Body:** Bring your repo and your token bill. Worst case, you leave with a plan you can
run yourself.
**CTA:** [Start a conversation →]

---

## Implementation notes (for the follow-up task)
- Route: add `/consulting` (needs a router in the Vite app) **or** ship a static
  `web/public/consulting.html` styled with the brand tokens (green `#22c55e`, the mono
  face). Static is lower-risk and needs no router.
- Repoint `CONSULT_URL` (App.tsx) and the README link here once live.
- The **only real blocker** is the contact destination (still `TODO(human)` — email /
  Cal.com / form). Every CTA above routes to it. See project memory `cro-lead-human-todos`.
- Keep it one screen-ish; this is a low-intent-to-medium-intent bridge, not a long sales
  page. Analytics: track a `consulting_cta_clicked` event (coordinate with analytics-lead)
  to measure the funnel.

## Anti-patterns (refuse)
- Fake clients, logos, testimonials, or case-study numbers. None exist yet.
- Urgency/scarcity ("limited slots"). No.
- "Book a demo" SaaS theatre. It's a person; say so.
- Synergix branding or making trovex look like a paid product. trovex stays free OSS;
  consulting is the optional door.
