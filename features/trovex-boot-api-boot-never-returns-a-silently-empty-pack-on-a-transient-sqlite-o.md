# [trovex/boot] /api/boot never returns a silently empty pack on a transient sqlite OperationalError under load

## Team : trovex-backend-2 (tsukumo)
## Branch : trovex-backend-2/boot-degraded (from dev)
## Relay task : 7df08701-fd7e-4ae6-a3b7-2cde620a84ae
## Trace : trace=6aa09f880f61bd0733a23da9357fe9aa
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. test: an injected transient OperationalError during boot search is retried or surfaced (degraded flag + log line), never an unflagged empty pack
- [ ] 2. root cause of the real trigger named with file:line
- [ ] 3. tests/test_server.py green 10/10 under a parallel load harness

## 2. Root cause & decisions

# 7df08701 — /api/boot never a silently empty pack under contention

ROOT_CAUSE: /api/boot returned an UNFLAGGED empty pack on two shed paths, so the
prompt hook could not tell "no records" from "recall shed under load". The REAL
trigger (corrected from the ticket's suspicion) is the 2.5s offload wall-deadline
`_BOOT_OFFLOAD_TIMEOUT_SEC` (src/trovex/server.py:50), blown under CPU starvation
→ `TimeoutError` → `_empty_pack()` returned silently (src/trovex/server.py
api_boot, the `except TimeoutError` arm). The `except sqlite3.OperationalError →
empty` in `boot_pointers` (src/trovex/boot.py) is a SECOND latent silent-empty
path. This matches the observed data exactly: the perf-A truncate test recalled
fine at low load (full run ~60s) and returned `pointers=[]` only when the host
was contended (runs 128–151s under load 58–100).

## Investigation — the suspected conn race does NOT reproduce
The ticket suspected a transient lock from the shared `searcher.db` connection.
Reproduced it directly: 16 reader threads running the real boot KNN + a writer
thread doing the real `log_pointer_query` INSERT, all on ONE shared connection =
**0 errors, 0 silent-empties**. Python's sqlite3 serialises operations on a
connection via its own mutex, so cross-thread use here does not raise. The
connection race is therefore NOT the trigger; the offload deadline is.

## Decision
- Add a `degraded` field to the /api/boot response schema: `None` = a true scope
  miss ("no records"); a string = recall was SHED, naming which path. Prod and
  hook/agents can now distinguish the two, and each shed path logs a WARNING.
  - `src/trovex/server.py` api_boot: `TimeoutError` → `degraded="timeout"`;
    load-shed (pool saturated / client gone) → `degraded="shed"`.
  - `src/trovex/boot.py` boot_pointers: narrow the except — the GENUINE sqlite-vec
    KNN ceiling (`"k value in knn query too large"`) → `degraded="ceiling"`
    (a bounded, legit empty); ANY OTHER `OperationalError` (lock/busy/transient)
    → `degraded="sqlite"` + log, never a silent empty. The swallow is NOT widened.
  - Healthy recall → `degraded=None` (the flag is always present in the schema).
- The 2.5s deadline is a PROD load-shed knob and stays unchanged. Correctness
  tests must not depend on host speed, so `tests/test_server.py` sets a generous
  boot deadline via an autouse fixture (prod default untouched).

Never-500 contract preserved: every path still returns a pack (empty + flagged),
boot never raises into the agent's tool call (review-backend §5: best-effort but
NOT silent).

## AC mapping
- AC1 (injected transient OperationalError retried/surfaced, never unflagged
  empty): `test_boot_pointers_flags_transient_sqlite_error_not_silent`,
  `test_api_boot_timeout_is_flagged_not_silent`.
- AC2 (root cause named with file:line): server.py:50 + api_boot `except
  TimeoutError` (primary), boot.py `except OperationalError` (secondary); conn
  race disproved above.
- AC3 (test_server.py green 10/10 under a parallel load harness): 10 concurrent
  full-file runs = 10/10 green (runs took ~27s each = real contention, vs ~8.6s
  solo). Plus `test_api_boot_concurrent_recall_never_silent_empty` as an
  in-suite guard.

[LEGACY_OPPORTUNITY] db.py `ThreadLocalReadConn` exists and its docstring invites
wiring `Searcher.db` to it (per-thread read connections) as the search.py-lane
follow-up — not needed for this fix, deferred.

## Bundled gate-unblock (separate commit)
dev HEAD (c33c735, perf B) shipped `scripts/bench_boot_concurrency.py:101` with a
RUF046 (`int(round(...))` — redundant) that fails `make test` (ruff) for EVERY
trovex presubmit = a gate false-red blocking the whole lane. The freeze permits
fixing gate false-reds; one-line fix committed separately (`chore: [trovex/ci]`)
so my submit is not wedged behind a dev-wide lint break. Not part of 7df08701's
ACs; isolated to its own commit for a clean review.

RED_EVIDENCE:
  cmd: uv run --extra dev python -m pytest -q tests/test_server.py
  output: |
    >       assert body["degraded"] == "timeout"
    E       KeyError: 'degraded'
    tests/test_server.py:755: KeyError
    FAILED tests/test_server.py::test_boot_pointers_flags_vec_ceiling_distinctly
    FAILED tests/test_server.py::test_boot_healthy_recall_is_not_degraded - KeyError: 'degraded'
    FAILED tests/test_server.py::test_api_boot_timeout_is_flagged_not_silent - KeyError: 'degraded'
  test_sha: 1327638

## review-backend verdict: SHIP
Change is exactly review-backend §5 (best-effort vs genuine error): the prior
`except → empty` swallowed a genuine transient/timeout as silent-wrong; the fix
surfaces it (degraded flag + WARNING log) while keeping boot's never-500 contract.
No §1 recall/scope/score logic touched; `degraded` is additive (no test asserts
the boot-response key-set); tests hermetic (BagEmbedder, no network). SHIP.

## 3. Files changed

```
scripts/bench_boot_concurrency.py |   2 +-
 src/trovex/boot.py                |  31 +++++++++--
 src/trovex/server.py              |  21 +++++--
 tests/test_server.py              | 113 ++++++++++++++++++++++++++++++++++++++
 4 files changed, 158 insertions(+), 9 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `7df08701-fd7e-4ae6-a3b7-2cde620a84ae`._
