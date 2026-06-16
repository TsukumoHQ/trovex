---
title: "Why your coding agent keeps picking the stale doc (and how to fix it)"
description: "Retrieval ranks docs by similarity, and a stale doc is just as similar to a query as the current one. That's why agents cite outdated runbooks. The fix is a freshness signal, not a better embedding."
slug: why-agents-pick-stale-docs
date: 2026-06-16
author: trovex
canonical_url: https://trovex.dev/blog/why-agents-pick-stale-docs
tags: [ai-coding-agents, rag, freshness, context, mcp]
category: ssot-coordination
---

# Why your coding agent keeps picking the stale doc (and how to fix it)

**Short version:** your agent picks the outdated runbook because the tools it uses rank docs
by *similarity to the query*, and a stale doc is usually just as similar as the current one.
Nothing in plain search or RAG knows which copy is authoritative. The fix isn't a better
embedding model. It's a freshness signal attached to each doc (canonical, stale, duplicate)
so the wrong copy gets skipped instead of ranked.

## Why does it pick the old one at all?

Because "most relevant" and "most current" are different questions, and your tools only
answer the first.

When an agent searches your docs (grep, plain RAG, a vector store), the ranking is by
semantic or lexical similarity to the query. An old `wiki/old-deploy.md` and the current
`deploy/runbook.md` are *about the same topic*, so they score about the same. The stale one
often scores higher, because stale docs tend to be longer and more keyword-dense (they
accreted edits before being abandoned). The agent has no signal that says "this one was
superseded," so it picks by relevance and sometimes lands on the corpse.

## Why a better embedding model won't save you

Teams reach for a fix at the wrong layer: a bigger model, a re-ranker, hybrid search. Those
improve *relevance*. They make the agent better at finding docs about deploys. They do
nothing about *currency*, because currency isn't in the text. Two docs can be equally,
correctly about rolling back a deploy while one is six months out of date. No amount of
semantic horsepower distinguishes them, because the distinction isn't semantic.

This is why "we improved retrieval and it still cited the old doc" is such a common, baffling
result. You optimized the axis that wasn't the problem.

## The actual fix: a freshness signal

Currency has to be tracked explicitly and returned with the result. Concretely:

- **Mark each doc** canonical, stale, or duplicate, based on which is the authoritative copy
  for its topic, not on how it reads.
- **Return that marker with the answer**, so the agent (and you) can see "this is the current
  one" instead of guessing from rank.
- **Skip the stale and duplicate copies** before they reach the context window, so they can't
  be picked and can't be paid for.

trovex does this: a query returns the single current doc as a `path:line` pointer *with* a
freshness marker, and the superseded copies are marked and skipped rather than ranked. When
an agent writes an updated answer, the older one is marked superseded automatically, so the
signal stays true without hand-maintenance. (Why a static `CLAUDE.md` can't carry this is in
[why CLAUDE.md stops scaling](./why-claude-md-stops-scaling.md).)

## How is this different from just deleting old docs?

You could delete stale docs, and sometimes you should. But teams keep them on purpose:
postmortems, superseded ADRs, "here's what we tried and why it failed" are valuable history
you don't want erased, just *not served as current*. A freshness marker keeps the history
readable while stopping it from masquerading as the answer. Deletion is lossy; marking is
not.

## See it on your own docs

The fastest check is to watch the freshness markers on your own overlapping docs: ask a
question your repo answers in more than one place, and see which trovex returns canonical
versus skips as stale.

trovex is in private beta. [Request access at trovex.dev](https://trovex.dev) and we'll get
you set up. If your team's agents keep acting on outdated docs and it's causing real
mistakes, that's the kind of thing we help fix. Happy to talk.
