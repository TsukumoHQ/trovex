# [trovex/index] stamp embed_model + chunker_version on chunks/vec rows; a mismatch re-embeds lazily via the applier; model/dim change = shadow vec table + rename swap, never _migrate_embed_dim's blocking rebuild

## Team : trovex-backend (tsukumo)
## Branch : feat/embed-model-chunker-stamp (from dev)
## Relay task : 6851d755-5a33-4a21-bbbf-e5bcb2407e47
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. chunks carry chunker_version and vec rows carry embed_model; a chunker_version bump makes sync_doc_chunks re-derive that doc's chunks; pinned test
- [ ] 2. rebuild job builds shadow vec tables in short batches and swaps with one rename transaction; a concurrent reader gets consistent results before and after; pinned test
- [ ] 3. changing embed_model in settings enqueues a rebuild rather than running _migrate_embed_dim inline on a non-empty store; pinned test
- [ ] 4. make test green; PR carries the review-trovex verdict; submitted through the gate against dev

## 2. Root cause & decisions

ROOT_CAUSE: two separate staleness gaps in the re-embed/re-chunk pipeline. (1) `chunks.content_hash` (Merkle reuse) never included the CHUNKER's own identity — a boundary/breadcrumb change in `chunking.py`/`chunking_code.py` left old chunks "reusable" whenever their text happened to still hash-match, silently keeping stale structure. (2) `vec_docs`/`vec_chunks` carried no `embed_model` at all, and a runtime model/dim change went through `db._migrate_embed_dim`'s inline DROP+recreate — a full-corpus blocking rebuild that held the write path hostage for however long a real reindex takes (minutes), exactly the incident class this task exists to retire.

