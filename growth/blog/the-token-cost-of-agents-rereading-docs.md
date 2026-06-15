---
title: "The token cost of coding agents rereading your docs"
description: "Coding agents reread your .md files every session to guess which one is canonical. Here's the math on what that costs, and how serving one current doc cuts doc-lookup tokens by about 60%."
slug: the-token-cost-of-agents-rereading-docs
date: 2026-06-15
author: trovex
canonical_url: https://trovex.dev/blog/the-token-cost-of-agents-rereading-docs
tags: [ai-coding-agents, tokens, context, mcp, developer-tools]
category: token-economics
---

# The token cost of coding agents rereading your docs

**Short version:** every session, your coding agent rereads several `.md` files
to work out which one is the current source of truth, then answers from a guess.
You pay for those reads on every session, every agent, every teammate. Serve the
agent the one canonical doc instead of the pile, and a typical doc lookup drops
from roughly 720 tokens to roughly 280. That's about 60% fewer tokens for the
same answer. This post shows where that number comes from and how to reproduce
it on your own repo.

## Why does my coding agent reread the same docs every session?

Because it has no way to know which doc is current.

A real repo accumulates overlapping markdown: a `deploy/runbook.md`, an older
`wiki/old-deploy.md`, an `ops/postmortem-0420.md` that mentions rollback in
passing. When your agent needs to answer "how do we roll back a deploy?", it
does what you'd do without an index. It lists the candidates, opens the likely
ones, and reads enough of each to decide which to trust.

It does this from a cold start every session, because the context window doesn't
persist. So the same lookup gets paid for again tomorrow, and again by the next
agent, and again by your teammate's agent on the same repo.

`CLAUDE.md`, `AGENTS.md`, and `.cursorrules` help a little. They pin a single
static blob into context. But one blob goes stale, doesn't scale past a handful
of topics, and can't route a specific question to the specific doc and section
that answers it. It's a sticky note, not an index.

## What does the rereading actually cost?

Let's price one lookup. The numbers below are illustrative (your repo and agent
differ), but the shape holds, and you can measure your own (see the last
section).

Take the deploy-rollback question against the three candidate files above.

**Without an index**, the agent reads enough of each candidate to judge which is
canonical:

| File | Read to decide | ~Tokens |
|------|----------------|---------|
| `deploy/runbook.md` (current) | relevant section | ~280 |
| `wiki/old-deploy.md` (stale duplicate) | enough to reject | ~240 |
| `ops/postmortem-0420.md` (stale) | enough to reject | ~200 |
| **Total** | | **~720** |

The agent spent ~440 tokens reading two files it ended up discarding. That's the
tax. The cost isn't the answer, it's the *guessing*.

**With one canonical answer**, the agent asks once and gets back a single
pointer: `deploy/runbook.md:42`, marked `canonical`, updated 3 days ago, plus
just the section that answers.

| Served | ~Tokens |
|--------|---------|
| `deploy/runbook.md` § "Rolling back a deploy" | ~280 |
| **Total** | **~280** |

```
720 → 280  ≈  61% fewer tokens on this lookup
```

The stale and duplicate files never enter the context window, so you also stop
paying the quieter cost: a polluted window that nudges the model toward the
wrong, older answer.

## Where does the ~60% number come from?

It's the average of that same arithmetic across many lookups, not a single
cherry-picked one.

Per-lookup savings vary. A question with one obvious doc saves little. A question
that touches a thicket of overlapping, half-stale files saves a lot. Across a
real session, with many lookups of mixed difficulty, the reduction on doc reads
lands around 60% for the repos we've measured.

Two honest caveats:

- **It's the doc-lookup portion of the bill, not your whole bill.** Your agent
  also reads code, runs tools, and reasons. trovex cuts the markdown-rereading
  slice. On a doc-heavy repo with a lot of agent traffic, that slice is large;
  on a tiny repo, it's small.
- **The real number is yours, not ours.** ~60% is representative, not a promise.
  The point of the savings dashboard (below) is that you don't have to take the
  figure on faith. It shows would-have-read versus actual for your own repo.

## How does trovex fix it?

You point it at your repo, and it does three things that map directly to the
costs above.

**1. One canonical answer instead of a pile.** trovex indexes your markdown and
exposes a single MCP tool. Your agent asks a question in plain language; trovex
returns the one current doc that answers it as a `path:line` pointer with a
freshness marker (`canonical`, `stale`, or `duplicate`), not a list of
candidates to rank. The guessing step disappears.

**2. Section-level reads.** When the answer is two paragraphs, trovex hands back
two paragraphs, not the 400-line file they live in. A short answer costs
short-answer tokens.

**3. A shared write path.** Agents also save what they learn (an incident, a
decision, "the rollback steps that actually worked") back through one shared
point. The next agent, and your teammate, read it instead of re-deriving it.
That's a single source of truth by construction, with no copies left to drift.

It runs locally: vectors in SQLite, embeddings via ONNX. No cloud, no API keys,
your code never leaves the machine.

## How is this different from RAG or dumping the repo?

- **Dumping the repo** (`repomix`, files-to-prompt) floods the window with
  everything. That's the opposite of token-efficient. You pay for the whole
  corpus to use a fraction of it.
- **Plain RAG / context servers** return a handful of candidate chunks ranked by
  similarity, and leave the agent to decide which to trust. That's still a pile,
  just a smaller one, and it carries no freshness signal. A stale chunk and a
  current one look equally relevant to a similarity score.
- **trovex** returns the *one* current doc with an explicit freshness marker, and
  closes the loop by letting agents write canonical notes back. The unit of
  output is an answer, not a candidate set.

## How do I measure this on my own repo?

Don't trust the ~60%. Reproduce it.

```bash
uv sync
uv run trovex index /path/to/your/repo
uv run trovex serve   # MCP at /mcp, dashboard at /
```

Point your agent (Claude Code, Cursor, Windsurf, Zed, any MCP client) at the
trovex MCP endpoint, then work a normal session. Open the Savings tab. It shows
would-have-read versus actual tokens on doc lookups: your real reduction, on
your real docs.

If the number is small, your repo probably doesn't have a doc-rereading problem,
and you should keep your setup. If it's large, you were paying that tax on every
session.

## FAQ

**My context window is huge, why does this matter?**
A bigger window doesn't make the reread cheaper; it makes it bigger. The cost
compounds across every session, agent, and teammate. And a big window isn't a
*current* one. It'll happily hold three conflicting docs and answer from the
wrong one. trovex serves the right doc cheaply; window size doesn't fix
correctness.

**I already use CLAUDE.md / AGENTS.md.**
Keep it for high-level rules. It's one static file, though. It goes stale,
doesn't scale past a few topics, and can't route a question to the right doc or
section. trovex keeps many docs canonical and serves the one that answers the
specific question.

**Is it one more service to babysit?**
One local process. `trovex serve`, point your agent at it, done in about a
minute. No cloud, no keys. It shows you the tokens it saves, so it justifies its
own existence.

**Does my code leave my machine?**
No. Indexing and embeddings run locally in SQLite and ONNX. Nothing is sent
anywhere.

## Try it

```bash
uv run trovex index /path/to/your/repo
```

It's open source: core under AGPL-3.0, CLI under MIT. Repo and docs:
[github.com/Synergix-lab/trovex](https://github.com/Synergix-lab/trovex) ·
[trovex.dev](https://trovex.dev).

If you're running agents across a team and the doc-rereading tax is a daily line
item, that's the kind of thing we help teams fix. Happy to talk.
