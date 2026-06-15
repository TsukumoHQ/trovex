# LinkedIn #2 — lesson from running agents at scale (DRAFT)

> **Status: DRAFT — do not post. A human (the founder) fires this.**
> This one barely mentions the product. It's an insight post — the agents-at-scale pain
> the consulting practice is actually about. trovex shows up once as "what I built for it".
> Link in first comment if you include one. No fabricated metrics.

---

## Post

The hardest part of running AI coding agents at scale isn't the model. It's keeping them all
working from the same truth.

One agent figures out the rollback procedure. The next session, a different agent re-derives
it from scratch — and maybe lands on the stale version. A teammate's agent has a third copy.
Nobody's wrong on purpose; the knowledge just never had one place to live, so it drifts.

A few things I've learned watching this happen across teams:

→ A single instructions file (CLAUDE.md / AGENTS.md) buys you a month. Then it's stale and
can't point to the right section.

→ Bigger context windows don't fix it. A big window isn't a *current* one. The agent still
has to find the right doc, and the cost compounds across every session and every agent.

→ The fix isn't "more context", it's "one point of passage". If every read and every write
goes through one shared store, there are no copies to drift. The agent that learns something
writes it once; every other agent — and every teammate — reads the same thing back.

That last idea is what I ended up building into a small open-source tool (trovex) so I could
stop hand-waving about it. But the tool is the easy part. The hard part is rolling this
discipline out across a team without slowing anyone down — which is most of what teams ask
me about.

If your agents are fast but inconsistent, that inconsistency is usually a knowledge-routing
problem, not a model problem. Happy to talk through it.

---

## Posting notes
- Optional link (repo) → first comment only. This post works fine with no link at all.
- Strongest as a standalone insight; let people ask "what's the tool?" in comments.

## Self-audit
- [x] Insight-led, product mentioned once. No numbers invented; ~60% not even needed here.
- [x] Consulting surfaces as "what teams ask me about" — subtle, end-weighted.
- [x] No banned words. Lowercase `trovex`. Founder voice.
