---
title: "Local-first vs cloud RAG for serving your coding agents context"
description: "A cloud RAG service for agent context adds an API key, a per-call bill, network latency, and your code leaving the machine. Here's when local-first wins, and the honest case for when it doesn't."
slug: local-first-vs-cloud-rag-for-agent-context
date: 2026-06-16
author: trovex
canonical_url: https://trovex.dev/blog/local-first-vs-cloud-rag-for-agent-context
tags: [ai-coding-agents, local-first, rag, mcp, developer-tools]
category: local-first-infra
---

# Local-first vs cloud RAG for serving your coding agents context

**Short version:** to give a coding agent the right doc for a query, you can run a cloud
service (managed vector DB plus an embeddings API) or keep the whole thing on your machine
(vectors in SQLite, embeddings via a local ONNX model). For this specific job, serving an
agent's doc lookups, local-first usually wins: no API key, no per-call bill, no round-trip
latency, and your code never leaves the box. Cloud earns its place when the corpus is huge,
shared across an org, or needs centralized governance. Most single-dev and small-team setups
aren't that. Here's the breakdown.

## What "cloud RAG for agent context" actually involves

When a context tool is cloud-based, a single doc lookup usually means: your agent's query
goes to a hosted service, which calls an embeddings API to vectorize it, queries a managed
vector database, and returns matches. Two external dependencies (the embeddings API and the
vector store), two network hops, and a per-call cost on at least one of them.

That's fine for some workloads. It's a lot of moving parts for "which of my markdown files
answers this question."

## Cost: per-call versus paid-once

Cloud RAG bills you per embedding and often per query. It's cheap per call and easy to
ignore, until you remember the access pattern: every agent, every session, re-embedding and
re-querying. The same compounding that makes doc rereading expensive (see
[the token cost of agents rereading docs](./the-token-cost-of-agents-rereading-docs.md))
applies to the embedding and query bill on top of the token bill.

Local-first has a different shape. Indexing runs once on your machine and again only when
docs change. Queries hit a local model and a local database. The marginal cost of a lookup
is CPU you already paid for. There's no meter running.

## Latency: a network hop you don't need

A cloud lookup pays for the round trip every time: out to the service, embeddings API,
vector query, back. Tens to hundreds of milliseconds, plus whatever the API is doing under
load.

A local lookup is an in-process query against SQLite with a local embedding. It's fast
enough that the agent isn't waiting on it, and it works on a plane with no wifi. For a step
that happens many times per session, that difference adds up.

## Privacy: where your code and docs go

This is the one that's hard to walk back. Cloud RAG means your repo's docs (often the most
context-rich, sometimes sensitive part of your codebase) get embedded and stored by a third
party. For a lot of teams that's a non-starter or a compliance conversation.

Local-first means indexing and embeddings run on your machine, vectors live in a local
SQLite file, and nothing is sent anywhere. No API key to leak, no data-processing agreement
to sign, no question about retention. That's how trovex runs by default: SQLite plus ONNX
embeddings, no cloud and no keys.

## Setup: one process versus an account and a key

Cloud RAG needs an account, an API key in your environment, and usually some service
configuration. Local-first is `index` then `serve`: one local process, no signup, working in
about a minute. For a tool that has to justify itself against "just let the agent read
files", a one-minute no-account setup matters.

## When cloud RAG is the right call (the honest part)

Local-first isn't universally better; it's better for this job at this scale. Reach for a
cloud setup when:

- **The corpus is too big for one machine** to index and hold comfortably, or it spans many
  repos you want searched together.
- **An org needs one shared, governed index** with access controls, audit, and central
  updates, rather than each developer running their own.
- **You want zero local footprint** on constrained or ephemeral environments and are fine
  paying for it.

If that's you, a managed service is a reasonable trade. The point isn't "cloud bad." It's
that the common case (a developer or small team serving agents context from their own repos)
gets cost, latency, and privacy wins from keeping it local, and gives up little.

## How trovex does it

trovex is local-first by default: it indexes your repo's markdown into SQLite, embeds with a
local ONNX model, and serves your agent the one canonical doc per query over MCP, with no
cloud and no API keys. You can still self-host it behind your own proxy if you want a shared
instance; see `docker/` in the repo. The default just doesn't make you opt into the cloud to
answer "which doc is current."

## Request beta access

trovex is in private beta. [Request access at trovex.dev](https://trovex.dev) and we'll get
you set up locally, so nothing leaves your machine. It's licensed AGPL-3.0 (core) and MIT
(CLI), and opens up more widely after the beta.

If you're running agents across a team and weighing local versus a shared index, that's the
kind of trade-off we help teams think through. Happy to talk.
