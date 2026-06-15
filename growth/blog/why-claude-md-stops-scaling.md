---
title: "Why CLAUDE.md stops scaling (and what to do about it)"
description: "A single CLAUDE.md or AGENTS.md is the right tool for a few stable rules. Here's the point where one static file goes stale, costs tokens on every session, and can't route a question to the right doc, and what canonical + freshness fixes instead."
slug: why-claude-md-stops-scaling
date: 2026-06-16
author: trovex
canonical_url: https://trovex.dev/blog/why-claude-md-stops-scaling
tags: [ai-coding-agents, claude-md, agents-md, context, mcp]
category: token-economics
---

# Why CLAUDE.md stops scaling (and what to do about it)

**Short version:** a `CLAUDE.md` or `AGENTS.md` is one static file your agent loads in full
every session. For a short, stable set of rules (build commands, conventions, "always run
the tests") it's perfect: zero infrastructure, always in context. It breaks down when your
real project knowledge outgrows one file, because a single blob goes stale, costs tokens on
every session whether or not a topic is relevant, and can't route a specific question to the
specific doc that answers it. The fix isn't a longer CLAUDE.md. It's keeping the file small
and letting a canonical, freshness-aware index carry the rest.

## What CLAUDE.md is good at

Give the agent a tight set of rules it should always know: how to build, how to run tests,
the conventions you care about, the one or two gotchas that bite everyone. That belongs in
`CLAUDE.md` (or `AGENTS.md`, the cross-tool equivalent). It's a clean fit: no infrastructure,
it's always loaded, and it's small enough to maintain by hand. Keep doing this. None of what
follows is an argument against having one.

## The failure mode: the file becomes a knowledge base

The trouble starts when the file stops being a list of rules and starts being where project
knowledge lives. Deploy steps go in. Then the rollback procedure. Then an architecture note,
a few "don't touch this" warnings, the auth flow, a postmortem summary. Each addition feels
reasonable. The file grows from a sticky note into a wiki that happens to be one file.

At that point three structural limits show up. They aren't bugs you can fix by writing the
file better; they're properties of "one static blob."

### 1. It goes stale, silently

The file is a copy of knowledge that lives elsewhere (the actual runbook, the ADR, the
code). When the source changes, the blob doesn't, and nothing flags the gap. Your agent then
reads confident, outdated instructions and acts on them. A stale doc that looks current is
worse than no doc, because the agent trusts it.

### 2. It costs tokens on every session, for every topic

One file is loaded whole. So every topic you add is paid for on every session, by every
agent, whether or not the current task touches it. A 40-section CLAUDE.md spends 40 sections
of tokens to answer a question that needed one. That's the same compounding cost as agents
rereading the repo, just moved into the context window up front. (The token math is in
[the token cost of agents rereading docs](./the-token-cost-of-agents-rereading-docs.md).)

### 3. It can't route

There's no "which part answers this?" step. The agent gets the same fixed text for every
query. When the answer isn't in the blob, it falls back to rereading the repo to find
specifics, which is the cost you were trying to avoid. A static file has no notion of "this
section is the canonical answer to that question."

## What actually fixes it: canonical + freshness + routing

The missing pieces are an index that can route a question to the right doc, a freshness
signal so stale and duplicate copies are marked instead of trusted, and section-level reads
so a short answer costs short-answer tokens.

That's what trovex does. It indexes your markdown and serves your agent the single current
doc that answers a query, as a `path:line` pointer with a freshness marker (canonical,
stale, or duplicate), and hands back just the section that answers. The corpus can grow
without the per-session cost growing, because cost scales with the question, not the size of
the knowledge base.

The two are complementary, not either/or: keep a small `CLAUDE.md` for stable rules, and let
trovex carry the docs that change and multiply. If you want the side-by-side decision view,
see the [trovex vs CLAUDE.md comparison](https://trovex.dev/vs/claude-md/).

## A simple test

Open your `CLAUDE.md`. If it's a short list of rules you'd happily read top to bottom, it's
doing its job; leave it. If it's scrolled into a sprawling knowledge dump where half the
sections are irrelevant to any given task and you're not sure which parts are still true,
that's the signal. The file outgrew the format.

## Request beta access

trovex is in private beta. [Request access at trovex.dev](https://trovex.dev) and we'll get
you set up, so you can keep your `CLAUDE.md` small and let trovex carry the rest. It's
licensed AGPL-3.0 (core) and MIT (CLI), and opens up more widely after the beta.

If your team's CLAUDE.md has turned into an unmaintainable knowledge base, untangling that is
the kind of thing we help teams with. Happy to talk.
