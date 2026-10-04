# [trovex/perf B] serving under concurrency: load-shed /api/boot, background log writer, read conn per thread, /healthz off pool, TRUNCATE fix

## Team : trovex-backend (tsukumo)
## Branch : feat/perf-b-b02389c2 (from dev)
## Relay task : b02389c2-c869-446c-88d1-60babe9a99be
## Trace : trace=74cd2f7293fb1145baee1e2256b2db9b
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. /api/boot has a server deadline (2-3s) and sheds immediately (empty pack, 200) when the pool is saturated or the client disconnected; test pins both
- [ ] 2. query logging moved to a single background writer with its own connection; boot path does zero writes; test pins it
- [ ] 3. read connection per worker thread (or pool) + one writer (db.py:60 shared conn retired); concurrency bench before/after
- [ ] 4. separate worker pools: recall/search vs capture/reindex/checkpoint, so captures never queue ahead of a prompt recall; test pins it
- [ ] 5. /healthz answered on the event loop without the worker pool (already in 35c0631e d17b0f1)
- [ ] 6. WAL TRUNCATE condition fixed (db.py:253) so the WAL returns under its cap after checkpoint; test pins it
- [ ] 7. receipt: 30-way concurrent /api/boot load test p50/p95/errors, before/after (target p95 < 150ms)

## 2. Root cause & decisions

ROOT_CAUSE: concurrent /api/boot stalls. 4 shared offload workers, 30s timeout; one shared sqlite conn for reads + query-log writes (~serial); WAL TRUNCATE gated on log_pages==0 so WAL never shrank; /healthz on worker pool (1badbcf regression). Fix: load-shed + boot deadline, background query-log writer, per-thread read conn, separate recall vs heavy pools, WAL TRUNCATE gate, /healthz on loop.

RED_EVIDENCE:
test_sha: 036a65f
red run at test_sha (tests-only commit on origin/dev 7329c92): tests/test_server.py + test_wal_wedge.py + test_wedge_class2_recurrence.py = 8 failed, 20 errors, 46 passed.
  failed: test_api_boot_sheds_when_pool_saturated, test_api_boot_sheds_when_client_disconnected, test_query_log_writer_writes_enqueued_rows, test_api_boot_enqueues_log_no_synchronous_write (AC1/AC2); test_periodic_checkpoint_tick_truncates_* x3 + test_periodic_tick_truncate_shrink_resets_write_path_backoff (AC5); test_threadlocal_read_conn_is_per_thread (AC3).
  errors: test_wedge_class2_recurrence.py (20) — missing symbols at collection/fixture (AC3/AC4 off-loop + pool helpers).
  passed at test_sha (prove nothing new, pre-existing behavior): 46 incl. unrelated server/boot tests.
impl commit: 5cc75de (src/ identical to f02ea32). bench harness + receipts: last commit.

PRE-SUBMIT: full suite on final tip green (see run below). Guard rule 3 fix included (f02ea32 content).

## review-trovex verdict: SHIP — 11 files, +798/-70 vs origin/dev 7329c92; ruff clean, full suite 1000 passed, no secret/brand/TODO hits.

final tip f9a465c: full suite 1000 passed (331s), tree = tested tip f02ea32 + bench harness/receipts.

## 3. Files changed

```
.niwa/receipts/b02389c2-bench-after.json  |  14 ++
 .niwa/receipts/b02389c2-bench-before.json |  14 ++
 .niwa/receipts/b02389c2-bench.md          |  30 +++++
 scripts/bench_boot_concurrency.py         | 170 ++++++++++++++++++++++++
 src/trovex/db.py                          |  79 ++++++++++-
 src/trovex/offload.py                     |  53 ++++++++
 src/trovex/server.py                      |  89 +++++++++----
 src/trovex/usage.py                       | 210 +++++++++++++++++++++++++-----
 tests/test_server.py                      |  84 ++++++++++++
 tests/test_wal_wedge.py                   |  86 ++++++++++--
 tests/test_wedge_class2_recurrence.py     |  39 +++++-
 11 files changed, 798 insertions(+), 70 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `b02389c2-c869-446c-88d1-60babe9a99be`._
