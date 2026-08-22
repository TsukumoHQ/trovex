# [trovex/serve] Wedge class 2: MCP CallToolRequest blocks whole event loop (recurring prod outage, NOT the WAL class)

## Team : trovex-backend (tsukumo)
## Branch : fix/serve-event-loop-block (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

ROOT_CAUSE: Every `@mcp.tool()` handler in `src/trovex/mcp_app.py` (trovex, trovex_write, trovex_tag, trovex_read, trovex_search, trovex_delete, trovex_archive, trovex_restore, trovex_undelete) is a plain `def`, not `async def`. The mcp SDK (mcp==1.28.1) computes `fn_is_async` once at tool registration (`Tool.from_function` → `_is_async_callable`) and, being False here, calls the handler directly on the single asyncio event loop instead of awaiting it (`func_metadata.py:93-96`). That loop is the SAME one serving every other route, since `server.py:323` mounts the MCP app into the same FastAPI app. The default-on local rerank tier (`rerank_local.py:63`, `fastembed.rerank.cross_encoder.TextCrossEncoder`) does a lazy, unbounded network fetch of its ONNX model on first use — `fastembed`'s constructor takes no timeout parameter at all, and the call was never offloaded to a thread. A slow/stuck fetch there (or in the embedder's OpenAI client, or a contended `store._lock`) froze the entire event loop, killing `/api/boot` and every other in-flight request along with the stuck tool call — the exact 2026-08-22 ~15:53Z incident (serve.log ends mid "Processing request of type CallToolRequest", external sqlite PRAGMA wal_checkpoint(PASSIVE) succeeded while hung, ruling out the WAL-class fix from eda6f60e).

DECISION: Fix at the dispatch boundary rather than instrumenting every individual outbound call, because the one call actually responsible (fastembed's TextCrossEncoder/TextEmbedding construction) has no timeout hook to give it. `_off_loop` (mcp_app.py) wraps each tool with a `functools.wraps`-preserving async twin that runs the real sync handler via `starlette.concurrency.run_in_threadpool` (same primitive already used for `/api/boot`), bounded by `asyncio.wait_for(..., timeout=TROVEX_TOOL_TIMEOUT_SEC)` (env-configurable, default 30s). `mcp.add_tool(dispatched)` registers the async twin for real MCP dispatch while the decorator returns the ORIGINAL sync function unchanged, so the module-level name (`mcp_app.trovex_write` etc.) stays synchronously callable — required because the existing test suite (test_mcp_errors.py, test_terse_citations.py, etc.) calls these functions directly and expects a plain string back, not a coroutine.

REJECTED_ALTERNATIVE: Making the tool functions themselves `async def` and rewriting their bodies to `await anyio.to_thread.run_sync(...)` around each blocking sub-call. Rejected because it touches every one of the 9 handlers' internals, breaks the ~15+ existing tests that call `mcp_app.trovex_write(...)` etc. synchronously, and still wouldn't bound fastembed's own construction (no timeout parameter exists there either) — the wait_for-at-the-boundary approach is strictly simpler and covers the same and more (any future blocking call inside a handler, not just the ones fixed today).

REJECTED_ALTERNATIVE: Adding a timeout only around the specific fastembed/rerank_local call site (e.g. running just `_get_encoder()` in a thread with a timeout). Rejected as too narrow — the same failure class applies to the OpenAI embedder's retry-with-`time.sleep` path and to `store._lock` contention; a single boundary-level fix covers all current and future blocking risks in one place instead of playing whack-a-mole per call site.

NOTE (AC5, indexer rollback): `indexer.py`'s `_rollback_on_error` decorator already wraps `reindex()`/`reindex_paths()` and does roll back cleanly on a `ModuleNotFoundError` (e.g. missing `tree_sitter_language_pack`) — the DB is left consistent, not stranded. It does NOT skip-and-continue past the failing file; the whole pass aborts and every file processed before the failure is lost for that run. Confirmed as safe (no partial/corrupt state) but not optimal; left as a documented follow-up, out of scope for this P1 (event-loop wedge), not touched here.

## review-backend verdict: SHIP

Ran `.claude/skills/review-backend` (trovex-backend lane) against this diff (src/trovex/mcp_app.py, tests/test_wedge_class2.py). Findings by section:

- §1 recall/retrieval, §2 write-side integrity, §3 reserved source id, §6 privacy defaults, §7 schema/embed-dim, §8 token-efficiency: not applicable — this diff touches only the tool-dispatch boundary (`_off_loop`), no retrieval/write/schema/output-shape logic changed.
- §4 auth/secrets: verified, not just assumed — empirically confirmed `contextvars` (incl. `current_write_token` read by `_authorized()`, and MCP's request-context contextvar read by `_pinned_source()`) propagate correctly into the `run_in_threadpool` worker thread (ad hoc repro: a contextvar set before the call reads back correctly inside the threadpool callee). Auth on `trovex_write`/`trovex_tag`/`trovex_delete` is unaffected.
- §5 best-effort vs genuine error: `_off_loop` catches ONLY `TimeoutError`; any real exception from the wrapped handler (ValueError, TopicCollisionError, etc.) propagates through `run_in_threadpool` unchanged — no swallowing of genuine errors. The timeout case is correctly typed via the existing CCAR `_err()` envelope, category="transient", isRetryable=True.
- §9 test discipline: new hermetic test (`tests/test_wedge_class2.py`, BagEmbedder, no network) proves (a) a stuck sync handler times out fast instead of hanging, (b) a concurrent `boot_pointers` call (the real /api/boot function) completes normally on the SAME event loop while the other call is stuck, (c) a fast call is unaffected, (d) the module-level tool name stays synchronously callable for existing direct/test callers.
- Cancellation semantics double-checked empirically (not just from docs, since `anyio.to_thread.run_sync`'s `abandon_on_cancel=False` default reads ambiguously): confirmed via a standalone repro that `asyncio.wait_for(run_in_threadpool(...), timeout=X)` returns at `X`, not at the real call's full duration — the orphaned thread keeps running in the background, exactly as documented in the code comment.

Full suite: 443 passed, ruff clean, at rebased HEAD.

No findings. SHIP.

## 3. Files changed

```
src/trovex/mcp_app.py      |  63 +++++++++++++++---
 tests/test_wedge_class2.py | 155 +++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 209 insertions(+), 9 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `5e80f318-191c-4754-aede-c16c3488e0ad`._
