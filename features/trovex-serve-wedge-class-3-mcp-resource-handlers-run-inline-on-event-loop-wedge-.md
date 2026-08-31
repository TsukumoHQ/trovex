# [trovex/serve] Wedge class 3: MCP resource handlers run inline on event loop, wedge on orphaned writer lock

## Team : trovex-backend (tsukumo)
## Branch : fix/mcp-resource-offload (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

# Wedge class 3 — MCP resource handlers off-loaded (task 8640b88b)

## Root cause
Live prod sample (2026-08-31 15:47-48Z, pid wedged 407%+ CPU): main event-loop
thread stuck in `sqliteDefaultBusyCallback -> unixSleep`. An orphaned writer
held the WAL lock; the 6 `@mcp.resource` handlers in `mcp_app.py`
(savings/deleted/catalog, all `db.execute` inline) were the one call class
33ca98a (tools) and eda6f60e (FastAPI routes) never touched — same wedge
class as f2b4c872, different call site.

## Fix
`mcp_app._off_loop_resource` — resource analogue of the existing `_off_loop`
(tools): registers an async twin that runs the handler through
`offload.off_loop` (bounded pool + `TOOL_TIMEOUT_SEC` wall-clock budget).
Confirmed via SDK source (`mcp/server/fastmcp/resources/types.py` +
`templates.py`) that `FunctionResource.read` and
`ResourceTemplate.create_resource` both already special-case an async `fn`
(`inspect.iscoroutine` check before await) — no SDK-internals workaround
needed, for concrete resources or `{param}` templates.

Unlike `_off_loop`, a timeout degrades to a plain markdown apology string,
not the tool-only CCAR `_err()` JSON shape — matches `/api/boot`'s
degrade-to-empty-pack precedent (server.py). Module-level names stay bound
to the original sync functions (direct/test callers unaffected).

All 6 handlers wrapped: `savings_receipt`, `savings_for_session`,
`deleted_docs`, `catalog_sources`, `catalog_index`, `catalog_for_source`.

## review-backend verdict: SHIP

## Verification
- New `tests/test_wedge_class3_resources.py`: synthetic stuck concrete +
  templated resource (mechanism), a real handler (`catalog_sources`) with
  its `db` swapped for a proxy that sleeps past `TOOL_TIMEOUT_SEC` on
  `.execute` (simulating an orphaned WAL writer), fast-path unaffected,
  module-level sync name preserved.
- `uv run pytest -q`: 463 passed.
- `uv run ruff check .`: clean.
- Self-review (review-backend skill, worktree-scoped): no findings — read-only
  change, only catches `TimeoutError` (matches `/api/boot` precedent), no
  auth/schema/recall-path touched.

## Follow-ups retired
- Memory `trovex-serve-resources-sync-followup` retired (was WRONG: called
  this "non-blocking, DB-only" — it isn't, busy_timeout=30000 blocks the loop
  same as any other inline sync call).

## Scope explicitly NOT in this task (per cto-tsukumo GO, 4 riders)
- Write-path latency (>30s trovex_write, 400% CPU) stays separate P2.
- Re-proof = new 1h stability-window clock post-deploy; watchdog stays until
  clean.

## 3. Files changed

```
src/trovex/mcp_app.py                |  45 ++++++--
 tests/test_wedge_class3_resources.py | 196 +++++++++++++++++++++++++++++++++++
 2 files changed, 235 insertions(+), 6 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `8640b88b-1b21-4321-a378-e81abc0213d8`._
