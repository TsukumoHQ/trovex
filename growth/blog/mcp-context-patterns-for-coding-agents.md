---
title: "MCP context patterns for coding agents: dump, retrieve, or answer"
description: "Three ways to feed a coding agent project context over MCP: dump the repo, return candidate chunks, or serve one canonical answer. What each costs, when each fits, and how to choose."
slug: mcp-context-patterns-for-coding-agents
date: 2026-06-16
author: trovex
canonical_url: https://trovex.dev/blog/mcp-context-patterns-for-coding-agents
tags: [mcp, ai-coding-agents, context, rag, patterns]
category: mcp-ecosystem
---

# MCP context patterns for coding agents: dump, retrieve, or answer

**Short version:** when you wire project knowledge into a coding agent over MCP, you're
choosing one of three patterns: dump everything into the window, return a set of candidate
chunks to rank, or serve the single canonical doc that answers the query. They trade off cost,
accuracy, and how much the agent has to do. For doc-heavy repos and multi-session work, the
answer pattern wins on tokens (about 60% fewer per lookup) and on getting the *current* doc;
the others have their place. Here's how to pick.

## What is MCP doing here, briefly?

MCP (Model Context Protocol) is how an agent calls out to a tool for context: the agent sends
a request, your MCP server returns content the agent folds into its reasoning. The protocol
is plumbing. The interesting decision is *what your server returns* for a knowledge query.
Three patterns cover almost everything.

## Pattern 1: dump the repo

The server returns a large slab of the codebase or docs (think `repomix`, files-to-prompt).

- **When it fits:** small repos, one-off tasks, or when the agent genuinely needs broad
  context it can't predict.
- **What it costs:** you pay for the whole slab on every call to use a fraction of it. It
  scales the worst, and a fat window can *lower* answer quality by burying the relevant part.
- **Verdict:** fine for small or exploratory work, expensive as a default.

## Pattern 2: retrieve candidate chunks (RAG)

The server embeds the query, searches a vector store, and returns the top-k most similar
chunks for the agent to sift.

- **When it fits:** large, heterogeneous corpora where no single doc is "the answer" and you
  want recall across many sources.
- **What it costs:** you build and maintain the pipeline (chunking, embeddings, store,
  re-ranker), and you still hand the agent a pile to rank. Crucially, similarity ranking has
  no notion of *current*, so a stale chunk ranks next to a fresh one (more on that in
  [why agents pick stale docs](./why-agents-pick-stale-docs.md)).
- **Verdict:** the right tool for broad retrieval; a blunt one for "which doc is canonical."

## Pattern 3: serve one canonical answer

The server returns the single current doc that answers the query, as a `path:line` pointer
with a freshness marker, at the section level, not a pile.

- **When it fits:** doc-heavy repos with overlapping `.md`, multi-agent or multi-session
  work, and teams that need one source of truth.
- **What it costs:** least per lookup (about 60% fewer tokens than reading candidates), and
  the agent does no ranking. The trade is that it's scoped to *your authored docs*, not
  arbitrary recall across everything.
- **Verdict:** the efficient default for project knowledge. This is the pattern trovex
  implements, including a shared write path so agents save what they learn back to the same
  store.

## How do I choose?

A rough rule:

- Tiny repo, one task → **dump** is fine.
- Broad, mixed corpus, recall matters → **retrieve** (RAG).
- Doc-heavy repo, you want the *current* answer cheaply across a fleet → **answer**.

They also compose: a RAG layer for broad recall plus a canonical-answer layer for your core
docs is a reasonable setup. The mistake is using dump-everything or raw RAG as the default
for "which of my docs is the source of truth," then paying for it on every session.

## Try the answer pattern

trovex is in private beta. [Request access at trovex.dev](https://trovex.dev) and we'll get
you set up: point it at a repo, wire it into your agent over MCP, and watch the savings on
your own docs. See the [quickstart](../../docs/quickstart.md) for wiring and the
[FAQ](../../docs/faq.md) for where it fits. If you're standardizing how a team feeds context
to agents, that's the kind of thing we help with. Happy to talk.
