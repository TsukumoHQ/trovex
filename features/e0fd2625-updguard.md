# e0fd2625-updguard

## Team : trovex-backend (tsukumo)
## Branch : fix/ssot-update-collision-guard (from main)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

## review-trovex verdict: SHIP

ROOT_CAUSE (e0fd2625 review r1 warning): SSOT was enforced on the CREATE path
(store.put else-branch → TopicCollisionError), but the UPDATE branch set
canonical_topic with no collision guard. Renaming a live canonical's title so its
slug lands on ANOTHER live canonical's topic trips the partial unique index with a
raw sqlite3.IntegrityError — uncaught by trovex_write's TopicCollisionError
handler, so the agent gets an opaque crash instead of an actionable block.

DECISION: mirror the CREATE guard on the UPDATE branch. When the existing doc is
status='canonical' and its new topic already has a DIFFERENT live canonical
(id != self): force=True atomically supersedes the prior canon
(status='superseded' + lifecycle='archived') in the same transaction; otherwise
raise TopicCollisionError so trovex_write returns the block-and-point pointer.
Guard only fires for a canonical driver (a non-canonical doc can't violate the
status='canonical' partial index), so a stale/superseded rename is unaffected.

VERIFICATION: new test — renaming a canonical's title onto another's topic raises
TopicCollisionError (asserting the TYPE, so it proves the raw IntegrityError is
translated), and force=True supersedes the prior and lets the rename land. Full
gate green: ruff check src tests, pytest -q -> 353 passed, brand guard clean.
Branched off origin/main AFTER e0fd2625 (fc2446df) merged.

review-trovex: ✅ ship — 2 files (store.py + test), gate green (ruff + pytest 353
passed), brand clean, no schema/wire change (guard only), no secret/host/number leak.

## 3. Files changed

```
src/trovex/store.py         | 22 +++++++++++++++++++++-
 tests/test_active_memory.py | 25 +++++++++++++++++++++++++
 2 files changed, 46 insertions(+), 1 deletion(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `e0fd2625-updguard`._
