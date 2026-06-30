---
name: trovex
description: Token-efficient routing for a repo's Markdown docs. Use BEFORE reading or grepping any .md file to find the one canonical doc for a question — and to read it at the section level instead of whole. Trovex serves the single current doc per query (with a canonical/stale/duplicate freshness marker) for ~60% fewer tokens than reading the top candidates. Triggers: looking up project docs/specs/runbooks/records, "where is X documented", "how do we deploy/roll back/configure X", any question answerable from the repo's .md, or writing a durable record/decision/post-mortem back into the docs.
---

# trovex

trovex is a local MCP server that indexes your repo's Markdown and serves the
**one canonical doc per query** — `path:line` + a freshness marker — instead of
making an agent read or grep many files. Local-first: SQLite + ONNX, no cloud,
no API key by default.

## When to use it

- BEFORE reading or grepping a `.md` file. Query trovex first; it routes you to
  the single doc that answers the question, often the exact section.
- Answering "where is X documented / how do we do X" from the repo's docs.
- Writing a durable record (incident, decision, post-mortem, current state) back
  into the doc store so the next session recalls it instead of re-deriving it.

## How to use it

Call the MCP tools (server at `http://localhost:8765/mcp` after `trovex serve`):

- `trovex(q)` — the router. Returns the best doc for `q` as `path:line` with a
  freshness marker. **Do this before opening any `.md`.** Set `summary=True` only
  if the minimal result is ambiguous (costs ~150 extra tokens).
- `trovex_search(q, limit, tags, kind)` — ranked candidates; filter by
  `tags=["owner/...","domain/..."]` or `kind` (`record` | `reference`).
- `trovex_read(doc_id, section=...)` — read the whole doc or just one heading's
  section (token-minimal; prefer `section`).
- `trovex_write(content, kind, tags, doc_id)` — store/update a doc. `kind="record"`
  for event-anchored notes (never goes stale by age). Pass an existing `doc_id`
  to update in place (no duplicate). One canonical doc per topic.
- `trovex_tag(doc_id, tags)` / `trovex_delete(doc_id)` — manage tags / remove.

## Notes

- Read the routed doc at the section level — don't slurp the whole file when
  `trovex_read(section=...)` gives you the relevant heading.
- Freshness marker: `canonical` = the current answer; `stale` = old, verify;
  `duplicate` = a near-copy of a canonical doc — prefer the canonical.
- If trovex isn't running, start it with `trovex serve`, or index a repo first
  with `trovex index /path/to/repo`.
