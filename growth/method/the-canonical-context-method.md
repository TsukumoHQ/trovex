---
title: "The Canonical Context Method"
description: "Practices for running coding agents on real work. The model is the part you can't control; the context you feed it is the part you can. Nine principles for keeping that context one current, canonical answer instead of a pile of candidates the agent has to guess from."
slug: method
route: /method
canonical_url: https://trovex.dev/method
author: trovex
date: 2026-06-22
tags: [ai-coding-agents, method, canonical-context, operating-layer, ssot]
---

# The Canonical Context Method

**Practices for running coding agents on real work.**

An agent's output is a function of two things: the model, and the context you feed it. You
can only rent the first. You own the second. Most teams spend their attention on the part they
can't control and neglect the part they can.

This is the method we use, and the one trovex is built to support. It isn't about a smarter
model. It's about handing the agent one current, canonical answer instead of a pile of
candidates to rank. Nine principles, in three parts.

## Direction

### 1. One question, one canonical answer
For any question an agent asks your repo ("how do we deploy?", "what's the auth flow?"), there
should be exactly one doc that answers it, and everyone should know which one. Parallel
near-copies are the root cause of drift. When two docs answer the same question, the agent
picks one at random, and half the time it's the wrong one.

### 2. Current beats complete
Retrieval ranks docs by similarity, and a stale doc is exactly as similar to a query as the
current one. Without a freshness signal the agent has no way to prefer the doc that's still
true. A short, current answer beats an exhaustive, out-of-date one. Mark what's current; let
the rest age out of the way.

### 3. Write the answer where every agent reads
A canonical answer that lives in one agent's session memory isn't canonical. It's a private
note. The answer has to live on a shared read/write path that every agent and every teammate
reads from and writes to, or each one re-derives it and the copies drift apart.

## Building

### 4. Don't make the agent re-derive
Before an agent does anything useful, it reads candidate files to find which one is current.
That work is pure overhead, and it repeats every session, every agent, every teammate. Locate
the answer once, serve it, and stop paying to re-find it. Serving one canonical answer instead
of read-and-rank is about **60% fewer tokens per lookup** (measured, not asserted).

### 5. Ground before you reason
When an agent gets real work wrong, the failure is usually procedural, not a reasoning gap: it
worked from a stale runbook and reasoned perfectly from a wrong premise. Fix the premise
first. Grounding the agent in the current constraints moves the outcome more than a model
upgrade, and costs nothing in model spend.

### 6. Verify against the canon, not the vibe
"It felt better" hides regressions. Before an agent's answer ships, check it against the
canonical doc it should have used. If the answer and the canon disagree, one of them is wrong,
and you want to know which before the agent acts on it.

### 7. Keep it local
The context an agent reads on every call should be served from where it works, not fetched
across a network round-trip each time. Local is faster, it's cheaper, and it keeps your docs
your docs.

## Maintenance

### 8. Prune to keep one source of truth
A source of truth degrades the moment a second copy appears. Before you write a new doc, search
for the one that already covers the question and update that instead. Pruning duplicates isn't
cleanup you do later; it's how the canon stays canonical.

### 9. Measure the tax
The cost of an agent re-finding docs is invisible because you meet it one cheap lookup at a
time. It only shows up at the end of the month as "why is our spend creeping up." Measure the
doc-locating slice directly so you can watch it shrink when you fix it.

---

## How this maps to trovex

trovex is the tool we built to run this method: one canonical doc per question, marked current,
served locally to every agent that asks. It's open source and in public beta.
[Install it and see your own number.](https://github.com/TsukumoHQ/trovex)

If your team is running agents on real work at scale and the operating layer is where it hurts,
that's the work we do. [Let's talk.](https://tsukumo.ch)
