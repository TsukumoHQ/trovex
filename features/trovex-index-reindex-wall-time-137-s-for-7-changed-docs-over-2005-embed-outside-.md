# [trovex/index] reindex wall time: 137 s for 7 changed docs over 2005 — embed outside the sqlite transaction, content-hash embedding cache, profile the scan

## Team : trovex-backend (tsukumo)
## Branch : fix/reindex-embed-outside-txn-cache (from dev)
## Relay task : cbb8e8fb-98e5-444f-85bc-b599154e159f
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. index_runs rows carry per-phase timings (scan, chunk, embed, write) and cache hit/miss counts; pinned test on the row shape
- [ ] 2. embedding runs with no sqlite transaction open; pinned test with a fake embedder asserting not in_transaction
- [ ] 3. embed_cache keyed by (content_hash, embed_model, chunker_version): identical content re-indexed hits the cache, changed content misses; pinned tests
- [ ] 4. unchanged-corpus reindex on a 2000-doc fixture completes under 5 s wall; pinned benchmark test with the fixture
- [ ] 5. make test green; PR carries the review-trovex verdict; submitted through the gate against dev

## 2. Root cause & decisions

TASK: cbb8e8fb — reindex wall time 137s for 7 changed docs over 2005, fast-follow to 67ebd68c

ROOT_CAUSE: 67ebd68c fixed the lock-contention goal (0 "database is locked" since deploy) but not wall time. Code inspection of indexer.py confirmed the research's hypothesis: `_flush_embeddings`/`_flush_chunk_embeddings` called `self.embedder.embed(texts)` (the ONNX model, CPU-bound, seconds-to-minutes under load) while the sqlite transaction opened by the preceding doc-row INSERT/UPDATE in `_upsert_doc` was still uncommitted — so the WAL writer slot stayed held by the indexer's connection for the whole model call, not just the cheap row write. There was also no embed cache, so identical/renamed content always re-embedded. Separately (NOT fixed in this ticket, see below): status.py's compute_status Pass 1 re-reads every non-superseded doc's file content (twice: once for the plan check, once for the frontmatter-stale check) on EVERY reindex regardless of whether that doc changed — at 2005 docs this is ~4000 file opens every run, independent of docs_changed. This is very likely the actual dominant cost behind the observed 137s (6-7 changed docs is far too few to explain 137s of embedding alone), but restructuring compute_status's reset-then-recompute design is a bigger, riskier change (SSOT canonical_topic collision handling, duplicate detection ordering — "order matters" per its own docstring) than this ticket's prescribed scope, and deserves its own reviewed ticket rather than a scope-creep fix bundled here.

DECISION: Implemented the prescribed scope exactly: (1) index_runs.phase_ms (json: scan/chunk/embed/write/status, computed as wall_ms minus the four measured phases as a residual) + embed_cache_hits/embed_cache_misses, via an additive migration extending the same _migrate_add_index_run_metrics from 67ebd68c; (2) `_embed_texts_cached` now commits any pending row writes before calling embedder.embed(), verified by a pinned test (TxnCheckingEmbedder asserting `not db.in_transaction` at call time); (3) embed_cache keyed by (sha256 of the exact embedded text, embed_model, chunker_version) — NOT docs.content_hash, which excludes the title prefix `_embed_text` adds and would cache-hit wrongly across a retitle. Deduplicates WITHIN a single flush batch too (two docs with byte-identical text in the same batch share one embed() call, not just cache-vs-persisted-table).

REJECTED_ALTERNATIVES: Restructuring compute_status to skip the file-read checks for docs proven unchanged this run (via content_hash match) was considered as part of this ticket, since it's the strongest actual root-cause candidate for the 137s. Rejected for THIS PR: the reset-then-recompute design (docs.status is blanket-reset to 'canonical' at the top of every run, by comment "clears stale flags from prior runs") means the file-read checks aren't obviously separable from the reset without risking the canonical_topic collision handling that already caused a live IntegrityError once (2026-08-22, noted in status.py). Flagging as a fast-follow instead of bundling an under-reviewed architecture change into a perf ticket.

[LEGACY_OPPORTUNITY]: compute_status Pass 1 (status.py:97-150) does 2 file reads per doc, every run, over the WHOLE corpus, uncorrelated with docs_changed — the reindex() caller already knows exactly which doc ids changed this run (added+updated ids) and unchanged docs' plan/stale-frontmatter classification can't have changed either (their content didn't); only the age-based staleness check is genuinely time-dependent and needs re-evaluation for every doc, but that's a cheap SQL comparison, not a file read. A follow-up could pass the changed-doc-id set into compute_status and skip the file-read checks for everything else, cutting Pass 1's cost from O(corpus) to O(changed) while keeping the age check O(corpus) but cheap. Not done here — separate ticket, needs its own review given the SSOT ordering constraints already documented in status.py.

## review-trovex verdict: SHIP
review-trovex: ✅ ship — 5 files, +418/-20 — gate green (ruff+pytest, 483 passed), no schema-breaking rename, no secret/brand leak. embed_cache table + no-txn-during-embed + phase_ms/cache-count columns on index_runs, all additive.

## 3. Files changed

```
src/trovex/chunking_code.py       |   6 ++
 src/trovex/db.py                  |  65 ++++++++++++-
 src/trovex/indexer.py             | 141 +++++++++++++++++++++++++---
 tests/test_incremental_reindex.py |  34 ++++++-
 tests/test_reindex_embed_perf.py  | 192 ++++++++++++++++++++++++++++++++++++++
 5 files changed, 418 insertions(+), 20 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `cbb8e8fb-98e5-444f-85bc-b599154e159f`._
