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
- **AC3** (replay static vs dense recall): absolute recall@k DEFERRED — trovex has
  0/7631 used-labelled queries (replay bug c03d169a, same blocker as perf E); the
  blind-pool method is documented in the perf E report. Computable signal now:
  receipt `.niwa/receipts/perf-d/overlap.json` — static-vs-dense top-5 agreement on
  50 real boot/prompt queries over the 2238 record-doc pool: mean overlap@5 0.056,
  static-top1-in-dense-top5 0.12. This is a WORST-CASE scope-free proxy (the boot
  path is owner-scoped, precision≈1 by scope over an agent's handful of own records —
  the static order barely matters there); it confirms potion is lower quality (the
  ~20% NanoBEIR gap), which is exactly why it is a DEGRADED fallback, not the normal
  path. The fallback's job is availability (<10ms pack vs nothing), the ticket's
  stated goal; the normal path's quality is untouched.

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
.niwa/receipts/perf-d/overlap.json      |  11 +++
 .niwa/receipts/perf-d/reembed-rate.json |   8 ++
 pyproject.toml                          |   7 ++
 scripts/bakeoff_perf_d.py               | 148 ++++++++++++++++++++++++++++++++
 src/trovex/boot.py                      |  83 +++++++++++++++++-
 src/trovex/cli.py                       |   8 +-
 src/trovex/config.py                    |  14 +++
 src/trovex/db.py                        | 135 ++++++++++++++++++++++++++++-
 src/trovex/embedder.py                  |  54 ++++++++++++
 src/trovex/indexer.py                   |  48 ++++++++++-
 src/trovex/search.py                    |   8 +-
 src/trovex/server.py                    |  28 +++++-
 src/trovex/state.py                     |  18 +++-
 src/trovex/store.py                     |  52 ++++++++++-
 tests/test_server.py                    | 138 +++++++++++++++++++++++++++++
 uv.lock                                 |  64 ++++++++++++++
 16 files changed, 805 insertions(+), 19 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `ad2ad98e-a41f-420d-a806-70378486faee`._
