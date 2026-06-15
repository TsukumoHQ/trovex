---
title: "trovex is in private beta: here's why, and how to get in"
description: "trovex is opening as a private beta instead of a public release. Here's the honest reasoning: get it right with a small group of real users before opening the doors, and how to request access."
slug: trovex-is-in-private-beta
date: 2026-06-16
author: trovex
canonical_url: https://trovex.dev/blog/trovex-is-in-private-beta
tags: [trovex, private-beta, build-in-public, ai-coding-agents]
category: announcements
---

# trovex is in private beta, here's why, and how to get in

**Short version:** trovex (the canonical doc store that stops your coding agents rereading
the repo, for about 60% fewer tokens per lookup) is opening as a private beta, not a public
release. We'd rather get it right with a small group of real users than ship wide and learn
in public. If your agents work a doc-heavy repo and the token bill bugs you,
[request access at trovex.dev](https://trovex.dev).

## Why private, and why now

The tool works. The reason to gate it isn't readiness theater. It's that the next thing
trovex needs is something you can't get from more solo building: a handful of real repos,
real agent traffic, and honest feedback about where it helps and where it doesn't.

Two concrete reasons:

1. **Proof before promises.** trovex is pre-launch with zero customers. The only number we
   stand behind is the ~60% fewer tokens per doc lookup, measured on our own repos. Before
   we say it louder, we want that number confirmed on *your* repo, in your words, not ours.
   A private beta is how we earn the right to make the claim publicly.
2. **Polish where it counts.** Setup, the savings dashboard, the agent wiring: these get
   sharper fastest with a small group we can actually talk to. Ship to everyone at once and
   the feedback is noise; ship to a few and it's signal.

No fake scarcity here. It's private because that's the honest way to get a tool from "works
on my machine" to "works on yours," not to manufacture a waitlist.

## What you get as an early tester

- **Hands-on setup.** We help you index your repo and wire your agent, and we watch where it
  snags so we can fix it.
- **Your own savings number.** Not our ~60%. Yours, on your docs, from the dashboard. If it's
  low, we'll tell you trovex isn't worth it for your setup.
- **A direct say in the roadmap.** Small group, short feedback loop. What you hit shapes what
  we build next.

## What we want back

Honest feedback, including the unflattering kind. Where setup confused you, where the
canonical answer was wrong, where the savings were smaller than you hoped. That's the whole
point of a beta. If it turns out trovex doesn't fit your workflow, that's a useful result,
not a failure.

## How to request access

Head to [trovex.dev](https://trovex.dev) and request beta access. Tell us a little about
your repo and how your agents use it, so we can prioritize setups where trovex will actually
help. We'll be in touch to get you running.

It's still open source under the hood (core AGPL-3.0, CLI MIT); the beta gates access while
we work with early testers, not the license. If you're running agents across a team and want
hands-on help doing it well at scale, that's the kind of thing we do, and a good reason to
reach out.

Want the background on what trovex does and the token math behind the ~60%? Start with
[the token cost of agents rereading docs](./the-token-cost-of-agents-rereading-docs.md).
