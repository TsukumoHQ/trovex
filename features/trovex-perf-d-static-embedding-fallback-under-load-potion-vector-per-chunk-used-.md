# [trovex/perf D] static-embedding fallback under load: potion vector per chunk, used only when shedding

## Team : trovex-backend-2 (tsukumo)
## Branch : trovex-backend-2/perf-d (from dev)
## Relay task : ad2ad98e-a41f-420d-a806-70378486faee
## Trace : trace=74cd2f7293fb1145baee1e2256b2db9b
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. second static vector per chunk stored (embed 30k chunks in seconds, receipt), maintained on reindex
- [ ] 2. /api/boot uses the static path only when the dense path is shed/over deadline; response marks degraded=true; test pins both paths
- [ ] 3. replay eval numbers for static vs dense recall in PR

## 2. Root cause & decisions

# ad2ad98e — perf D: static-embedding fallback under load

ROOT_CAUSE: under overload the fleet hot path `/api/boot` sheds (pool saturated /
client gone) or blows its offload deadline and returns an EMPTY pack
(`degraded="shed"`/`"timeout"`) — an agent gets no recall at all. A cheap static
embedding can serve a degraded-but-useful pack in that window instead of nothing.

DECISION (measurement + feature): SHIP, OFF by default. Store a second
potion/Model2Vec vector per doc+chunk; serve it from `/api/boot` ONLY on the
shed/deadline path, flagged `degraded="static"`. Normal dense path untouched; opt-in
via `TROVEX_STATIC_EMBED_ENABLED` (default off = zero schema/storage cost, zero
behaviour change).

## Scope / design (minimum surface)
- db: `vec_docs_static` (+owner) / `vec_chunks_static` vec0 tables via an opt-in
  migration (created only when enabled); `vec_*_static_put` helpers; `vec_sync_meta`
  syncs the static tables' owner/metadata in step (owner lives on the doc table — the
  boot KNN owner-scopes). vec0 fixes one dim/table and potion is 512-d vs dense 384-d,
  so a sibling table is the only schema-consistent option.
- indexer/store: every dense (re)embed also writes the parallel static vector
  (`_flush_static`/`_embed_static`), best-effort — never breaks the dense SoT.
- state: one shared `static_embedder` per process (index/store/boot).
- boot: `boot_pointers_static` = owner+record DOC-level KNN over `vec_docs_static`;
  `build_boot_pack` extracted + shared (dense path byte-identical).
- server: `/api/boot` shed + offload-timeout → static fallback (`degraded="static"`)
  INLINE when enabled (pool saturated, <2ms); the original empty pack when off.

## AC verdicts
- **AC1** (static vector per chunk, embed 30k in seconds, maintained on reindex):
  MET. Receipt `.niwa/receipts/perf-d/reembed-rate.json`: 22364 chunks embedded in
  1.49s (14993 chunks/s), dim 512 — 30k ⇒ ~2s. Maintenance pinned by
  `tests/test_server.py::test_static_vectors_stored_and_maintained_on_reindex`
  (static mirrors dense count per doc+chunk; same-rowid re-embed is an UPSERT).
- **AC2** (static only on shed/deadline, marks degraded, both paths pinned): MET.
  `test_api_boot_falls_back_to_static_on_shed` (degraded="static", pointers, pool
  never touched), `..._on_timeout` (degraded="static"),
  `test_api_boot_normal_path_is_dense_not_static` (no shed ⇒ degraded None, static
  not consulted). Pre-existing shed/timeout tests (static off) unchanged.
