# [trovex/capacity] partition 'trovex' is at 228% of the vec0 KNN ceiling (9359 chunks vs k=4096, 'wraith' at 82%): measure what a scoped chunk KNN actually returns today, then either build the usearch escape hatch capacity.py promises or shard the partition

## Team : trovex-backend (tsukumo)
## Branch : feat/vec0-capacity-escape (from dev)
## Relay task : 4c89b89a-59dc-4429-b597-6af110b757e5
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. task result states, with the exact query, whether scoped chunk KNN on a partition above 4096 chunks loses candidates today
- [ ] 2. if capped: usearch escape hatch per capacity.py with a pinned equivalence test (top-10 overlap >= 0.9 vs brute force on a 5k-chunk fixture) and a pinned test that a flagged partition serves from HNSW while others stay on sqlite-vec; if not capped: capacity warning corrected and rate-limited, pinned test
- [ ] 3. /api/status carries per-partition docs, chunks and ceiling ratio; pinned test
- [ ] 4. make test green; PR carries the review-trovex verdict; submitted through the gate against dev

## 2. Root cause & decisions

ROOT_CAUSE: `store.search_chunks` and `search.py::_vector_rows` both set the vec0 KNN `k` to exactly `VEC0_MAX_K` (4096) whenever a `tags` filter is given, on the theory (stated in both docstrings) that "tags aren't a vec0 column, so a tag-scoped query scans the whole (bounded) partition." That theory silently breaks once a partition's vector count exceeds 4096: sqlite-vec's `k=?` is a HARD ceiling — a query for `k > 4096` raises `k value in knn query too large`, it does not clamp — so `k=4096` is NOT "the whole partition" once the partition is bigger than that; it is the 4096 nearest neighbours BY RAW VECTOR DISTANCE, full stop. Anything ranked past position 4096 is dropped before the tag filter even runs, no matter how well its tag matches.

**Measured on a copy of the real prod store** (`~/.trovex-data/trovex.db`, copied to a scratch dir, never touched live): partition `'trovex'` has 9969 `vec_chunks` rows (2.4x the ceiling). Repro (exact code, `store.search_chunks`'s own vsql, executed via the project's own `SqliteStore`/`embed_query_blob`):
```python
vsql = ("SELECT v.rowid FROM vec_chunks v WHERE v.embedding MATCH ? AND k = ? "
        "AND v.source_id = 'trovex' AND v.lifecycle != 'archived' "
        "AND v.lifecycle != 'pending_delete' AND v.status != 'duplicate' ORDER BY v.distance")
k4096 = {r["rowid"] for r in db.execute(vsql, [qblob, 4096])}
tagged_ids = {c.id for c,d,t in join(chunks,docs,doc_tags) if d.source_id=='trovex' and t.tag=='owner/trovex-backend'}  # 194 total
```
For a boot-style query ("current state resume open work in flight next steps gotchas"): **only 42/194 (22%) of one agent's own owner-tagged chunks land inside the top-4096** — the other 152 (78%) are UNREACHABLE by `search_chunks(tags=[...])` for that query, at any `--limit`, today, in production. Two more sampled queries: 166/194 and 35/194 reachable. This is real, live, silent recall loss on the fleet's Active-Memory boot path (`/api/boot` is exactly this call shape) — not a theoretical risk.

Doc-level KNN (`_vector_rows`, same `k=4096-if-tags` pattern) is NOT currently truncating in practice — `vec_docs` for 'trovex' is 1174 rows, under the ceiling — but carries the identical latent bug once it crosses 4096 too.

