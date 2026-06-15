# Lead magnet: is your agent setup burning tokens?

*Owner: content-lead · 2026-06-15 · pairs with [content-strategy.md](./content-strategy.md)*

A self-serve audit a developer runs in five minutes to find out whether their coding agents
waste tokens rereading docs. It stands alone as useful even if they never talk to us. The
failing checks happen to be the ones that get worse at team scale, which is where consulting
lives. No email wall on this; it's a discovery + activation asset first.

---

## The magnet (publishable content)

### Is your coding agent burning tokens on docs? A 5-minute self-audit

Coding agents reread your repo's markdown every session to work out which doc is current,
then answer from a guess. You pay for that on every session, every agent, every teammate.
This audit tells you whether that tax is small or large for your setup, before you change
anything.

Score one point per "yes."

**Your docs**
- [ ] Your repo has more than ~20 markdown files (runbooks, ADRs, READMEs, wikis, notes).
- [ ] Two or more docs cover the same topic, and you couldn't say which is canonical without
      opening them.
- [ ] At least one doc is stale but still sitting in the repo where an agent can read it.
- [ ] You don't have a reliable signal (a marker, a convention) for "this is the current
      one."

**Your agents**
- [ ] Your agent lists or greps files, then opens several, before it answers a doc question.
- [ ] You've seen it cite or follow an old or duplicate doc.
- [ ] It re-reads the same files in a new session because nothing carried over.
- [ ] You run more than one agent, or more than one session a day, on the same repo.

**Your team**
- [ ] A teammate's agent re-derives things yours already figured out.
- [ ] Knowledge an agent discovered (an incident, a decision) lives only in a chat log, not
      anywhere the next agent can read it.
- [ ] Your `CLAUDE.md` / `AGENTS.md` has grown into a long blob that's half out of date.

**Your bill**
- [ ] You can't say how many tokens go to doc lookups versus real work.
- [ ] Your agent token spend is trending up and you're not sure which part is avoidable.

### Reading your score

- **0–3: low.** Your doc set is small or tidy. Rereading isn't your problem; keep your
  setup. (Honest answer: you probably don't need trovex yet.)
- **4–8: real tax.** You're paying for guessing on most sessions. A canonical-doc layer
  pays for itself quickly. This is the typical solo / small-repo case.
- **9+: compounding.** The cost multiplies across agents, sessions, and teammates, and the
  inconsistency is already causing wrong answers. This is the case that gets expensive fast
  and is hardest to fix by hand.

### What to do about it

1. **Measure it first.** Don't guess at the guessing. Point trovex at the repo and read the
   savings number on your own docs:
   ```bash
   uv run trovex index /path/to/your/repo
   uv run trovex serve   # dashboard at /
   ```
   The Savings tab shows would-have-read versus actual tokens. That's your real number.
2. **Make one doc per topic canonical.** Mark the current one; let the stale and duplicate
   copies be skipped instead of read.
3. **Give agents one read/write path.** When an agent learns something, it should save it
   once, where every other agent and teammate reads it back, instead of re-deriving it.
4. **Re-run the audit in a week.** The score should drop. If it doesn't, the bottleneck is
   somewhere else, and you've spent five minutes to learn that.

If you scored 9+ and you're rolling agents out across a team, the by-hand version of steps
2–4 is a real project. That's the kind of thing we help teams do well. [Working with a
team? Let's talk.](https://github.com/Synergix-lab/trovex)

---

## Funnel spec (internal)

**Type:** ungated self-audit (no email capture). Reach and activation matter more than a
contact form this early.

**Where it sits:**
- A section / standalone page off the token-economics cornerstone (links both ways).
- A short version pinned in the README and linked from the landing FAQ.
- The skimmable, screenshot-friendly format social-lead repurposes into a carousel / thread
  (drafts only).

**How it feeds consulting without selling:**
- The value is the audit itself; a low score honestly tells some people *not* to bother.
  That honesty is what makes the high-score readers trust the rest.
- The 9+ band names a team-scale, by-hand problem. The consulting line appears once, at the
  end, contextual to that band. It is never a gate and never a pitch.

**Funnel stages:** discovery (AI-citable checklist + comparison fodder) → activation (step 1
is "install and measure") → consulting path (9+ band only).

**Measurement (handoff to analytics-lead):** track audit-page views, install-line copies
from the page, and clicks on the consulting link. If high-score readers click through,
the magnet is doing its job.

**Honesty guardrails:** no fabricated proof; the only number is the real ~60%. The audit
makes the reader generate their *own* number rather than asserting one.