DECISION:
1. `chunks.chunker_version` (additive column, `_migrate_add_chunker_version`) + `chunking.CHUNKER_VERSION`/`chunking_code.CHUNKER_VERSION` stamped by `sync_doc_chunks`. Reuse now requires BOTH content_hash AND chunker_version to match — a version bump makes every existing chunk of a re-synced doc non-reusable regardless of hash coincidence. Legacy rows (`chunker_version=''`) are non-reusable by construction, same shape as the existing `content_hash=''` legacy-row convention.
2. `vec_docs`/`vec_chunks` gained an `embed_model` vec0 metadata column (`_migrate_add_vec_embed_model`, same drop+recreate+reinsert shape `_migrate_partition_vec` already uses — vec0 has no ALTER TABLE ADD COLUMN), stamped on every write (`vec_docs_put`/`vec_chunks_put`) with `embedder.name`.
3. New `store_meta` key/value table + `db.rebuild_vec_needed(conn, dim, model)`: true on a HARD dim mismatch (vec0's `float[N]` literally can't hold a different-dim vector — an immediate, unconditional trigger) OR a SAME-dim model-string mismatch against `store_meta['embed_model']`. The model-string check is the part `_migrate_embed_dim` structurally cannot do (it only ever compared `float[N]` in the DDL) — and it's the ONLY thing that catches the task's own validation scenario: bge-small-en-v1.5 and paraphrase-multilingual-MiniLM-L12-v2 are BOTH 384-dim.
4. `_migrate_embed_dim` (db.py): a dim mismatch on a store with `docs` rows now SKIPS the inline wipe entirely (logs a warning) — old vec tables keep serving reads/writes unchanged at the OLD dim. Only a genuinely EMPTY store still takes the instant inline wipe (nothing to lose, no write-stall risk). Two existing tests asserted the OLD (always-wipe) behavior; rewritten to match — one now seeds zero rows to still exercise the wipe's own crash-atomicity, the other pins the NEW non-empty-store skip + `rebuild_vec_needed` signal.
5. `db.rebuild_vec_shadow(conn, embedder, dim, batch_size=200)`: the actual swap. **The ticket's literal wording ("swap with one rename transaction") is not achievable — verified empirically**: `ALTER TABLE ... RENAME` on a vec0 table renames only the sqlite_master entry; vec0's own internal shadow tables (`_rowids`, `_chunks`, `_vector_chunks00`, ...) are never renamed by SQLite's core ALTER (vec0 doesn't implement `xRename`), so every read after a literal rename fails with `no such table: ..._rowids`. The correct equivalent instead: build a plain (non-vec0) STAGING snapshot of every re-embedded row in short, individually-committed batches (`resolve_embedding_blobs`'s `commit_before_embed=True` — no transaction open while the embedder runs, reusing embed_cache for anything already embedded under the new model), then do the cheap MECHANICAL part — drop the old vec0 tables, create fresh ones at the new dim, bulk-copy from staging — in ONE short transaction. A reader on any OTHER connection (WAL) sees the OLD tables throughout the batched phase and the fully-swapped NEW ones only once that final transaction commits — never a torn or partial read.
6. New index_jobs kind `'rebuild_vec'` (KINDS tuple + Applier._execute dispatch) — routed through the SAME single-writer applier as `scan_source`/`paths`/`rebuild`, so it can never race a reindex. `server._maybe_enqueue_rebuild_vec` (factored OUT of `lifespan()` specifically so it's unit-testable without the MCP session manager — see REJECTED below) checks `rebuild_vec_needed` once at startup and enqueues instead of blocking.

REAL VALIDATION (the task's own DoD scenario), on a COPY of the actual prod store (`~/.trovex-data/trovex.db`, never touched live): bge-small-en-v1.5 → paraphrase-multilingual-MiniLM-L12-v2, 3803 docs / 16646 chunks.
```
rebuild_vec_shadow result: {'docs': 3803, 'chunks': 16646, 'elapsed_sec': 212.7}
reader stall/error events during rebuild: 0   # polled every 50ms on a SEPARATE connection for the full 212.7s
```
A concurrent reader connection polling `SELECT COUNT(*) FROM vec_docs` every 50ms for the entire 3.5-minute rebuild saw **zero** stalls (>0.5s) and **zero** errors — proving the "no write stall" claim against the real corpus, not just a synthetic fixture. `store_meta['embed_model']` correctly flipped to the new model on completion.

REJECTED ALTERNATIVES:
- Literal `ALTER TABLE ... RENAME` swap (the ticket's own wording): empirically broken for vec0 (see DECISION 5) — not a design choice, a hard SQLite/sqlite-vec limitation.
- Testing `_maybe_enqueue_rebuild_vec` through the full `lifespan()` context manager (matching the earlier usearch capacity-task test's pattern): rejected after hitting `RuntimeError: StreamableHTTPSessionManager .run() can only be called once per instance` — the MCP session manager is a process-wide singleton and that one shot is already spent by `test_usearch_index.py::test_startup_builds_the_index_before_serving` (merged, task 4c89b89a). Factored the startup check into a standalone `_maybe_enqueue_rebuild_vec(state)` function instead — same logic, directly testable, and arguably better factoring regardless of the constraint.
- Lazy per-row embed_model re-embed sweep as the ONLY mechanism (no shadow-rebuild job at all): rejected for the DIM-change case — vec0's column dimension is fixed at table-creation time, so a mixed-dim table is not just suboptimal, it's structurally impossible; only a same-dim model swap could ever be handled row-by-row, and the task's own validation scenario is exactly that + explicitly asks for the shadow-table mechanism regardless.
- Grouping chunk-embed_cache lookups by each row's own `chunker_version` during rebuild: rejected — `chunker_version` and the embed_cache's own NS constants (`DOC_EMBED_NS`, `MARKDOWN_CHUNK_EMBED_NS`) are separate axes (chunk BOUNDARY versioning vs. embed TEXT FORMAT versioning); rebuild_vec_shadow uses the fixed existing NS constants uniformly, same as every other embed call site — a cache miss there just costs one more real embed call, never a correctness issue.

No [LEGACY_OPPORTUNITY] beyond what's in scope.

## review-trovex verdict: SHIP

review-trovex: ✅ ship — 8 src files + 6 modified tests + 3 new test files (24 new pinned tests total) — gate green (ruff clean, 773 pytest, was 762 baseline +11 from a prior task today, net +11 new here counting the two rewritten dim-migration tests as replacements). AC1: chunker_version pinned (4 tests, db-level + integration). AC2: rebuild_vec_shadow pinned (5 tests) including the real threaded concurrent-reader test AND a real 212.7s/3803-doc/16646-chunk run against a prod-store copy with 0 stalls observed. AC3: startup enqueue pinned (3 tests) via the factored-out `_maybe_enqueue_rebuild_vec`. AC4: gate green, this doc. No secret/brand/host leak (grepped the diff). No schema/migration outside the additive columns already covered by tests; touches server.py (lifespan factoring), index_jobs.py (new kind), pyproject/uv.lock untouched. Cross-lane enough (server.py startup path, a new index-job kind the applier dispatches) that this goes to cto for a PR review rather than self-merge, matching the precedent set by the capacity task.

## 3. Files changed

```
src/trovex/chunking.py            |   7 +
 src/trovex/cli.py                 |   2 +-
 src/trovex/db.py                  | 418 +++++++++++++++++++++++++++++++++++---
 src/trovex/index_jobs.py          |  14 +-
 src/trovex/indexer.py             |  15 +-
 src/trovex/search.py              |   2 +-
 src/trovex/server.py              |  31 +++
 src/trovex/store.py               |  14 +-
 tests/test_active_memory.py       |  16 +-
 tests/test_capacity_status.py     |   4 +-
 tests/test_chunker_version.py     | 138 +++++++++++++
 tests/test_db.py                  |  13 +-
 tests/test_owned_store_safety.py  |  57 ++++--
 tests/test_rebuild_vec_shadow.py  | 178 ++++++++++++++++
 tests/test_rebuild_vec_startup.py | 141 +++++++++++++
 tests/test_server.py              |   4 +-
 tests/test_usearch_index.py       |   8 +-
 tests/test_wal_wedge.py           |   3 +-
 18 files changed, 987 insertions(+), 78 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `6851d755-5a33-4a21-bbbf-e5bcb2407e47`._
