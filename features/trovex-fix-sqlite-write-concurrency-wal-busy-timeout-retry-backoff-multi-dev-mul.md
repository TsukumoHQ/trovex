# [trovex] Fix sqlite write concurrency: WAL + busy_timeout + retry-backoff (multi-dev/multi-agent lock contention)

## Team : trovex-backend (tsukumo)
## Branch : fix/sqlite-wal-busy-retry (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

ROOT_CAUSE: SqliteStore.put/delete had no retry on SQLITE_BUSY. WAL mode and
busy_timeout=30000 were already enabled in db.open_db (landed in an earlier
task, af9f97f) — confirmed via `PRAGMA journal_mode`/`PRAGMA busy_timeout`,
not assumed off. Those make sqlite itself wait up to 30s for a lock before
raising, but a caller whose transient cross-process contention (a separate
`trovex serve`/CLI process's own connection to the same trovex.db) outlasts
that window still got a raw sqlite3.OperationalError("database is locked")
surfaced straight to the MCP caller — observed live: 5 fleet agents
respawning near-simultaneously made trovex_write from cto-tsukumo fail 3x
running before giving up.

DECISION: add an outer `_retry_on_locked` decorator in store.py, applied to
SqliteStore.put and SqliteStore.delete (the two write entry points behind
trovex_write/trovex_delete/capture). On sqlite3.OperationalError whose message
contains "locked" or "busy", it rolls back the connection (undoing any partial
pre-commit work so the retried call starts clean, not layered on an aborted
transaction) and retries with backoff (0.2s, then 0.4s) for up to 3 attempts
total before re-raising. Any other OperationalError (e.g. a real schema bug)
is never retried — it raises immediately, so a genuine error still surfaces
loud rather than being masked by 3 silent retries.

REJECTED ALTERNATIVE: raising busy_timeout further instead of adding retry.
Rejected because 30s is already generous (sized for the ~25s full-corpus
reindex transaction) and the AC explicitly calls for a retry layer as the
narrow-case fallback on top of busy_timeout, not a replacement for it — the
two are complementary (busy_timeout is sqlite's own C-level wait; the retry
covers the case a competing writer's transaction genuinely outlives even that).

TEST: tests/test_db.py::test_open_db_enables_wal_and_busy_timeout confirms
WAL + busy_timeout=30000 are on. tests/test_store.py adds a real cross-process-
shaped repro (multiple SqliteStore instances, each its own sqlite connection,
to the same db file, concurrent puts via ThreadPoolExecutor — bypasses the
existing in-process self._lock entirely) plus unit tests of the retry wrapper
itself (retries-then-succeeds, gives-up-after-max-attempts, does-not-retry-
non-lock-errors). Full suite: 402 passed, ruff clean.

## review-backend verdict: SHIP

Checked against every branch of the review-backend checklist. Scope is
store.py's put()/delete() write entrypoints only — no recall/search path (§1),
no auth/secret surface (§4), no schema/embed-dim change (§7), no
token-efficiency/savings-math change (§8) touched.

- §2 write-side integrity: the retry wraps the ENTIRE pre-commit method body
  and calls self.db.rollback() before each retry, so a partially-executed
  transaction is fully undone before the method re-runs from scratch (re-reads
  `existing`/`row` fresh) — no partial-write, no double-insert. Anything after
  the real commit() (the best-effort detect_duplicate_for) is already inside
  its own try/except Exception, so it can never surface an OperationalError
  for the decorator to (mis)retry.
- §5 never-crash-the-agent: a lock that never clears still raises after 3
  attempts — a genuine unresolved contention surfaces loud, it is not
  swallowed. Only "locked"/"busy" messages retry; any other OperationalError
  (e.g. a real schema bug) raises on the first attempt, unretried.
- §9 test discipline: new tests use BagEmbedder / fake objects only, no
  network or real embedder calls; the retry-wrapper unit tests avoid
  monkeypatching sqlite3.Connection.execute (not settable on the C type) by
  testing the decorator against a plain fake object instead.

No findings.

## 3. Files changed

```
src/trovex/store.py | 39 +++++++++++++++++++++
 tests/test_db.py    | 10 ++++++
 tests/test_store.py | 98 +++++++++++++++++++++++++++++++++++++++++++++++++++++
 3 files changed, 147 insertions(+)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `2f3539eb-2ce3-470a-b1af-fc0f6115d7bd`._
