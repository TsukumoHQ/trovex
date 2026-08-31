# [trovex/serve] Post-deploy stall triage: write+search 30s timeouts at 19:34-19:35Z ON build 8bf75f6 (wedge fixes included), pid 87916 at ~350% CPU for 1h40

## Team : trovex-backend (tsukumo)
## Branch : fix/wal-checkpoint-passive-mode (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

ROOT_CAUSE: `checkpoint_if_wal_large()` (src/trovex/db.py:105) ran `PRAGMA wal_checkpoint(TRUNCATE)` synchronously on the shared write connection after every commit once the WAL crossed 10MB. TRUNCATE requires exclusive access (no active reader on any WAL frame); under sustained concurrent read traffic (fleet-wide `/api/boot` searches) it almost never gets that window and busy-waits on the connection's `busy_timeout`. Prod (task 7768dbe6, 2026-08-31): live probes showed `trovex_write` timing out at HTTP 504/~49.7s and `trovex_search` at ~29.8s — both landing right at the configured `busy_timeout=30000`ms. A `sample` capture of pid 87916 confirmed one thread pinned in `pysqlite_connection_execute → sqlite3_step → sqlite3VdbeExec → btreeBeginTrans → sqliteDefaultBusyCallback → unixSleep → nanosleep` for 2088/2098 samples (~99.5% of the window) — the checkpoint call, not reindex (no reindex/compute_status/embedder frames in the Python stack; the CPU load was legitimate concurrent ONNX embedding inference from fleet-wide search traffic, not a busy-loop). Not a recurrence of the prior wedge classes (33ca98a, f2b4c872) — this is a new bottleneck exposed only once concurrent read volume grew enough that TRUNCATE's exclusivity requirement stopped being satisfiable in practice.

FIX: swap TRUNCATE → PASSIVE. PASSIVE checkpoints as many WAL frames as it can without waiting on any reader/writer and returns immediately either way — it may leave the WAL only partially truncated under sustained load (a disk-space/housekeeping tradeoff, not an availability one), but it can never wedge the write path. Added `test_checkpoint_if_wal_large_uses_passive_not_truncate` (tests/test_wal_wedge.py) to pin the mode so it can't silently regress back to a blocking checkpoint.

## review-backend verdict: SHIP
Scope check against the review-backend checklist (§1-8): no recall/retrieval path touched (§1), no write-data-integrity change — the checkpoint call runs after commit and doesn't alter what gets written/versioned/cascaded (§2), no source-id logic (§3), no auth/secret surface (§4), the existing try/except best-effort shape around the checkpoint call is unchanged, still never propagates (§5), no privacy-default change (§6), no schema/embed-dim change (§7), no token-output-shape/savings-math change (§8). Falls entirely under §9 (test discipline): new test on a recognized path (tests/test_wal_wedge.py), hermetic (BagEmbedder fixture, no network), asserts the exact PRAGMA string so it can't drift back to a blocking mode. 465/465 tests green, ruff clean on both changed files.

## 3. Files changed

```
src/trovex/db.py        | 15 +++++++++++++--
 tests/test_wal_wedge.py | 29 +++++++++++++++++++++++++++++
 2 files changed, 42 insertions(+), 2 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `7768dbe6-2fed-4c14-a863-bf6e97fafadd`._
