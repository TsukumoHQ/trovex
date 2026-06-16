---
title: "The token economics of running a fleet of coding agents"
description: "One agent rereading docs is a rounding error. A fleet of agents across a team, every session, is a budget line. Here's the multiplication that makes doc-context cost add up, and where to cut it."
slug: token-economics-of-agent-fleets
date: 2026-06-16
author: trovex
canonical_url: https://trovex.dev/blog/token-economics-of-agent-fleets
tags: [ai-coding-agents, tokens, cost, multi-agent, mcp]
category: token-economics
---

# The token economics of running a fleet of coding agents

**Short version:** the cost of an agent rereading your docs looks trivial per lookup, then
you multiply it by every lookup, every session, every agent, and every teammate. At fleet
scale the doc-context slice of your token bill is a recurring line item, not a rounding
error. Most of it is spent re-deriving answers you already paid for. Serving one canonical
doc per query (about 60% fewer tokens per lookup) compounds the same way the waste does, just
in the other direction.

## Why does doc-context cost feel invisible?

Because you meet it one lookup at a time, and one lookup is cheap.

An agent reads a few candidate `.md` files to find the current one: maybe 700 tokens. At
fractions of a cent, who cares. The cost is invisible because it never arrives as a single
bill. It arrives as a small tax on every interaction, and you only feel it at the end of the
month as "why is our spend creeping up."

## The multiplication that actually matters

Doc-context cost isn't a number. It's a product:

```
lookups per session  ×  sessions per day  ×  agents  ×  teammates  ×  days
```

Walk one plausible small-team case (illustrative, not a benchmark; plug in your own):

- 8 doc lookups in a session
- 4 sessions a day
- 2 agents per dev (an editor agent + a background one)
- 4 devs on the team
- 20 working days

That's 8 × 4 × 2 × 4 × 20 = **5,120 doc lookups a month**. At ~700 tokens of candidate-reading
each, that's ~3.6M tokens a month spent *locating* docs, before the agent does any actual
work with them. Most of those lookups are the same handful of questions ("how do we deploy?",
"what's the auth flow?") answered from scratch each time.

The point isn't the exact figure. It's that every term in that product is a multiplier, and
none of them shrink on their own. They grow as you add agents and people.

## Where the waste concentrates

Three places, all of which scale with the fleet:

1. **Re-location.** Every agent rereads the repo to find which doc is canonical, because the
   last agent's discovery didn't persist. Pure duplication.
2. **Stale-context drag.** When the candidate pile includes stale and duplicate files, the
   agent pays to read them *and* sometimes answers from the wrong one, which costs a
   correction cycle later.
3. **Re-derivation.** An agent works out a non-obvious answer (the real rollback steps), the
   session ends, and the next agent on the team derives it again from zero.

A bigger context window doesn't touch any of these. It makes each lookup *bigger*, not
rarer.

## What cutting it looks like

The lever is to stop paying for location and re-derivation. Serve the agent the one current
doc that answers a query (a `path:line` pointer with a freshness marker), at the section
level, and let agents write what they learn back through one shared store so the fleet reads
it instead of re-deriving.

That's about 60% fewer tokens per doc lookup (the per-lookup math is in
[the token cost of agents rereading docs](./the-token-cost-of-agents-rereading-docs.md)),
and because it sits inside the same multiplication, the saving scales with the fleet exactly
as the waste did. The shared-write side is covered in
[one source of truth for a fleet of agents](./one-source-of-truth-for-a-fleet-of-agents.md).

## How do I find my own number?

Measure the slice before you decide it matters. trovex ships a savings dashboard that shows
would-have-read versus actual tokens on doc lookups across your sessions, so you see the
fleet-level number on your own repo rather than trusting a blog post's arithmetic.

trovex is in private beta. [Request access at trovex.dev](https://trovex.dev) and we'll get
you set up. If you're running agents across a team and want help sizing and cutting this at
scale, that's the kind of thing we do. Happy to talk.
