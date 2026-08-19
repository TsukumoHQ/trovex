# review-followups-knn-dup

## Team : trovex-backend (tsukumo)
## Branch : chore/review-followups-knn-dup (from main)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

## review-trovex verdict: SHIP

ROOT_CAUSE: Two non-blocking review follow-ups on already-merged work.
(1) The P0 outage regression test (4d832f33) did NOT isolate the search.py
widen-retry clamp: boot.py's try/except swallows the OperationalError and the
plain limit=5 search never fires the widen-retry, so removing SQLITE_VEC_MAX_K
kept the test green — the "fails outright" claim was false (reviewer verified by
mutation). (2) The trovex MCP tool docstring (mcp_app.py) advertised a
'⚠ duplicate' marker that the default pool can no longer emit after c41904dd
excluded status=duplicate.

DECISION:
(1) Add a test that isolates the clamp by asserting RECALL, not just no-throw:
60 near-padding docs (distance 0) fill the k=50 first pass; ONE owner-scoped
record sits just behind them (inside the clamped 4096 pool, past the first pass);
4050 far docs push the corpus past 4096. Only the clamped widen-retry recalls the
owner record, so a dropped clamp makes the scoped search raise and boot fail-open
to empty. Kept the original test (still covers ceiling-crossing + boot 200
fail-open) alongside the new isolating one.
(2) Remove the '⚠ duplicate' entry from the tool docstring legend. STATUS_MARKER
keeps the mapping for any include_duplicates path.

VERIFICATION — MUTATION-PROVEN non-vacuity: with BOTH search.py clamps removed,
the new test FAILS ("k value in knn query too large, provided 4111, limit 4096")
while the old test still PASSES — demonstrating the new test closes the exact gap
the reviewer flagged. Owner record made fresh (mtime=now) so it clears the boot
freshness floor (0.62), matching real /api/boot behaviour. Full gate green:
ruff check src tests, pytest -q -> 348 passed, brand guard clean (python + web).

REJECTED ALTERNATIVE: replacing the original outage test. Kept it — it still
covers the boot fail-open / HTTP 200 path and ceiling-crossing; the new test adds
the missing clamp-isolation rather than trading one for the other.

review-trovex: ✅ ship — 2 files (mcp_app.py docstring + test_active_memory.py),
test + doc only, no src/schema/wire behaviour change, gate green (ruff + pytest
348 passed), brand clean, no secret/host/number leak.

## 3. Files changed

```
src/trovex/mcp_app.py       |  4 +--
 tests/test_active_memory.py | 86 ++++++++++++++++++++++++++++++++++++++++++++-
 2 files changed, 87 insertions(+), 3 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `review-followups-knn-dup`._
