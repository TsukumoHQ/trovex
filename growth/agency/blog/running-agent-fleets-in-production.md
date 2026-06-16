---
title: "Running agent fleets in production: what it actually takes"
description: "Going from one agent to a fleet doing real work in production isn't a prompt change. It's four engineering layers (context, orchestration, observability, and an operating model your devs actually run). Here's the honest checklist."
slug: running-agent-fleets-in-production
date: 2026-06-16
author: tsukumo
audience: CTO / eng leadership
tags: [ai-agents, multi-agent, production-ai, engineering-leadership]
category: agency
---

# Running agent fleets in production: what it actually takes

**Short version:** one agent doing a task is a script. A fleet doing real work in production
is a system, and it needs four things the demo never shows: context the agents can trust,
orchestration so they don't collide, observability so you can run them on evidence not faith,
and an operating model your developers actually run. Skip any one and the fleet is expensive,
unreliable, or quietly abandoned. Here's the honest version of what's involved.

## 1. Context the agents can trust

An agent is only as good as what it knows about your codebase. At fleet scale, "let it read
the repo" is both expensive (every agent, every session, re-deriving the same things) and
wrong (it picks stale or duplicate docs). You need a context layer that serves the current,
canonical answer cheaply and on demand. Get this right and agents are fast and correct; get
it wrong and you're paying premium tokens for confident mistakes. (We built trovex for exactly
this, about 60% fewer tokens per doc lookup, because we hit the problem ourselves.)

## 2. Orchestration so the fleet doesn't collide

Two agents editing the same area, or duplicating each other's work, is worse than one agent
going slower. A fleet needs coordination: who owns what, in what order, how work is split and
merged, what happens when two agents disagree. This is the part teams underestimate most,
because with one agent it doesn't exist, and with five it's the whole game. (It's why we built
WRAI.TH.)

## 3. Observability so you run on evidence

You cannot operate in production what you cannot see. For a fleet you need to know, in close
to real time: what each agent did, what it cost, where it failed, and whether the output met
your bar. Without this, you're trusting a black box with commit access, which no serious team
will do for long. With it, agents become a measurable production system you can tune. (This is
what yoru is for.)

## 4. An operating model your devs actually run

The hardest layer isn't software. It's people. A fleet is operated, by developers who've
learned to set goals and guardrails, review at the right altitude, and intervene when needed,
instead of typing every line. That's a real skill shift, and it only sticks if the framing is
honest: the devs are the operators, the gains are theirs, and the agents don't replace them.
Teams that skip this get tools nobody trusts and everybody routes around.

## The honest part: it's mostly engineering, not prompting

Notice what's not on this list: clever prompts, a bigger model, more seats. Those help at the
margin. The fleet stands or falls on the four layers above, and they're ordinary, demanding
production engineering. That's good news, it means it's buildable, repeatable, and yours to
keep, not a magic trick. It's also why "buy licenses and hope" doesn't get a team there.

## How tsukumo does it

We run our own agent fleets in production to ship our software, and we built the four layers
(context, orchestration, observability, the operating model) because we needed them. When we
work with your team, we install that same stack on your environment and standards, and train
your developers to operate it, so the capability stays after we leave.

If you're trying to get from one agent to a fleet that actually runs in production, that's the
work we do. [Talk to us about your team.](https://tsukumo.ch)