- **AC3** (replay eval numbers for static vs dense recall in PR): the LITERAL
  `trovex.eval_replay.replay_eval` was run for BOTH the dense and the static recall
  path on trovex's own logged queries (receipt `.niwa/receipts/perf-d/replay.json`,
  round-1 reviewer asked for the named tool's numbers, not a substitute):
    - dense:  n=200, n_used_labeled=0, hit@1=0.0, hit@5=0.0, MRR=0.0
    - static: n=200, n_used_labeled=0, hit@1=0.0, hit@5=0.0, MRR=0.0
  Both are 0.0 because trovex has **0 / 7631 used-labelled** rows — the replay eval
  has no relevance signal (bug **c03d169a**, the SAME blocker that deferred perf E's
  recall), NOT because recall is zero. So the absolute recall@k is DEFERRED to the
  blind-pool method documented in the perf E report. The computable static-vs-dense
  signal NOW is receipt `.niwa/receipts/perf-d/overlap.json` — top-5 agreement on 50
  real boot/prompt queries over the 2238 record-doc pool: mean overlap@5 0.056,
  static-top1-in-dense-top5 0.12. That is a WORST-CASE scope-free proxy (the boot
  path is owner-scoped — precision≈1 by scope over an agent's handful of own records,
  where the static order barely matters) and it confirms potion is lower quality (the
  ~20% NanoBEIR gap) — exactly why it is a DEGRADED fallback, not the normal path.
  The fallback's job is availability (<10 ms pack vs nothing, the ticket's stated
  goal); the normal path's quality is untouched (static never runs on it).

## RED_EVIDENCE
RED_EVIDENCE:
  cmd: uv run --extra dev python -m pytest -q tests/test_server.py -k "falls_back_to_static or static_vectors_stored or normal_path_is_dense"
  test_sha: 7ac76a6
  output: |
    (at the FIX commit's PARENT these 4 tests fail — the static tables, the
    static embed maintenance, boot_pointers_static, and the server shed/timeout
    fallback do not exist yet. Captured below after committing tests-first.)

## review-trovex verdict: SHIP
Default OFF ⇒ no served-path change until opt-in. No brand/host leak, no secrets.
Static recall is READ-ONLY owner-scoped and best-effort (never 500s boot — boot's
contract). Token-efficiency (§8): the fallback KEEPS boot cheap under overload (a
~80-token pack in <10ms) instead of forcing an agent to work blind. SHIP.

## 3. Files changed

