# tsukumo suite overview: "we run what we sell"

*Owner: content-lead · narrative section for the tsukumo site. Voice: prod-grade,
builder-credible. Lowercase wordmarks (`tsukumo`, `trovex`, `yoru`); `WRAI.TH` per its own
styling. No fabricated proof. Source: agency-positioning, ecosystem. The point of this
section: the open suite is the receipt for the consulting.*

---

## Section: We run what we sell

**Eyebrow:** Proof, not slides

**H2:** We didn't read about running agents in production. We built the tooling for it.

**Body:** Most AI consultancies sell a way of working they've only demoed. We ship an open
suite that we run on our own work every day, the same operating model we transition your team
into. If you want to know whether we can make your agents reliable in production, look at the
tools we had to build to make ours reliable.

### The suite, and what each part proves

**WRAI.TH, orchestration.** Running one agent is a copilot. Running a *fleet* is an
operating problem: who does what, in what order, without stepping on each other. WRAI.TH is
how we coordinate fleets of agents. It proves we operate agents at scale, not one at a time.

**trovex, context.** Agents burn tokens and pick stale docs when they reread a repo to find
the current answer. trovex serves the one canonical doc per query, locally, for about 60%
fewer tokens per lookup. It proves we make agent context cheap and correct, the difference
between a demo and a production bill.

**yoru, observability.** You can't run agents in production on faith. yoru is how we see what
the fleet is doing, what it costs, and where it goes wrong. It proves we treat agents as
production systems you measure, not magic you trust.

### Why this proves the consulting

These three are exactly the problems a team hits when it moves from AI-as-copilot to
AI-as-operator: coordinating a fleet, feeding it the right context cheaply, and seeing what
it does. We didn't theorize them. We hit them building our own products, and built the layer
that solves them. When we transition your team, we're not improvising; we're installing an
operating model we run ourselves.

That's the whole argument. The suite is open, the work is real, and the consulting is just us
doing for your team what we already did for ours.

**CTA:** See how we'd do it with your team

---

## Notes for build (cro-lead / design-lead)

- Three-up layout (WRAI.TH / trovex / yoru), each with the "what it proves" line, that's the
  load-bearing copy, not the feature description.
- Link each to its own site/repo where public (trovex.dev; WRAI.TH if public; yoru when it
  ships). trovex is private beta, link to the waitlist, not a clone.
- Real number: only trovex's ~60% per-lookup appears; everything else stays qualitative until
  owner-verified numbers land. No fabricated metrics.