DECISION: build the usearch (HNSW) escape hatch capacity.py already documents (config field `Settings.usearch_partitions` / env `TROVEX_USEARCH_PARTITIONS` already existed, scaffolded but never wired — this task wires it):
1. `usearch_index.py` (new): `PartitionIndex` wraps a `usearch.index.Index(metric="cos")` — same cosine-distance sense as the `vec0` tables (`distance_metric=cosine`), so distances from either source are directly comparable. `rebuild_partition(db, table, source_id, dim)` reads `rowid, embedding` straight off `vec_docs`/`vec_chunks` (two literal per-table queries, not an f-string table name — keeps `scripts/security_guard.py`'s RULE 3 happy, same pattern `capacity.partition_counts` already uses) and replaces the whole index — no incremental delete/update bookkeeping. A process-wide registry (`get_index`/`_indexes`) keyed `"{table}:{source_id}"`.
2. `store.search_chunks` / `search.py::_vector_rows`: for a `source_id` in `settings.usearch_partitions`, route through `usearch_index.get_index(...)` when built (`eff_k = len(index) if tags else k` — a genuine full-partition scan, no ceiling), falling back to the unchanged sqlite-vec path whenever the index isn't built yet (dep absent, or no rebuild has run) — never a hard failure. `_vector_rows`'s usearch branch can't reuse the vec0 SQL as-is (vec0 only populates `v.distance` inside a MATCH KNN, not a plain `rowid IN (...)` lookup) — it re-selects metadata off `docs` (the lifecycle/kind/status source of truth) and attaches the distance usearch already computed, in Python.
3. Rebuilt after every index run for a flagged partition (`Indexer._rebuild_usearch_indexes`, called at the end of both `reindex()` and `reindex_paths()` — the incremental fs-watch/index_jobs path, not just the full one) AND once at server startup (`lifespan`, before the applier starts) so a request landing right after boot never sees an empty index.
4. `capacity.capacity_report`/`log_capacity_warnings` take `usearch_partitions` and skip the chunk-ceiling warning for a covered partition — that specific risk is what the index resolves; the separate brute-force-soft-limit (doc count) warning is untouched, usearch doesn't change that scale.
5. `/api/stats` (the actual status/stats endpoint — the ticket said `/api/status`; there is no route by that name, `/api/stats` is the one server.py already exposes for this) now carries a `capacity` array: `{source_id, docs, chunks, ceiling_ratio, usearch}` per partition.

Equivalence: usearch top-10 overlap vs true sqlite-vec brute force on the REAL prod-copy data was **10/10 on every one of 4 sampled queries** (see task result). The pinned hermetic test (`tests/test_usearch_index.py`, 5000-chunk synthetic fixture, clustered — not iid-noise — vectors, matching real embedding-space structure) holds the task's own >= 0.9 bar with margin.

REJECTED ALTERNATIVES:
- "if not capped, correct + rate-limit the warning": moot — SCOPE (1) proved recall IS capped, with real numbers, so the ticket's other branch applies.
- Sharding the partition into multiple smaller source_ids instead of usearch: rejected — 'trovex' is the SSOT for Active-Memory records across the whole fleet; splitting it would break the "one owned partition" invariant every other subsystem (boot, capture, dedup) assumes, for a problem the drop-in HNSW adapter already solves without touching that invariant.
- Making usearch a hard (non-optional) dependency: rejected — capacity.py's own stated design goal is "offline-first ... zero new deps" by default; an optional extra + graceful no-op fallback preserves that for every install that never crosses the threshold.
- Pushing metadata (kind/lifecycle) filtering INTO usearch: rejected — usearch has no such concept, and the existing post-filter in `search_chunks`'s `out` loop / `_vector_rows`'s tail already re-checks lifecycle/kind/status/tags/source on every candidate regardless of which KNN source found it, so it's free correctness, not new work.

No [LEGACY_OPPORTUNITY] beyond what's in scope.

## review-trovex verdict: SHIP

review-trovex: ✅ ship — 7 files touched (5 src + 2 new test files + pyproject/uv.lock for the optional usearch dep) — gate green (ruff clean, 756 pytest, was 746, +10 new, 0 regressions). AC1: real repro + numbers against a prod-store copy in the task result and above. AC2: usearch escape hatch built exactly to capacity.py's spec, equivalence test clears the 0.9 bar (10/10 on real data), pinned routing test (flagged partition serves from HNSW, unflagged stays on sqlite-vec), rebuild-after-reindex pinned for BOTH reindex()/reindex_paths(), startup-build pinned. AC3: /api/stats carries per-partition capacity, pinned. AC4: gate green, this doc. No secret/brand/host leak (grepped the diff). No schema/migration, no prod deploy, no release tag. Touches server.py (lifespan, /api/stats) and pyproject.toml (new optional dep) — cross-lane enough (shared surfaces, a new runtime extra) that this goes to cto for a PR review rather than self-merge, even though the gate is green.

## 3. Files changed

```
pyproject.toml                |   9 ++
 src/trovex/capacity.py        |  17 ++-
 src/trovex/indexer.py         |  23 ++-
 src/trovex/search.py          |  58 +++++++-
 src/trovex/server.py          |  35 ++++-
 src/trovex/store.py           |  18 ++-
 src/trovex/usearch_index.py   | 135 ++++++++++++++++++
 tests/test_capacity_status.py | 130 +++++++++++++++++
 tests/test_usearch_index.py   | 321 ++++++++++++++++++++++++++++++++++++++++++
 uv.lock                       | 151 +++++++++++++++++++-
 10 files changed, 883 insertions(+), 14 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `4c89b89a-59dc-4429-b597-6af110b757e5`._
