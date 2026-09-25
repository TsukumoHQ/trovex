# [trovex/index] reindex must not hold the sqlite write lock for minutes: incremental reindex of changed docs, serialized runs, busy_timeout for writers

## Team : trovex-backend (tsukumo)
## Branch : fix/reindex-incremental-serialized (from dev)
## Relay task : 67ebd68c-1edb-4a03-87b5-f9387ad24c5c
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. incremental run over an unchanged corpus re-embeds 0 docs and finishes under 2 s on the current store; pinned test with a fixture store
- [ ] 2. a doc whose content hash changed is re-embedded, unchanged siblings are not; pinned test
- [ ] 3. two concurrent /api/reindex requests yield one run (second returns the first's run id); pinned test
- [ ] 4. a trovex_write issued while a reindex runs succeeds within busy_timeout (no 'database is locked'); pinned concurrent test
- [ ] 5. index_runs rows carry docs_changed, docs_total, wall_ms
- [ ] 6. pytest green; PR body carries the review-trovex verdict; submitted through the gate

## 2. Root cause & decisions

> ⚠️ Root cause / arbitration not recorded by the doer yet. The gate requires it before merge — this gap is visible on purpose.

## 3. Files changed

```
src/trovex/db.py                    | 29 +++++++++++++++++++++-
 src/trovex/indexer.py               | 48 +++++++++++++++++++++++++++++-------
 src/trovex/server.py                | 25 +++++++++++++++----
 src/trovex/state.py                 | 12 +++++++--
 tests/test_incremental_reindex.py   | 49 +++++++++++++++++++++++++++++++++++++
 tests/test_reindex_single_flight.py | 28 +++++++++++++++++++--
 6 files changed, 172 insertions(+), 19 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `67ebd68c-1edb-4a03-87b5-f9387ad24c5c`._
