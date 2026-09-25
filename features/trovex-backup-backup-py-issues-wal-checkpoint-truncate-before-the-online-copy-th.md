# [trovex/backup] backup.py issues wal_checkpoint(TRUNCATE) before the online copy — the exact call db.py documents as starving writes to the 30 s busy_timeout; use PASSIVE or no checkpoint

## Team : trovex-backend (tsukumo)
## Branch : fix/backup-passive-checkpoint (from dev)
## Relay task : 2081581c-cb7d-4ee5-b181-705724c6da8d
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. backup.py no longer issues wal_checkpoint(TRUNCATE); pinned source-guard test
- [ ] 2. pinned test: make_backup completes with a concurrent open read transaction on the store, in under 5 s, and the backup file opens and serves a KNN query
- [ ] 3. make test green; PR carries the review-trovex verdict; submitted through the gate against dev

## 2. Root cause & decisions

TASK: 2081581c — backup.py's wal_checkpoint(TRUNCATE) starves writers to the 30s busy_timeout

ROOT_CAUSE: backup.py's make_backup() ran `PRAGMA wal_checkpoint(TRUNCATE)` on a second connection before the sqlite3 backup-API online copy. TRUNCATE needs EXCLUSIVE access to the WAL and busy-waits (up to busy_timeout, 30s on this store) against any reader holding an older WAL frame — under the server's normal read traffic there is almost always one (the same class of stall already measured and documented in db.py's checkpoint_if_wal_large, prod 2026-08-31 task 7768dbe6: trovex_write/search stalled to exactly 30000ms). The backup path reintroduced that exact stall once a day, unconditionally.

DECISION: Replace TRUNCATE with PASSIVE. The sqlite3 backup API (src.backup(dst)) already copies a fully consistent snapshot including WAL content regardless of any pre-checkpoint — the checkpoint was only ever a size/speed optimization (a smaller WAL means a faster/smaller backup), never required for correctness. PASSIVE "does as much work as it can without interfering with other database connections" (sqlite.org/wal.html) — it never blocks, so a busy store just gets a smaller optimization for free instead of a stall. KEEP=7 pruning unchanged.

REJECTED_ALTERNATIVES: Dropping the pre-checkpoint entirely (no PRAGMA call at all) was considered — simpler, and correctness-equivalent since the backup API handles WAL content either way. Kept PASSIVE instead of dropping it: it's free (never blocks) and still shrinks the WAL opportunistically between backups, which keeps backup file size and copy time down over time — a real, if minor, ops benefit with zero downside now that it can't stall anything.

## review-trovex verdict: SHIP
review-trovex: ✅ ship — 2 files, +134/-2 — gate green (ruff+pytest, 490 passed), no schema change, no secret/brand leak. Source-guard test pins the exact PRAGMA string (not a blind TRUNCATE-anywhere-in-file grep, which would false-positive on this very explanatory comment); concurrency test proves make_backup completes fast with a held reader and the resulting file is a real, independently-queryable KNN-capable snapshot.

## 3. Files changed

```
src/trovex/backup.py |  15 ++++++-
 tests/test_backup.py | 121 +++++++++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 134 insertions(+), 2 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `2081581c-cb7d-4ee5-b181-705724c6da8d`._
