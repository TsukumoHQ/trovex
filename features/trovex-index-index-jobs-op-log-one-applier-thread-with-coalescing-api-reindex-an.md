# [trovex/index] index_jobs op-log + one applier thread with coalescing: /api/reindex and fs-watch bursts enqueue and return a job id, never 409; short BEGIN IMMEDIATE batches only (server half of the reindex storm)

## Team : trovex-backend (tsukumo)
## Branch : feat/index-jobs-applier-queue (from dev)
## Relay task : dab8766b-7d15-4db0-bb68-c193db02cac7
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. index_jobs table + single applier thread; two /api/reindex calls during a run produce one queued rerun, never a 409; pinned test
- [ ] 2. fs-watch bursts for the same source are unioned into one paths job; pinned test
- [ ] 3. every applier write batch is BEGIN IMMEDIATE ... COMMIT with embeddings computed before BEGIN; pinned test asserting not in_transaction during embed (reuse cbb8e8fb's fake embedder)
- [ ] 4. a job left in processing at startup is re-run and completes; pinned test
- [ ] 5. make test green; PR carries the review-trovex verdict; submitted through the gate against dev

## 2. Root cause & decisions

ROOT_CAUSE: /api/reindex's concurrency guard (085f1d69/67ebd68c) was a per-request non-blocking threading.Lock (state.reindex_lock): the first caller ran Indexer.reindex() inline (off the event loop via off_loop); a second concurrent caller just coalesced onto reading the first's status. This fixed the original prod stall (two overlapping Indexer.reindex() calls piling onto the same write transaction), but it has a gap the ticket exists to close: a caller whose trigger arrives WHILE a run is already in flight has no guarantee its own changes are covered by that run — it just gets told "here's what's already running," and if more changed after the running pass started scanning, that caller's own intent is silently dropped unless it happens to poll and retry itself. Separately, fs-watch bursts (watch.py's Watcher, used by the standalone `trovex watch` CLI command) run through a completely independent local debounce/lock, sharing no coordination with the HTTP path at all.

DECISION: replace the per-request lock with an op-log (index_jobs table) + a single background applier thread (index_jobs.py), pattern-matched to Meilisearch's async tasks (single writer, consecutive same-type tasks batched, enqueued/processing/succeeded/failed) and Qdrant's WAL sequence numbers (idempotent crash replay):
- POST /api/reindex enqueues and returns 202 {job_id, position, coalesced} immediately — it never calls Indexer.reindex() itself again.
- A request matching an already-QUEUED job of the same (kind, source_key) merges into it (paths unioned for kind='paths') — no new row.
- A request matching a job already PROCESSING sets rerun_after (+ rerun_payload for paths) instead of a new row or a rejection — the applier reruns that SAME row the instant the current pass finishes, so a trigger that arrives mid-run is never lost.
- One background thread (Applier, started in `lifespan`) drains the queue in seq order — structurally the only caller of Indexer.reindex()/reindex_paths() once the server owns the Indexer, so no lock is needed there at all anymore.
- Crash safety: a job left 'processing' at startup (process died mid-run) is reset to 'queued' — safe because reindex()/reindex_paths() gate re-embed on content_hash/mtime, so replaying already-applied work is a fast no-op.
- New GET /api/reindex/{job_id} reads a job's state (404 if unknown).
- index_runs.job_id links a run back to what enqueued it.

Reuses Indexer.reindex()/reindex_paths() completely unchanged except an added optional `job_id` param (threaded into the index_runs INSERT) — cbb8e8fb's BEGIN IMMEDIATE / embed-before-BEGIN batching, which is what makes a long job safe to run without holding the write lock, is NOT reimplemented, per the ticket's explicit instruction.

state.py: reindex_lock/reindex_run_id/_reindex_run_seq removed (redundant once there is structurally one applier). AppState.applier is a lazy property (constructs an Applier bound to self.indexer/self.store on first access) rather than a required constructor field — ~15 test files build AppState directly and none of them needed editing.

