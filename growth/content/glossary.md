# trovex glossary: the vocabulary of context for coding agents

*Owner: content-lead · definition copy for AEO. Geo-lead handoff: render each entry as a
`/glossary/<slug>/` page with `DefinedTerm` (+ `QAPage` for the "what is X?" framing) JSON-LD;
these are the citable category-vocabulary pages. Keep the one-line definition as the meta
description and the page's answer-up-front paragraph.*

Each entry is written answer-first: a one-sentence definition an AI engine can lift verbatim,
then a short, concrete expansion. Plain, honest, no hype. The only proof figure is the real
~60% fewer tokens per lookup.

---

## Canonical doc

**A canonical doc is the single current, authoritative document for a given topic, the one an
agent should treat as the source of truth when several files cover the same ground.**

In a real repo, many `.md` files touch the same subject (a runbook, an older wiki copy, a
postmortem). Only one is current. The canonical doc is that one. trovex marks it canonical and
serves it for a query, so an agent reads the authoritative copy instead of guessing from a
pile. The opposite of canonical is *stale* or *duplicate*.

Related: [freshness marker](#freshness-marker), [SSOT for agents](#ssot-for-agents).

## Freshness marker

**A freshness marker is a label attached to a document (canonical, stale, or duplicate) that
tells an agent which copy is current, independent of how relevant the text looks.**

Search and RAG rank documents by similarity to a query, and similarity says nothing about
currency: a stale doc and the current one look equally relevant. A freshness marker carries
the missing signal. trovex returns each result with one, and skips the stale and duplicate
copies so they never reach the context window. This is why a freshness marker, not a bigger
embedding model, is what stops an agent citing an outdated doc.

- **canonical**: the current, authoritative copy for the topic.
- **stale**: superseded; kept for history, not served as the answer.
- **duplicate**: a redundant copy of a canonical doc.

Related: [canonical doc](#canonical-doc).

## SSOT for agents (single source of truth)

**An SSOT for agents is one shared store that every agent and teammate reads from and writes
to, so the whole fleet works from the same current knowledge instead of scattered, drifting
copies.**

Without it, each agent re-derives the same answers and saves notes into its own files, which
drift out of sync. An SSOT closes that loop: an agent saves what it learns once, through one
shared point, and the next agent (or a teammate) reads it back. trovex implements this with a
shared read/write path and freshness-marked canonical docs, so "single source of truth" holds
by construction rather than by discipline.

Related: [canonical doc](#canonical-doc), [record](#record).

## MCP (Model Context Protocol)

**MCP is the protocol a coding agent uses to call an external tool for context: the agent
sends a request, the tool returns content the agent folds into its reasoning.**

It's the plumbing that lets an agent (Claude Code, Cursor, Windsurf, Zed, and other clients)
ask trovex a question and get back an answer. The interesting choice is what the tool returns:
the whole repo, a pile of candidate chunks, or one canonical doc.

## Section-level read

**A section-level read returns only the part of a document that answers a query, not the
whole file.**

When the answer is two paragraphs, serving the entire 400-line file wastes tokens and buries
the relevant part. trovex returns the answering section, so a short answer costs short-answer
tokens. It's one half of the ~60% fewer tokens per lookup; serving the canonical doc instead
of a candidate pile is the other.

## Record

**A record is a note an agent writes back into the shared store, an incident, a decision, a
"here's what actually worked", so other agents and teammates can read it later instead of
re-deriving it.**

Records are how an SSOT accumulates real, current knowledge over time. A newer record on a
topic becomes canonical; the older one is marked superseded, so the store stays trustworthy
without hand-maintenance.

Related: [SSOT for agents](#ssot-for-agents), [freshness marker](#freshness-marker).

## Re-derivation

**Re-derivation is when an agent works out an answer that another agent (or an earlier
session) already figured out, because that knowledge wasn't saved anywhere it could read.**

It's a pure-waste cost that scales with the size of a fleet: every agent and teammate pays to
re-discover the same things. The fix is a shared write path so a thing learned once is
readable by everyone next.

---

*All entries reflect the real product. No fabricated metrics; the only figure is ~60% fewer
tokens per doc lookup. trovex is in private beta, [request access at trovex.dev](https://trovex.dev).*