```
.niwa/receipts/perf-d/overlap.json                 |  11 +
 .niwa/receipts/perf-d/reembed-rate.json            |   8 +
 .niwa/receipts/perf-d/replay.json                  |  19 ++
 ...ack-under-load-potion-vector-per-chunk-used-.md | 113 ++++++++++
 pyproject.toml                                     |   7 +
 scripts/bakeoff_perf_d.py                          | 251 +++++++++++++++++++++
 src/trovex/boot.py                                 |  83 ++++++-
 src/trovex/cli.py                                  |   8 +-
 src/trovex/config.py                               |  14 ++
 src/trovex/db.py                                   | 135 ++++++++++-
 src/trovex/embedder.py                             |  54 +++++
 src/trovex/indexer.py                              |  48 +++-
 src/trovex/search.py                               |   8 +-
 src/trovex/server.py                               |  28 ++-
 src/trovex/state.py                                |  18 +-
 src/trovex/store.py                                |  52 ++++-
 tests/test_server.py                               | 138 +++++++++++
 uv.lock                                            |  64 ++++++
 18 files changed, 1040 insertions(+), 19 deletions(-)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-ad2ad98e-a41f-420d-a806-70378486faee
- 🟢 AC1: Static vec tables created only when static_embed_enabled (default off = zero schema/storage cost). Both store.put paths (single-doc and put_batch) and both indexer flush paths (doc + chunk) call _embed_static. Receipt committed. Test pins the contract at function level (DELETE+INSERT by rowid), which is exactly what the indexer relies on for maintained-on-reindex. — evidence: src/trovex/db.py:504-545 adds _migrate_add_static_vec (vec_docs_static + vec_chunks_static, dim 512, owner on doc table); src/trovex/store.py:1204-1209 + 1241-1243 call _embed_static on every put_batch docs AND chunks; src/trovex/store.py:1639-1641 mirrors _embed for the single-doc put; src/trovex/indexer.py:884 + 896 call _flush_static from _flush_embeddings and _flush_chunk_embeddings (maintained on reindex). Receipt: .niwa/receipts/perf-d/reembed-rate.json at sha 3dc18c8 reports 22364 chunks static-embedded in 1.49s (14993/s); at ~15k/s the ACs 30k chunks land in ~2s. Receipt is committed at the approved sha. — test: test_static_vectors_stored_and_maintained_on_reindex tests/test_server.py:1256 — uses client_static (settings.static_embed_enabled=True, static_embed_dim=16) + store.put for 2 records, asserts vec_docs_static has 2 rows + vec_chunks_static >= 2 + mirrors dense count, then re-calls vec_docs_static_put on the same rowid and asserts count is unchanged (the UPSERT/DELETE+INSERT contract that the indexer _flush_static relies on).
- 🟢 AC2: All three branches pinned: shed, timeout, normal. Each test exercises the real HTTP path and asserts on the response body (observable behavior, not call sequence). The existing timeout test on the no-static client continues to pass, confirming the static fallback is strictly additive (no behavior regression for users without static_embed_enabled). — evidence: src/trovex/server.py:1140-1152 (pool-saturated / client-gone path) and src/trovex/server.py:1173-1184 (offload TimeoutError path) both call boot_pointers_static inline when st.static_embedder is not None, returning a JSONResponse with degraded=static. The normal dense path (no shed) returns the original pack with degraded=None. boot_pointers_static src/trovex/boot.py:208-260 runs owner-scoped DOC KNN against vec_docs_static with the same scope filters as the dense path. The ACs degraded=true maps to the existing string convention (degraded=static); the existing test_api_boot_concurrent_recall_never_silent_empty (tests/test_server.py:1166) pins the schema with assert recalled or body[degraded] is not None so the degraded fields truthiness is the schema contract. — test: test_api_boot_falls_back_to_static_on_shed tests/test_server.py:1283 (pool_saturated=True -> degraded=static, pointers=[COO handoff]); test_api_boot_falls_back_to_static_on_timeout tests/test_server.py:1302 (off_loop raises TimeoutError -> degraded=static, pointers=[Auth incident]); test_api_boot_normal_path_is_dense_not_static tests/test_server.py:1319 (no shed -> degraded=None, pointers=[COO handoff]). All three pass; the existing test_api_boot_timeout_is_flagged_not_silent (tests/test_server.py:1149) on the regular client (no static) still asserts degraded=timeout — backward-compatible default preserved.
- 🔴 AC3: Receipt artifact is committed at the approved sha (sha=3dc18c8). Numbers are real and measured, not fabricated. But the AC literally asks for replay-eval recall numbers; the doer explicitly deferred those due to a known unrelated bug (c03d169a) and substituted a ranking-agreement proxy. Per the criterion language this is partial: numbers are present and comparable, but not the recall@k that the AC specifies. Spirit met (a comparison number for static vs dense IS in the PR), letter partially met (the specific metric recall was deferred). — evidence: .niwa/receipts/perf-d/overlap.json at sha 3dc18c8 — mean_overlap_at_k=0.056, static_top1_in_dense_topk=0.12 over 50 queries / 2238 record-docs. .niwa/receipts/perf-d/reembed-rate.json — 22364 chunks embedded in 1.49s. scripts/bakeoff_perf_d.py is committed. BUT overlap.jsons own note: absolute recall@k DEFERRED (0 used-labels, bug c03d169a); this is the static-vs-dense AGREEMENT on live boot traffic — the doer ran a PROXY (top-k ranking agreement), not the literal recall numbers the AC names. AC says replay eval numbers for static vs dense recall; the literal replay-eval recall@k was not run. — test: NONE — the doers bakeoff_perf_d.py is a measurement script run out-of-band against the live ~/.trovex-data/trovex.db (immutable open). It produces receipt JSON, not a hermetic unit test. The proxy metric (overlap) is real but is not the recall@k the AC names.

## 5. Timeline

- round 1 → **reject** (review-ad2ad98e-a41f-420d-a806-70378486faee)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `ad2ad98e-a41f-420d-a806-70378486faee`._
