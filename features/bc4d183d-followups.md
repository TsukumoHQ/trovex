# bc4d183d-followups

## Team : trovex-backend (tsukumo)
## Branch : feat/collapse-ephemeral-owners (from main)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

## review-trovex verdict: SHIP

Two bc4d183d review-r1 follow-ups (the 4th sub-item cto ruled on + the correctness
warning), one branch.

ROOT_CAUSE #1 (CORRECTNESS, live-store impact — the warning): compute_status opens
with `UPDATE docs SET status='canonical'` over ALL rows. After e0fd2625 added the
partial unique index (one live canonical per topic) and the migration created
superseded docs, that bulk reset flips a superseded doc back to canonical while its
live canonical still exists → sqlite IntegrityError, crashing EVERY reindex on a
store that has any superseded doc — and the deployed store has them (migration
de-dupe). Reproduced (IntegrityError: UNIQUE docs.workspace_id, docs.canonical_topic).
It also erased 'superseded' before the reindex-time sweep could tombstone the fork,
so that pass was a silent no-op (also flagged).
FIX: compute_status treats 'superseded' as SSOT-managed — the reset AND the
plan/stale pass-1 both skip status='superseded'. Superseded docs survive the
reindex (no crash) and remain for sweep_bloat to tombstone. Fixed the misleading
server.py/store.py comments (reindex-time sweep now genuinely works; owned
age-staleness is a standalone-path safety net, since compute_status ages owned docs
too — its age rule ignores file existence).

ROOT_CAUSE #2 (the deferred 4th sub-item, per cto's rule): a respawned/numbered
agent leaves owner records tagged owner/<name>-<N>, piling forks.
FIX: sweep_bloat._collapse_ephemeral_owners_locked — per group <name>: if an
unsuffixed owner/<name> exists → tombstone every owner/<name>-<N>; else keep the
HIGHEST N, tombstone the lower. Reversible (doc_tombstones snapshot + cascade,
recoverable, consistent with the superseded pass; dropping the row also shrinks the
KNN corpus). A doc that also wears a keeper owner tag is never tombstoned.
Idempotent.

VERIFICATION: tests — (1) after a force-supersede, compute_status no longer raises
and leaves the doc superseded, then the sweep tombstones it; (2) an unsuffixed
owner keeps its canonical and drops both numbered forks, a no-unsuffixed group
keeps the highest N and drops the lower, an unrelated owner is untouched, forks are
recoverable via list_tombstones, and a second sweep collapses nothing. Full gate
green: ruff check src tests, pytest -q -> 357 passed, brand guard clean. Rebased
onto origin/main after bc4d183d (9cf0e17) merged.

review-trovex: ✅ ship — 4 files (status/store/server + tests), gate green
(ruff + pytest 357 passed), brand clean, no schema change, fixes a live reindex
crash, no secret/host/number leak.

## 3. Files changed

```
src/trovex/server.py        |  9 ++---
 src/trovex/status.py        | 13 +++++--
 src/trovex/store.py         | 85 +++++++++++++++++++++++++++++++++++++++++----
 tests/test_active_memory.py | 61 +++++++++++++++++++++++++++++++-
 4 files changed, 153 insertions(+), 15 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `bc4d183d-followups`._
