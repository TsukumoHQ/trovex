---
title: "One source of truth for a fleet of coding agents"
description: "When several agents and teammates work the same repo, they re-derive the same answers and write notes that drift. Here's why a shared read/write path beats scattered .md files, and what it changes."
slug: one-source-of-truth-for-a-fleet-of-agents
date: 2026-06-16
author: trovex
canonical_url: https://trovex.dev/blog/one-source-of-truth-for-a-fleet-of-agents
tags: [ai-coding-agents, multi-agent, ssot, mcp, developer-tools]
category: ssot-coordination
---

# One source of truth for a fleet of coding agents

**Short version:** one agent on one repo wastes tokens rereading docs. Several agents, or
several teammates, do something worse: they re-derive the same answers in parallel and
write what they learn into scattered files that quietly drift out of sync. The fix isn't
more docs or a bigger context window. It's one shared read/write path, so a thing learned
once is canonical for everyone who reads it next. This post is about the write side of that,
the part that only shows up once more than one agent touches the repo.

## What goes wrong when you add the second agent?

A single agent rereading docs is a cost problem. (We did the token math on that in
[the token cost of agents rereading docs](./the-token-cost-of-agents-rereading-docs.md).)
Add a second agent, or a teammate, and you get a consistency problem on top of it.

Three things start happening:

1. **Parallel re-derivation.** Your agent works out the rollback steps on Monday. Your
   teammate's agent works out the same rollback steps on Tuesday, from scratch, because it
   has no idea the first one already did. You pay twice for one answer.
2. **Drift.** Each agent writes its findings into its own `.md`, or a chat log, or a comment.
   Now there are three notes about rollback, written at three times, and nothing says which
   is current. The next reader guesses, and sometimes guesses wrong.
3. **Lost knowledge.** An agent figures out why the API returned 504s after a deploy, writes
   it into a session that ends, and the knowledge evaporates. The next incident re-runs the
   investigation.

None of this is fixed by a smarter agent or a larger window. It's a structural problem: there
is no single place where "what we know" lives.

## Why doesn't CLAUDE.md or a shared wiki solve this?

They solve a slice and then stop.

A `CLAUDE.md` or `AGENTS.md` is a single hand-maintained file. It works until the knowledge
outgrows one file, which is fast on a real project. It also assumes a human keeps it current;
agents generate knowledge faster than a person curates it, so it lags.

A wiki or a docs folder is many files with no canonical signal. It's exactly the pile the
single-agent post was about, now also being written to by several actors at once. More
writers, more drift.

What's missing in both is a **write path with a notion of canonical**: a place an agent can
save a finding such that the save itself makes it the current answer, and the older note is
marked superseded rather than left to compete.

## What a shared write path changes

The idea is small. Give every agent one place to read from and one place to write to, and
make that place the source of truth by construction.

Concretely, with trovex an agent can:

- **Write what it learns once.** An incident, a decision, "the rollback steps that actually
  worked", saved as a record through `trovex_write`. Not into a new loose file.
- **Read it back by meaning, at the section level.** The next agent asks a question and gets
  that record as the canonical answer, with a freshness marker, not a list of candidate
  notes to compare.
- **Supersede instead of duplicate.** A newer record on the same topic becomes canonical; the
  old one is marked, not deleted and not left to masquerade as current.

Because reads and writes go through one point, there are no copies to sync. The fleet and the
humans see the same store. A teammate reading at `/doc/{id}` sees exactly what the agents
see.

## A concrete walk-through

Two agents, one repo, one week:

1. **Monday: agent A** hits a 504 storm after a deploy, works out the cause (a connection
   pool exhausted by a migration), fixes it, and writes a record: *"incident: api 504s after
   deploy — pool exhausted by long migration; mitigation: cap migration concurrency."*
2. **Tuesday: agent B**, a different session on a teammate's machine, sees 504s again. It
   asks trovex "why would the api 504 after a deploy?" and gets agent A's record back as the
   canonical answer. It applies the known mitigation in minutes instead of re-investigating.
3. **Wednesday: the mitigation changes.** Someone lands a real fix. An agent writes the new
   record; trovex marks it canonical and the Monday note as superseded. Nobody has to
   remember to delete the old one.

The token saving (the ~60% from the first post) still applies to every one of those reads.
The new thing is that the *second* investigation never happened at all.

## Is this just a database for agents?

Sort of, with two differences that matter.

A plain database (or a vector store, or a notes app) gives you storage and retrieval. It
doesn't give you **canonical**: ask it a question and it returns whatever matches, ranked by
similarity, with no opinion about which is current. trovex's unit of output is the one
current answer with a freshness marker, and its write path supersedes rather than appends.

The second difference is that it's **the same store the agents already read code-context
from**, reached through the same MCP tool, local-first. There's no separate system for "agent
memory" to wire up and keep in sync. The read path and the write path are one path.

## When does this matter, honestly?

If you run one agent, in one session, on a small repo, the write path is a nice-to-have. The
single-agent token math is your main win.

It starts to matter the moment there's a *second* actor on the same repo: a second agent, a
second session that should remember the first, or a teammate. That's where re-derivation and
drift cost real time, and where keeping things consistent by hand stops scaling. If that's
your situation, the shared write path is the point, not a footnote.

## Request beta access

trovex is in private beta. [Request access at trovex.dev](https://trovex.dev) and we'll get
you set up. Then have one agent write a record (`trovex_write`) and another ask the question
it answers, and watch the second one get the answer back instead of working it out again.
It's licensed AGPL-3.0 (core) and MIT (CLI), and opens up more widely after the beta.

If you're rolling agents out across a team and the drift-and-re-derivation tax is real,
that's the kind of thing we help teams fix. Happy to talk.