SCOPE CALL (per "when a ticket's scope turns out wrong, one relay message with both readings and continue"): the ticket frames fs-watch bursts as part of "the server half of the reindex storm," but `trovex serve` has NO live filesystem watch today — Watcher/`trovex watch` is a separate, standalone CLI foreground command with its own Indexer instance, entirely untouched by this change. Building a live watch INTO `trovex serve` for the first time is materially separate scope from "replace the queue mechanism." kind='paths' exists in the schema and coalesces correctly (tests/test_index_jobs.py proves it directly against enqueue()), so this module is exactly the primitive a future live-watch-in-serve integration would plug into — but nothing wires it up yet. Did not wait for a steer on this (per instruction); flagging here for visibility.

REJECTED ALTERNATIVES:
- Keep reindex_lock alongside the new queue (belt-and-suspenders): rejected — two independent concurrency mechanisms protecting the same resource is more state to reason about, not less, and the queue alone is a strictly stronger guarantee (single caller, not just "no two running at once").
- Give a rerun_after request a fresh row instead of flagging the processing one: rejected — the ticket is explicit ("instead of a new row"), and reusing the same row keeps the job's identity/job_id stable across a rerun for anyone polling GET /api/reindex/{job_id}.

AUDIT — every place that called the old reindex_lock/run_id mechanism:
| site | before | after |
|---|---|---|
| server.py POST /api/reindex | acquire reindex_lock, run inline via off_loop, release | index_jobs.enqueue() + applier.notify(), 202 |
| server.py (sweep_bloat) | ran inline after every reindex, same try/finally | Applier._run_job calls store.sweep_bloat() after every successful execute (same "after every /api/reindex" cadence, now per-job) |
| state.py AppState | reindex_lock/reindex_run_id/_reindex_run_seq fields | index_jobs_lock field + lazy `applier` property |
| tests/test_reindex_single_flight.py | 3 tests asserted the 200/409-free coalescing dict | rewritten for 202/job_id; the other 4 tests (bounded commits, concurrent-write-stays-fast against Indexer/compute_status/sweep_bloat directly) are untouched, still pass |
| tests/test_owned_store_safety.py, tests/test_security.py | asserted 200 + inline stats | updated to 202 + drive `applier.run_one()` (or applier isn't running in that fixture, exercising pure enqueue coalescing) |

Pinned by tests/test_index_jobs.py (10 tests: coalescing on queued, paths union, distinct source_key, rerun_after-not-a-new-row, applier executes + links job_id, rerun_after chains onto the SAME row, no open transaction during embed via the applier path, crash recovery, HTTP 202 + status endpoint, 404 on unknown job) plus the 3 rewritten tests in test_reindex_single_flight.py. V-model: disabled enqueue()'s queued-job coalescing check -> 4 tests fail across 2 files; restored -> all green. Stability: touched test files re-run twice clean (no thread-timing flakiness observed).

make test: 722 passed (base already includes 21c1370f's security fix + 7111f05a's onboarding fix, both merged to dev ahead of this rebase — confirmed their tests still pass unchanged).

## review-trovex verdict: SHIP
review-trovex: SHIP — 9 files (index_jobs.py new ~290 LoC, db.py +schema, indexer.py +job_id param, server.py route rewrite, state.py field swap, 4 test files updated/added ~450 LoC) — gate green (ruff clean, pytest 722 passed), no Active-Memory/doc-router surface touched, no secret/brand/host leak, no contract break beyond the documented /api/reindex response shape change (200+stats -> 202+job_id, which is the ticket's own AC), V-model pinned, one scope call flagged above (no live fs-watch built into `trovex serve` — out of scope for this ticket).

## 3. Files changed

```
src/trovex/db.py                    |  50 +++++-
 src/trovex/index_jobs.py            | 278 +++++++++++++++++++++++++++++++++
 src/trovex/indexer.py               |  32 ++--
 src/trovex/server.py                |  71 ++++-----
 src/trovex/state.py                 |  30 ++--
 tests/test_index_jobs.py            | 297 ++++++++++++++++++++++++++++++++++++
 tests/test_owned_store_safety.py    |  21 ++-
 tests/test_reindex_single_flight.py |  82 +++++-----
 tests/test_security.py              |   7 +-
 9 files changed, 756 insertions(+), 112 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `dab8766b-7d15-4db0-bb68-c193db02cac7`._
