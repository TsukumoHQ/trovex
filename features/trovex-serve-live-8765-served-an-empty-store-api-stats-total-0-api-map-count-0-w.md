# [trovex/serve] live :8765 served an EMPTY store (/api/stats total 0, /api/map count 0) while ~/.trovex-data/trovex.db holds 4664 docs — agents got nothing from trovex

## Team : trovex-backend (tsukumo)
## Branch : fix/serve-empty-store-35c0631e (from dev)
## Relay task : 35c0631e-7c3f-40e6-be81-c08fd89513eb
## Trace : trace=74cd2f7293fb1145baee1e2256b2db9b
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. root cause named with file:line (why the served connection saw 0 rows on a populated DB), proven by a reproducing test
- [ ] 2. fix + regression test
- [ ] 3. /healthz returns non-200 when docs count reads 0 but the DB file has rows (or the store failed to open), answered without the worker pool

## 2. Root cause & decisions

# Decision — 35c0631e [trovex/serve] served-empty-store (frozen snapshot)

ROOT_CAUSE: `src/trovex/usage.py` `log_pointer_query` runs on every `/api/boot`. Its `INSERT INTO mcp_queries` opens an implicit write transaction (Python's default `isolation_level`); if the following `executemany` raises (e.g. a malformed pointer dict missing `"id"`), the `except` swallowed it with **no `db.rollback()`**. That left the long-lived served connection stuck in an open write transaction, which (1) froze every later `SELECT` on that connection to the pre-import snapshot (`/api/stats` served 0 and `/api/boot` recall went empty on a 4.7k-doc store), (2) held the WAL write lock so checkpoints could never run (WAL grew to ~140 MB) and the separate reindex writer hit `database is locked` (writes/log stopped 09-28). Reproduced empirically: after the swallowed error `conn.in_transaction` is True and an external writer is locked out.

## Decision
- **Fix (the bug):** roll back in the `except` (wrapped in `contextlib.suppress` so the best-effort "boot never 500s" contract holds, and the original error is still logged). Releases the half-open write txn.
- **Safety net — `/healthz` served-empty-store guard, LOOP-ONLY (audit Q9):** a frozen/stale server kept answering 200 while serving 0 docs, so the fleet booted empty silently. `AppState.health` now carries a `{stale, detail}` flag, recomputed by a background timer in `lifespan` (`_health_refresh_timer`, every 15 s, on the offload pool like the WAL checkpoint timer) via `_refresh_health -> _healthz_store_counts` (served count vs a **fresh**-connection on-disk count — a frozen snapshot can't vouch for its own stale read). `/healthz` is a pure flag read: no DB, no offload pool on the probe path, instant — 503 iff the flag is stale. A probe can therefore never queue behind recall or orphan a worker during the overload it exists to report.
- **Tests (`tests/test_server.py`):** stuck-txn rollback regression (asserts `in_transaction` False, failed INSERT not committed, external writer not locked out); `/healthz` reads the flag not the DB (loop-only proof); `/healthz` 503 after the background refresh sees served 0 + populated file; 200 on a populated store.

## Scope boundary (findings reported to cto, NOT in this diff)
- Finding (1) `/api/boot` latency: cto's audit found the dominant cause was launchd `ProcessType=Background` (30-55x slower), now hot-patched to Interactive; boot queries the DOC-level vec table (1752 vecs, under the ceiling), so the chunk-partition ratio was not boot's bottleneck. Serving-under-concurrency work tracked separately (b02389c2).
- Finding (3) WAL won't TRUNCATE = downstream of serving latency / a held reader; the periodic TRUNCATE timer recovers once readers are short-lived. cto decision: no manual TRUNCATE; the redeploy restart lets the timer truncate.

## Rejected alternatives
- Leaving the swallowed-error path without rollback (the bug) / switching the served connection to `isolation_level=None`: broader blast radius; the targeted rollback is the minimal local fix for the proven bug.
- **Per-probe `/healthz` store check via `off_loop` (my first cut, 1badbcf): REJECTED per audit Q9** - it took an offload worker on every probe, so a health check could queue behind recall and contribute orphaned workers during overload. Replaced by the background-refreshed flag above; `/healthz` stays loop-only.
- A one-time manual `PRAGMA wal_checkpoint(TRUNCATE)` on the live DB: cto chose the redeploy-restart path; not touching the live DB.

AC4 (live `/api/stats` total == `sqlite3` count, receipt) is post-merge + redeploy, daemon/founder-side (cto approves + redeploys on green).

## review-backend verdict: SHIP

Ran the review-backend checklist against this diff:
- §5 (best-effort vs genuine error) - the core case done right: the fix rolls back the corrupt open-txn state while staying best-effort (`contextlib.suppress`, boot still never 500s, original error still `log.debug`'d). The background refresher and `/healthz` both swallow only their own non-essential errors, and `/healthz` no longer sits on the agent-critical offload pool at all.
- §1 recall / §2 write-integrity / §3 reserved `trovex` source / §7 schema+embed-dim - no impact: the change rolls back a failed `mcp_queries` LOG insert and adds a read-only background health probe + a flag; no search/boot/scope path, no owned-doc write, no schema/migration.
- §4 auth / §6 privacy - `/healthz` is read-only and returns only a flag/detail (doc counts), no secret/token; no default flipped; the on-disk cross-check opens the local DB `query_only` (non-destructive).
- §9 tests - the rollback path, the loop-only `/healthz` contract, and the 503/200 flag behavior are all covered by hermetic BagEmbedder TestClient tests; the wedge-class-2 off-loop guards stay green.
No blocking findings.

RED_EVIDENCE:
  cmd: uv run --extra dev python -m pytest -q tests/test_server.py -k "pointer_query or healthz_503"
  test_sha: d17b0f1ed6be9e46895fbec034217aba954be4fa
  output: |
    (pre-fix tree: src/trovex/{usage,server,state}.py reverted to origin/dev, new tests kept)
    E   ImportError: cannot import name '_refresh_health' from 'trovex.server'   # /healthz guard absent pre-fix
    FAILED tests/test_server.py::test_log_pointer_query_rolls_back_stuck_txn_on_error  # conn left in_transaction / writer locked out
    FAILED tests/test_server.py::test_healthz_503_when_served_empty_but_db_populated
    2 failed, 24 deselected, 1 warning in 5.79s

## targeted-green receipt (cto ruling (a): NIWA_PRESUBMIT_CHECK=0 for this submit; `make test` SIGTERM'd under host freeze)
cmd: uv run --extra dev python -m pytest -q tests/test_server.py tests/test_wedge_class2_recurrence.py
result: 45 passed, 1 warning in 11.63s  (HEAD d17b0f1)
note: verify_cmd (tests/test_server.py) + the wedge-class-2 off-loop guards both green. Gate review + post-merge checks still run.

## 3. Files changed

```
...ty-store-api-stats-total-0-api-map-count-0-w.md |  82 +++++++++++++++++
 src/trovex/server.py                               | 100 ++++++++++++++++++++-
 src/trovex/state.py                                |   5 ++
 src/trovex/usage.py                                |  11 +++
 tests/test_server.py                               |  91 +++++++++++++++++++
 5 files changed, 287 insertions(+), 2 deletions(-)
```

## 4. QA Log

### Round 3 — ❌ REJECTED by review-35c0631e
- 🟢 AC1: Root cause cited with file:line; regression test exercises exact failure path. Reverting rollback makes in_transaction assertion fail. — evidence: src/trovex/usage.py:283-303 names root cause: INSERT INTO mcp_queries opens implicit write txn; if executemany raises, prior except swallowed without rollback leaves long-lived served conn stuck in open write txn -> freezes later SELECTs to pre-import snapshot. Test drives failure path and asserts rollback ran. — test: test_log_pointer_query_rolls_back_stuck_txn_on_error (tests/test_server.py:510) calls log_pointer_query with malformed pointer (no id), executemany raises KeyError; asserts db.in_transaction is False, mcp_queries count unchanged, separate writer not locked out.
- 🟢 AC2: Fix + regression test both present. Safety nets also covered. — evidence: src/trovex/usage.py:301-302 adds rollback wrapped in contextlib.suppress so best-effort contract holds; original error still log.debug'd. /healthz + background refresh timer (server.py:421-447, 1314-1331) are safety net so same incident cannot recur silently. — test: test_log_pointer_query_rolls_back_stuck_txn_on_error (tests/test_server.py:510) is the regression pin; fails pre-fix (in_transaction True, external writer locked out), passes with rollback.
- 🟢 AC3: Mechanism verified by behavioural test. Both served=0+populated-file branch and loop-only contract pinned. Store-failed-to-open branch shares same path as served=0 (both yield 'not served'), so 503 test covers transitively. — evidence: src/trovex/server.py:1314-1331 - /healthz returns PlainTextResponse(detail, status_code=503) when state.health['stale'] set. state.health set by _refresh_health (server.py:424-436) which compares served count (long-lived conn) vs on-disk count (FRESH conn, server.py:470-486): stale when not served (0 OR None = served=0 OR store failed) AND on_disk > 0. — test: test_healthz_503_when_served_empty_but_db_populated (tests/test_server.py:575) swaps state.searcher.db for empty in-memory conn, calls _refresh_health, asserts /healthz returns 503 and body contains 'stale store'. test_healthz_is_loop_only_reads_flag_not_db (tests/test_server.py:561) verifies /healthz never touches DB on probe path. Same code path covers store-failed-to-open (served None -> not served -> on_disk check runs).
- 🔴 AC4: Missing receipt artifact on branch under .niwa/receipts/. Gate forces red. Doer explicitly defers to post-merge, but contract for this criterion is the receipt file itself. — evidence: AC4 is receipt-bearing (live :8765 after redeploy: /api/stats total matches sqlite3 count). Checked .niwa/receipts/ in review worktree and via git log origin/dev..HEAD --diff-filter=A: branch only adds features/trovex-serve-live-8765-...md (scribe provenance). NO receipt artifact committed. Doer's own doc (features/trovex-serve-live-8765...md:37) acknowledges AC4 is post-merge+redeploy. Per brief, receipt-bearing criterion is green ONLY when receipt file under .niwa/receipts/ cites approved sha - none exists. — test: NONE - receipt-bearing criterion cannot be satisfied by unit test of code seam (per brief: field failure 92bd83b0 graded doctor green from a renderer test and shipped binary cargo could not build). No .niwa/receipts/<file> committed on branch, so no receipt=<file> can be cited.

## 5. Timeline

- round 3 → **reject** (review-35c0631e)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `35c0631e`._
