# Untitled task compute-

## Team : trovex-backend (tsukumo)
## Branch : fix/compute-status-loop-commit-test (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

ROOT_CAUSE: test coverage gap — test_concurrent_write_stays_fast_during_compute_status's synthetic docs never triggered a status UPDATE in compute_status's Pass 1 loop, so lines 148-149 (the periodic in-loop `db.commit()` every REINDEX_COMMIT_BATCH rows) were never exercised. The test's fast write_elapsed was explained entirely by the one-time commit at status.py:91 (post collision-resolution), not by Pass 1's own batching.

FIX: every 3rd synthetic doc's filename now matches settings.plan_path_patterns ("DRAFT"), so Pass 1 performs a real status UPDATE on ~1/3 of the 30 rows, spread across REINDEX_COMMIT_BATCH=3 boundaries — the periodic commit path now actually runs.

VERIFY: with the periodic in-loop commit disabled (temporarily, `if False and ...`), write_elapsed regressed to 2.54s (blocked) vs the <1.0s bound — confirms the test now genuinely pins Pass 1's own batching, not just the earlier one-time commit. Restored, full suite green (464 passed), ruff clean.

## review-backend verdict: SHIP
Test-only change (tests/test_reindex_single_flight.py), zero production code touched. No §1-8 surface implicated — no new recall path, no schema change, no MCP tool surface, no new external I/O. Verified negative-control (temporarily disabling the code under test) fails as expected, confirming the assertion is load-bearing rather than tautological.

## 3. Files changed

```
tests/test_reindex_single_flight.py | 7 ++++++-
 1 file changed, 6 insertions(+), 1 deletion(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `compute-status-loop-commit-test`._
