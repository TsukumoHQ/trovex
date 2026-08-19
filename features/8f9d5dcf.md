# 8f9d5dcf

## Team : trovex-backend (tsukumo)
## Branch : feat/terse-citations (from main)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

# feat/terse-citations — trovex_search returns citations, not dumps

Task 8f9d5dcf — trovex steal #4 (Context7 UX + FastContext "citations not
dumps"). Reassigned from frontend (MCP output shape = backend lane). Pairs with
the access ladder (#3).

ROOT_CAUSE: trovex_search concatenated k FULL sections (_fmt_passage per hit) —
a dump. For a k=5 search that's five whole sections in one response, most of
which the agent never needed; it contradicts the token-savings moat and the
ladder's "start low, escalate on need" model.

## Decision (additive, back-compat — still a text string)

- `_fmt_citation(h)`: one terse anchored hit — the citation (heading breadcrumb +
  trovex:<doc-id>) over a short ~28-word snippet. The breadcrumb + doc-id is the
  stable anchor; the exact span is trovex_read(doc_id, section=<heading>).
- `trovex_search` now returns k citations + ONE 'climb the ladder' affordance
  (_SEARCH_LADDER_HINT), not k full sections. The agent triages the pointer list,
  then reads the one span it wants via trovex_read (query→passage/full, or
  doc_id+section). Fewer tokens, and it composes with the card/passage/full ladder.
- trovex_read is unchanged — it already carries the ladder (card/passage/full);
  the card tier is itself a citation. The doc-router `trovex(q)` already returns a
  terse path list. So the only dump was trovex_search.

Line-anchor: markdown is heading-addressed, so the citation anchors on the
breadcrumb + doc-id (stable across edits) rather than a fragile line number; the
exact cited span is fetched by trovex_read(doc_id, section=<heading>).

## Gate

`uv run ruff check src tests` clean; `uv run pytest -q` → 329 passed (+ new
test_terse_citations: anchored-citation shape, snippet trimmed not dumped +
strictly smaller than the section, single ladder-hint for many hits, clean
no-results on an empty store). Existing trovex_search tests (error paths) still
pass. brand + security guards green. Left pre-existing ruff-format debt
(mcp_app.py:867) untouched (cto reflow).

Back-compat: wire contract (string return) unchanged; trovex_search signature
unchanged. Output is terser by design (the task's intent).

review-trovex: ✅ ship — 2 files, ~149 LoC — gate green (ruff+pytest), additive
output-shape change (no wire/signature change), pairs with the ladder, no
leak/secret/number issue.

## 3. Files changed

```
src/trovex/mcp_app.py         |  32 +++++++++--
 tests/test_terse_citations.py | 120 ++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 149 insertions(+), 3 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `8f9d5dcf`._
