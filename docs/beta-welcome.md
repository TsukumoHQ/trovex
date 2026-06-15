# Welcome to the trovex beta

You're in. Thanks for testing trovex while it's still private. This page is the fast path
from "I have access" to "I can see what it saves me," plus how to tell us what's working and
what isn't.

*(This is the in-repo guide. The emails you get from us are the nudges; this is the thing to
keep open while you set up.)*

## What trovex does, in one paragraph

Your coding agent rereads your repo's markdown every session to work out which doc is
current, then answers from a guess. trovex indexes that markdown and serves your agent the
one current doc that answers a query (a `path:line` pointer with a freshness marker),
instead of the pile. Same answers, about 60% fewer tokens per lookup. It runs locally:
vectors in SQLite, embeddings via ONNX, no cloud or keys.

## The fastest path to the aha (about 2 minutes)

The "aha" is seeing a real savings number on *your* repo. Get there first, explore later.

1. **Index a real, doc-heavy repo.** Not a toy one. The savings show up where you actually
   have overlapping `.md`.
   ```bash
   uv sync
   uv run trovex index /path/to/your/repo
   ```
2. **Ask it something your docs answer**, and watch the tokens it saved versus reading the
   top candidates:
   ```bash
   uv run trovex search "how do we deploy?"
   ```
3. **Wire it into your agent and open the dashboard:**
   ```bash
   uv run trovex serve   # MCP at /mcp, savings dashboard at /savings
   ```
   Work a normal session, then open `http://localhost:8765/savings`. The would-have-read
   versus actual number is the point.

Full setup detail is in the [quickstart](./quickstart.md); objection-style questions are in
the [FAQ](./faq.md).

## If the savings number is small

That's a real result, not a failure. trovex earns its place on doc-heavy repos with real
agent traffic. If your number stays low, tell us, that's useful signal about where trovex
does and doesn't fit, and exactly the kind of thing the beta is for.

## How to give feedback (please do)

The whole reason for a private beta is your honest reaction, including the unflattering
parts. Most useful to us, in rough order:

- **Where setup snagged.** Anything confusing, broken, or slower than "about 2 minutes."
- **Where the canonical answer was wrong.** It returned a stale or wrong doc, or missed the
  right one.
- **Your real savings number** (a screenshot of the dashboard is perfect), and whether it
  felt worth it.
- **What you wish it did.** The roadmap is short and you have a direct say in it.

Send it however is easiest for you, reply to any of our beta emails, or open an issue in the
repo. Short and honest beats polished.

## What happens next

We read everything and fix the snags fast while the group is small. As the tool and the
proof firm up, trovex opens more widely. Early testers shaped it; that's the point.

If you're running agents across a team and want hands-on help doing it well at scale, say so,
that's the kind of thing we do.
