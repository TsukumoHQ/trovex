# [trovex/serve] Wedge class 2 RECURRENCE despite 33ca98a: CallToolRequest wedge + 407% CPU busy-spin, tool timeout doesn't unwedge

## Team : trovex-backend (tsukumo)
## Branch : fix/serve-inline-blocking-routes (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

ROOT_CAUSE: 33ca98a off-loaded the 9 MCP `@mcp.tool()` handlers but never touched FastAPI's own routes. Confirmed from a LIVE thread dump on the wedged prod process (macOS `sample`, py-spy needed unavailable sudo, two samples 2s apart): the main event-loop (uvloop) thread ITSELF was inside `onnxruntime::InferenceSession::Run` (embedding matmul, spin-waits its own worker threads across cores = the 407%+ CPU), reached via a plain coroutine chain, not any executor thread. `/api/capture` called `capture_state()` -> `store.put()` -> `embedder.embed()` INLINE in its `async def` route; several doc-mutation routes (restore/undelete re-embed via `put()`; delete/tags/collections hit `_retry_on_locked`'s real `time.sleep` backoff) did the same. Because the LOOP THREAD is the one stuck in native code, no coroutine can run — including `asyncio.wait_for`'s own timeout callback — which is why TROVEX_TOOL_TIMEOUT_SEC never fired and even bare /healthz went dark. 37 orphaned python threads were live during the wedge, consistent with prior timed-out MCP tool calls whose underlying thread never got a slot back (starlette's `run_in_threadpool` uses anyio's shared, unbounded-relative-to-this-app default CapacityLimiter).

DECISION: Centralize every blocking call site (MCP tools AND FastAPI routes) behind one shared `offload.off_loop` — a dedicated, small, BOUNDED ThreadPoolExecutor (not the shared default), so orphaned calls have a capped blast radius instead of silently growing threadpool pressure forever. Added `offload.run_watchdog`: if the pool is ever fully saturated by orphaned (past-own-deadline) calls for TROVEX_WATCHDOG_SATURATION_SEC (default 120s), it self-heals via process exit (launchd restarts it) — automating the manual `launchctl kickstart` mitigation already in use. `/api/reindex`'s inline-blocking + no-concurrency-guard half of this class (task 085f1d69, already implemented+tested, never merged) is folded in here rather than shipped as a second competing PR. `/api/boot` degrades to its own existing empty-pack contract on timeout (`boot_pointers` must never 500); every write route returns a clean 504 via a small `_offloaded` helper instead of an unhandled-exception 500.

REJECTED_ALTERNATIVE: only fixing `/api/capture` (the one route with live forensic evidence). Rejected because the same inline-blocking pattern (embed-on-restore/undelete, retry-on-locked backoff on delete/tags/collections) exists on every other write route for the identical reason — 33ca98a's off-loop fix was applied to MCP tools only, not systematically — and CTO's explicit ask was to sweep all FastAPI routes, not patch the one with a smoking gun.

[LEGACY_OPPORTUNITY]: MCP resource handlers (`resources.py`-equivalent `@mcp.resource(...)` functions in `mcp_app.py`) remain plain sync `def`s dispatched directly by FastMCP, same as tools were before 33ca98a — not off-loaded by this fix either (pre-existing follow-up, memory key `trovex-serve-resources-sync-followup`). They're DB-read-only (no embed call), so lower risk than the routes fixed here, but the same class of bug in miniature if a resource handler's DB read ever blocks on a contended write.

## review-backend verdict: SHIP

review-backend: self-reviewed against every branch — §1 recall/retrieval (untouched: no scope/floor/case-normalization change), §2 write integrity (untouched: no change to dup-guard/section-patch/cascade-delete/versioning; only the dispatch boundary moved), §3 reserved source id (untouched), §4 auth ordering preserved — every `_write_authorized()` check still runs BEFORE its route's offload call, unchanged, §5 TimeoutError is the narrow except everywhere (only that type is caught; every other exception still propagates as before) and is correctly mapped to a loud, non-2xx 504 (or /api/boot's own pre-existing empty-pack-on-failure contract) rather than swallowed or crashing the loop, §6 no default changes (host/embedder/retention untouched), §7 no schema change, §8 no output-shape/token-cost change, §9 hermetic BagEmbedder regression tests added for every touched route including an injected-stuck-handler test proving /healthz stays responsive while a route is off-loop-stuck, plus bounded-pool and watchdog-self-heal tests. No correctness/invariant regressions found.

pytest: 458 passed (446 baseline + 3 reindex-single-flight + 12 wedge-class-2-recurrence, incl. the injected-stuck-handler /healthz test and bounded-pool/watchdog tests). ruff clean.

## 3. Files changed

```
src/trovex/indexer.py                 |  31 +++
 src/trovex/mcp_app.py                 |  56 +++---
 src/trovex/offload.py                 | 175 +++++++++++++++++
 src/trovex/server.py                  | 142 ++++++++++----
 src/trovex/state.py                   |   8 +-
 tests/test_reindex_single_flight.py   | 182 ++++++++++++++++++
 tests/test_wedge_class2_recurrence.py | 344 ++++++++++++++++++++++++++++++++++
 7 files changed, 875 insertions(+), 63 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `f2b4c872-472b-4b59-8bba-66a5aed05e21`._
