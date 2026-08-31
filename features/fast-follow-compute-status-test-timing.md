# Untitled task fast-fol

## Team : trovex-backend (tsukumo)
## Branch : fix/compute-status-test-timing (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

ROOT_CAUSE: test_concurrent_write_stays_fast_during_compute_status (085f1d69,
tests/test_reindex_single_flight.py) constructed writer_store = SqliteStore(...)
*after* thread.start(), inside the timing window it measures. SqliteStore's
constructor calls open_db(), whose migration chain issues its own write
statements against the same db file — so on pre-fix code that construction
itself blocked on compute_status's held write lock and absorbed the wait.
Only the subsequent store.put() call was timed, which then ran against an
already-idle lock, so the test passed on both pre-fix and fixed code —
a false-negative regression guard (review-085f1d69 non-blocking finding).

DECISION: move writer_store construction before thread.start(), so only
store.put() contends with the lock the test exists to probe. Verified by
swapping in the pre-batched-commit status.py (d3b0cd6): the test now fails
(write waited 3.04s vs the 1.0s bound), confirming it pins the bug for real.
No alternative considered — this is the minimal fix matching the reviewer's
suggested repair; nothing else in the test needed to change.

## review-backend verdict: SHIP

Diff is 2 files, 11/-5 lines: test-fixture ordering fix (writer_store built
before the slow pass starts, not inside the timing window it measures) and
a comment-scope wording fix. No recall/retrieval, write-integrity, schema,
auth, or privacy-default surface touched — nothing in §1-8 of the checklist
applies. §9 (test discipline): the test stays hermetic (BagEmbedder, no
network); verified against pre-fix status.py (d3b0cd6) that it now actually
fails (3.04s wait vs 1.0s bound), confirming it pins the regression it
claims to. Full suite 464 passed, ruff clean.

## 3. Files changed

```
src/trovex/status.py                | 9 +++++----
 tests/test_reindex_single_flight.py | 7 ++++++-
 2 files changed, 11 insertions(+), 5 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `fast-follow-compute-status-test-timing`._
