# [trovex/serve] reindex must never hold the writer lock across the scan — short write txns + interim: pause auto-reindex until landed

## Team : trovex-backend (tsukumo)
## Branch : fix/sweep-bloat-lock-batching (from dev)
## Relay task : a9850600-144b-4d50-8690-c022bb0d27fb
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. INTERIM applied on prod today: auto-reindex paused/lengthened, PASSIVE checkpoint backfills frames, probe trovex_write <5s, recorded in the deploy record with numbers
- [ ] 2. reindex() splits read-only scan/hash/embed from write application; no write transaction spans the scan
- [ ] 3. each write transaction is time-bounded (~1s) and released between batches; concurrent SqliteStore.put p95 <1s during a full reindex of a 10k+ doc corpus (test)
- [ ] 4. root cause of 220s for 11k unchanged docs identified and fixed or explicitly deferred with numbers
- [ ] 5. 467+ suite green, review-trovex verdict, merged via gate, deployed, post-verify numbers reported

## 2. Root cause & decisions

# Decision — sweep in-process lock wedge (task a9850600)

ROOT_CAUSE: After the reindex write-txn fix (2d23c39) freed the SQLite writer lock (BEGIN IMMEDIATE <1s, PASSIVE checkpoint busy=0), trovex_write STILL timed out at 30s while reads stayed fast (16–350ms). The wedge had moved IN-PROCESS: `store.sweep_bloat()` runs after EVERY reindex (server.py:947 api_reindex) and held the Python `self._lock` across its whole body — the superseded-fork tombstone loop AND phase-4 `reconcile_vec_meta`, which re-syncs every vec row the sweep's bulk stale-UPDATE just marked (live: 4538 mismatched rows, ~1ms/row = 4+s) one rowid at a time. put()/check_duplicate also take `self._lock`, so they blocked for the sweep's full duration even though the DB lock was free. Reads never touch `_lock` — exactly why the differential showed reads fast / writes wedged.

## Decision
Break the whole-sweep `_lock` hold into short, released bursts:

1. **Tombstone loops batched** (commit 69ba336): `_tombstone_ids_batched` snapshots the doomed ids, then tombstone-deletes them in `_SWEEP_LOCK_BATCH` (200) chunks, acquiring + committing + releasing `_lock` per chunk. `_collapse_ephemeral_owners_locked` split into a compute-only `_ephemeral_owner_victims_locked` + the shared batched pass.

2. **reconcile_vec_meta batched** (commit 26d8696): `reconcile_vec_meta(conn, *, on_batch=None, batch_size=200)` calls `on_batch` after every `batch_size` synced rows. `Store._reconcile_vec_meta_batched()` passes a callback that commits and briefly RELEASES + re-acquires `_lock` every `_SWEEP_LOCK_BATCH` rows so a concurrent put() interleaves. A 1ms yield between release and re-acquire is required — releasing then re-acquiring in the same thread otherwise wins the lock back before the OS schedules the blocked waiter (releasing a Lock does not release the GIL). Applied to both `sweep_bloat` (proven per-reindex wedge) and `sweep_retention` (opt-in/off in prod, same latent pattern).

Semantics preserved: same phase order, same return dicts, still idempotent. A snapshotted id deleted by a racing writer mid-sweep is a safe no-op (both tombstone helpers and `vec_sync_meta` skip a missing row). `vec_sync_meta` reads CURRENT doc state, so releasing the lock between reconcile batches introduces no staleness; new mismatches created mid-sweep are caught by the next reindex's sweep. Snapshot + cascade-delete still commit together per chunk, so a doc is never deleted without its recoverable `doc_tombstones` snapshot. `reconcile_vec_meta`'s default `on_batch=None` keeps the existing `compute_status` caller (status.py:157) byte-identical.

## Rejected alternatives
- **Drop phase-4 reconcile from sweep_bloat** (rely on compute_status' reconcile): rejected — the sweep's OWN stale-UPDATE creates the 4538 mismatches AFTER compute_status ran, so vec rows stay drifted (wrong KNN status/lifecycle metadata) until the next reindex.
- **Reconcile with no lock**: rejected — `self.db` is a single shared connection; concurrent access without `_lock` races the writer. The lock must be held per batch, just not across the whole loop.
- **`time.sleep(0)` as the yield**: rejected — too weak under load (can return before the OS schedules the waiter); `0.001` reliably yields and is a rounding error against a multi-second pass.
- **TRUNCATE/one-shot checkpoint**: rejected — memory `trovex-serve-wal-flush-mode` (never TRUNCATE on the shared write connection). Not the lock problem here anyway.

## Verification
- ruff check clean; full suite 473 passed (hermetic, BagEmbedder).
- `test_concurrent_put_stays_fast_during_sweep_bloat_reconcile` (tests/test_reindex_single_flight.py): 40 aged canonicals, slowed per-row `vec_sync_meta` (~2s full resync); a put() on the SAME store (sharing `_lock`) issued mid-reconcile finishes in <1s (pre-fix ~2s). Stable across 3 runs.
- `test_sweep_bloat_releases_lock_between_batches` (tests/test_active_memory.py): counts lock acquisitions with a tiny batch = proves release-per-chunk, not one hold.

## review-trovex verdict: SHIP
4 files, ~90 LoC. Gate green (ruff check clean + 473 pytest passed, hermetic). Active-Memory invariants held (no retrieval/scope/owner-tag/upsert change; vec0 metadata sync semantics identical). No secret/brand/host/number leak. Lock discipline: acquire/release balanced on every path including exceptions (finally releases exactly one hold); `reconcile_vec_meta` default `on_batch=None` keeps the compute_status caller byte-identical.

## 3. Files changed

```
src/trovex/db.py                    |  26 +++++++-
 src/trovex/store.py                 | 119 +++++++++++++++++++++++++++++-------
 tests/test_active_memory.py         |  60 ++++++++++++++++++
 tests/test_reindex_single_flight.py |  91 ++++++++++++++++++++++++++-
 4 files changed, 270 insertions(+), 26 deletions(-)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-a9850600-144b-4d50-8690-c022bb0d27fb

## 5. Timeline

- round 1 → **reject** (review-a9850600-144b-4d50-8690-c022bb0d27fb)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `a9850600-144b-4d50-8690-c022bb0d27fb`._
