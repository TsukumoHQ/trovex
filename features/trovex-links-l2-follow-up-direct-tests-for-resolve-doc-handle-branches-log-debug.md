# [trovex/links L2 follow-up] direct tests for resolve_doc_handle branches + log.debug in _link_hint

## Team : trovex-backend (tsukumo)
## Branch : trovex-backend/links-l2-6664c8c9 (from dev)
## Relay task : 6664c8c9-e5db-4541-a227-f0b148219e2a
## Trace : trace=80361ddda004dbc71bc910c0b1d7c2ae
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. test: resolve_doc_handle LIKE-prefix branch with a handle containing '_' matches only the literal prefix
- [ ] 2. test: resolve_doc_handle bare-path-unique branch resolves; ambiguous bare path does not
- [ ] 3. _link_hint logs at debug on exception (test with caplog)
- [ ] 4. uv run --extra dev python -m pytest -q green

## 2. Root cause & decisions

# 6664c8c9 — links L2 follow-up: direct tests + best-effort log

ROOT_CAUSE: The trovex/links L2 change (b9687dfb) shipped `resolve_doc_handle`
with a LIKE-prefix branch whose `_`/`%` escape (via `like_escape` + `ESCAPE '\'`)
and whose bare-path-unique branch were only covered indirectly through the MCP
surface, and `Searcher._link_hint` swallowed every inner exception with no trace
(`except Exception: return ""`). A silent swallow hides a real DB/link-count
regression, and the escape fix had no test pinning it, so a future edit could
drop the escape and only an agent-visible wildcard mismatch would reveal it.

DECISION:
- Add `tests/test_links_parse.py` with direct, hermetic (`open_db`, no embedder)
  tests for the two untested `resolve_doc_handle` branches:
  - LIKE-prefix with a handle containing `_` resolves to ONLY the literal-prefix
    row (two ext_ids `abc_one`/`abcZtwo` — without the escape, `abc_` is a
    wildcard matching both -> ambiguous None; the escape keeps it unique).
  - bare path: unique -> resolves; same path under two sources -> ambiguous None.
- `_link_hint` now `log.debug(..., exc_info=True)` on the swallowed exception
  (module logger `trovex.search`, matching the mcp_app L56 best-effort+log
  pattern) while STILL returning `""` so a hint failure never breaks formatting.
  Covered with `caplog`.

Scope held to the three reviewer notices; no behaviour change beyond the added
debug log. Full suite green (1039 passed); targeted verify_cmd green (8 passed).

REJECTED ALTERNATIVES:
- Re-raise / surface the `_link_hint` error: rejected — a count hint is cosmetic
  and must never break a search result's formatting (the original intent).
- Build docs via the full Indexer/Store for the resolve tests: rejected — direct
  `INSERT` into `docs` gives precise control of `ext_id`/`path`/`source_id` with
  no model download, keeping the test fast and deterministic.

## review-trovex verdict: SHIP
review-trovex: ✅ ship — 2 files, 103 LoC — gate green (ruff + pytest 1039 passed, targeted verify_cmd 8 passed), Active-Memory invariants held (_link_hint still returns "" byte-stable; best-effort debug log only; no scope/score/owner-tag/schema change), hermetic tests (open_db, no embedder), no leak/secret/brand/number.

## 3. Files changed

```
src/trovex/search.py      |  4 ++
 tests/test_links_parse.py | 99 +++++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 103 insertions(+)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `6664c8c9-e5db-4541-a227-f0b148219e2a`._
