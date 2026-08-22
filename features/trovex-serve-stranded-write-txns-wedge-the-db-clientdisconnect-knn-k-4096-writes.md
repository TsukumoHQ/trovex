# [trovex] serve: stranded write txns wedge the db (ClientDisconnect + knn k>4096) — writes fail until restart

## Team : trovex-backend (tsukumo)
## Branch : fix/trovex-wal-wedge (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

# stranded write-txn wedge — trovex serve (eda6f60e)

## ROOT_CAUSE
Two independent triggers strand an uncommitted write transaction on the shared
sqlite connection, after which every subsequent write hits "database is
locked" until the process restarts:

1. **`_retry_on_locked`'s original except-clause never rolled back a
   non-`SQLITE_BUSY` error** — it checked `_is_locked_error` and re-raised
   BEFORE calling `self.db.rollback()`, so a genuine exception (a
   `ClientDisconnect` mid-request, an embed failure, any handler bug) left the
   implicit transaction open. The next write on that same connection piled
   onto it instead of starting clean — writes accumulated but never flushed,
   and the WAL couldn't checkpoint past it.
2. **`compute_status`'s blanket promote-to-canonical UPDATE** (`status.py`)
   raises `sqlite3.IntegrityError` on `idx_docs_canonical_topic` whenever 2+
   non-superseded docs already share a `canonical_topic` — observed live via
   `api_reindex` → `indexer.reindex` → `compute_status`. `Indexer.reindex`/
   `reindex_paths` build one large transaction from first write to a final
   `self.db.commit()` with no try/except, so this IntegrityError stranded the
   same class of open transaction — different trigger, same wedge.

Also present but separately gated: sqlite-vec's KNN `k` param has a hard
4096 ceiling; `search_chunks`'s tag-scoped path already hardcodes `k=4096`
(no doc-count-dependent widen) since the P2a partition refactor (dev commit
`c9c5320`, predates this task) — confirmed still true, locked in with a
regression test rather than re-fixed.

## CHANGE
- `store.py` `_retry_on_locked`: broadened to catch `BaseException`, rollback
  UNCONDITIONALLY before deciding to retry or re-raise (was: rollback only on
  the locked-retry path, never on a surfaced error). Applied to the 11
  previously-undecorated write methods (`set_lifecycle`, `delete_by_id`,
  `set_pinned`, `recompute_importance`, `sweep_retention`, `sweep_bloat`,
  `restore_deleted`, `put_batch`, `set_tags`, `create_collection`,
  `delete_collection`) — `put`/`delete` already had it.
- `db.py`: `checkpoint_if_wal_large(conn, db_path)` + `WAL_WARN_BYTES=10MB` —
  forces `PRAGMA wal_checkpoint(TRUNCATE)` when `<db>-wal` exceeds the
  threshold; called after every successful decorated write as a backstop.
  Entirely best-effort: wrapped so no exception (stat() OSError, checkpoint-
  time sqlite error) can ever propagate out of an already-committed write.
- `status.py` `compute_status`: resolves `canonical_topic` collisions FIRST
  (winner = current-canonical, else newest mtime/highest id; losers demoted to
  `status='duplicate', dup_of_id=<winner>`) before the blanket promote, so the
  UPDATE never sees 2 eligible canonical_topic peers.
- `indexer.py`: `_rollback_on_error` (same shape as store's, no retry — just
  rollback-on-any-exception + checkpoint-on-success) applied to `reindex()`
  and `reindex_paths()`.
- `tests/test_wal_wedge.py` (new, 9 tests): exception-mid-put stays writable
  (AC5 literal repro); generalized decorator rolls back on ANY exception;
  locked-retry regression; WAL-watchdog force/no-op; watchdog exception
  never propagates past a committed write; `compute_status` collision
  resolution; `indexer.reindex` rollback on `compute_status` failure;
  tag-scoped search survives a >4096-chunk partition (AC1 lock-in).

## REJECTED ALTERNATIVE
Considered fixing AC1 by re-deriving `k = min(doc_count, 4096)` at query time.
Rejected: the P2a partition refactor already bounds per-partition chunk count
below the ceiling by design and hardcodes `k=4096` for the tag-scoped branch —
re-deriving doc_count would add a query for no behavioral gain. Wrote a
regression test instead (>4096-chunk partition, `search_chunks` must not
raise) to lock the invariant in, since nothing previously proved it.

Considered implementing AC4 (0.0.0.0 bind + explicit-auth-token guard) in this
PR. Deferred: it requires coordinating a startup-guard escape hatch with the
live launchd-managed prod deploy (`~/.config/trovex-growth/deploy-wt/trovex/
deploy/serve-trovex.sh`, not this repo) or the service refuses to boot.
Flagging as a fast-follow ticket rather than blocking a P1 wedge fix (4th
re-wedge same day) on ops coordination that has no reply yet.

## TEST
`uv run pytest -q` — 411 passed, 0 failed (was 410 before the self-review
fix added one more). `uv run ruff check .` — clean.

## review-backend verdict: SHIP (after one fix)
Scope: src/trovex/{store,db,status,indexer}.py, tests/test_wal_wedge.py,
tests/test_store.py (checkpoint-on-success fixture patch).
Gate: uv run pytest -q (411/411) / uv run ruff check . (clean).
Found during self-review (§5, never-crash-the-agent): `checkpoint_if_wal_large`
runs AFTER the caller's write already committed, but only caught
`FileNotFoundError`/`sqlite3.OperationalError` — any other exception (a
`PermissionError` from `stat()`) would propagate out of a write call that had
already succeeded, turning a committed write into a reported failure to the
agent. Fixed: wrapped the whole body, `except OSError: pass` /
`except sqlite3.Error: log.warning(...)` — nothing from this best-effort
backstop can escape a successful write. Regression test added
(`test_checkpoint_if_wal_large_never_propagates`).
No other findings: recall paths untouched (§1 n/a), every stranded-transaction
class rolls back before retry/raise not after (§2), no delete/schema/auth
surface touched (§3/§4/§7), no default binding changed — AC4 explicitly
deferred not silently dropped (§6), no response-shape or savings-math change
(§8), new behavior is test-covered and hermetic via BagEmbedder (§9).

## VERDICT
SHIP. Files: src/trovex/store.py, src/trovex/db.py, src/trovex/status.py,
src/trovex/indexer.py, tests/test_wal_wedge.py, tests/test_store.py.
Branch fix/trovex-wal-wedge off dev@ebd5f60. AC1/AC2/AC3/AC5 done +
regression-tested; AC4 deferred to a fast-follow ticket (ops coordination
needed, documented above).

## 3. Files changed

```
src/trovex/db.py        |  34 ++++++
 src/trovex/indexer.py   |  35 +++++-
 src/trovex/status.py    |  43 +++++++-
 src/trovex/store.py     |  40 ++++++-
 tests/test_store.py     |   2 +
 tests/test_wal_wedge.py | 279 ++++++++++++++++++++++++++++++++++++++++++++++++
 6 files changed, 426 insertions(+), 7 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `eda6f60e-5158-47b1-8263-50aee0f4eb01`._
