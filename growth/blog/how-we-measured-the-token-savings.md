---
title: "How we measured ~60% fewer tokens (and how to check it on your own repo)"
description: "A claim with no method behind it is just a number. Here's exactly what the ~60% counts, the two ways trovex computes it, and the command that runs the before/after on your own logs so you can get your own figure instead of trusting ours."
slug: how-we-measured-the-token-savings
date: 2026-06-22
author: trovex
canonical_url: https://trovex.dev/blog/how-we-measured-the-token-savings
tags: [ai-coding-agents, tokens, benchmark, methodology, cost]
category: token-economics
---

# How we measured ~60% fewer tokens (and how to check it on your own repo)

**Short version:** the ~60% is a reduction on the tokens an agent spends *locating* docs, not
on your whole session. We compute it two ways: a per-query estimate the CLI shows you live,
and a real before/after that reads your agent's actual file-read logs. The second one is the
honest one, because it runs on your numbers, not ours. The point isn't a fixed percentage.
It's a method you can run yourself.

## What the number actually counts

It counts `.md` doc lookups by a coding agent, and nothing else.

Without trovex, an agent that needs a current answer typically globs and greps, then reads two
or three candidate `.md` files to work out which one is current. With trovex it gets one
ranked, freshness-marked answer and reads the **one canonical doc** (or zero, if every
candidate is stale). The saving is the tokens it didn't have to read.

So `~60%` is a reduction on doc-lookup token spend. It is not a claim about your total bill, and
the tilde is doing real work: the figure depends on your corpus (how many overlapping or stale
`.md` files you have) and your agent's habits. We don't claim a universal constant. We claim a
method.

## The two ways we compute it

### 1. The per-query estimate (what the CLI shows live)

For each query, trovex estimates the work it saved:

```
would_have_read = tokens of the top 3 candidate docs   # the triage an agent skips
actual_read     = tokens of the top 1 canonical doc    # what it reads instead
saved           = would_have_read - actual_read - (small pointer response)
ratio           = saved / would_have_read
```

This is shown per query in `trovex search` and aggregated on the savings dashboard. Be clear
about what it is: an estimate of avoided work. It assumes the unaided baseline is "read the top
three candidates," which is the common triage pattern, not a law. Useful as a live signal,
but it's a model, so we don't rest the claim on it.

### 2. The real before/after (the one to trust)

The honest number doesn't model anything. It reads the actual `.md` read events your agent
logged and compares two time windows:

```
baseline window (before routing through trovex)  ->  tokens per .md read
current  window (with trovex routing)            ->  tokens per .md read
delta = 1 - current / baseline
```

One command:

```bash
uv run trovex measure        # default: prior 7 days vs last 7 days
```

It prints both windows, the delta, a verdict, and the paths costing you the most tokens. This
is the figure a skeptic should trust, because it's built from your logs, not our assertion.

## How to get your own number

1. Install the baseline hook so your agent's `.md` reads get logged.
2. Work normally for a few days **without** routing through trovex. That's your baseline.
3. Index your repo and route your agent through trovex. That's your current window.
4. Run `uv run trovex measure` and read the delta on your own corpus.

If your number comes in under 60%, that is the honest answer for your repo, and it's the one
you should act on. A team drowning in duplicate runbooks will see more; a tidy repo with one
doc per topic already does some of this by hand and will see less. The method tells you which
you are.

## The honesty rules we hold ourselves to

- We're pre-launch with zero customers, so there are **no customer numbers** here. Any
  dashboard figure you see in a screenshot is the product UI with illustrative data, labelled
  as such, not a result from someone's repo.
- The per-query estimate and the real before/after are different measurements. We don't dress
  the estimate up as a measured result. When we say "measured," we mean `trovex measure`.
- The tilde stays. No bare "60%", no "up to", no best case painted as typical.

This is the same shape of proof a tool earns trust with when it has no logos to show yet: a
quantified claim wired to a method you can reproduce. The
[per-lookup math is here](./the-token-cost-of-agents-rereading-docs.md), and how it compounds
across a fleet is [here](./token-economics-of-agent-fleets.md). This post is the part where you
stop reading our numbers and run your own.

---

*trovex is one canonical doc for your coding agents, about 60% fewer tokens per lookup.
It's open source and in public beta. [Install it and run `trovex measure` on your own
repo.](https://github.com/TsukumoHQ/trovex)*
