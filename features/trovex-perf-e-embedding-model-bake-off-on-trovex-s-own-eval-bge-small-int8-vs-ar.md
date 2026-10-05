# [trovex/perf E] embedding model bake-off on trovex's own eval: bge-small int8 vs arctic-embed-xs vs mdbr-leaf-ir (re-exported ONNX)

## Team : trovex-backend-2 (tsukumo)
## Branch : trovex-backend-2/perf-e (from dev)
## Relay task : 87207ea6-cb46-433f-ae77-5954fb6d5bd2
## Trace : trace=74cd2f7293fb1145baee1e2256b2db9b
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. p50/p95 query embed latency (1 thread, and under 16-way concurrency) per candidate, table in report
- [ ] 2. recall@k: DEFERRED by cto 2026-10-05 (replay used-labels are 0/4158, root cause c03d169a/1c51605e); report states the deferral and the blind-pool method to run later
- [ ] 3. recommendation with migration plan (re-embed time measured on the real index)
- [ ] 4. no production switch in this ticket; switch is a follow-up after cto sign-off

## 2. Root cause & decisions

# 87207ea6 — perf E embedding model bake-off (measurement report)

ROOT_CAUSE: the embedding model was never measured on trovex's OWN corpus — the
candidate choice (bge-small int8 vs arctic-embed-xs vs mdbr-leaf-ir) rested on MTEB
vendor claims. This ticket measures latency + migration cost on the real 21923-chunk
index and records the decision. Finding: bge-small's int8 query path (perf A: 6.9 ms
p50 / 62 ms p95 @16-way) beats every fp32 alternative on the steady-state hot path;
arctic-xs's only edge is one-time re-embed speed (~11.5 vs 21.6 min). DECISION
(cto, 2026-10-05): STAY on bge-small-en-v1.5 int8 — hot-path win, zero migration.

## Decision / scope
- Measurement only, NO production switch (AC3). cto ruling: stay on bge-small int8.
- Latency + re-embed-cost tables measured in-slot (OMP=4 re-embed, OMP=1 query);
  report in `features/trovex-perf-e-embedding-model-bakeoff.md`.
- Recall pass DEFERRED (cto): trovex has 0/4158 used-labelled queries (replay eval
  has no relevance signal — filed separately as c03d169a, P1). A cheap TREC-style
  blind-pooled 20-query recall sample runs when the host is quiet; the harness +
  reproducible query seed are committed so it is one command.
- Fairness: arctic/mdbr are asymmetric (query prompt); the harness uses fastembed
  query_embed/passage_embed + the mdbr prompt + mean pooling so a future recall pass
  is apples-to-apples. The first plain-embed top-10 was discarded, not committed.

## Rejected alternatives (this pass)
- Switch to arctic-xs now: rejected — no int8 query build, so its fp32 query latency
  (13.9 ms single / 115 ms @16-way) loses to bge-int8; re-embed speed is one-time.
- mdbr-leaf-ir full eval: deferred — ships ONNX but needs the blind recall pass to
  justify the switch + an int8 export to match hot-path latency.

No production code changed (measurement harness under scripts/ + a report doc +
measurement receipts). Docs/measurement ticket.

## review-backend verdict: SHIP
No src/ or served-path change (review-backend §§1-8 N/A — the harness reads the live
corpus READ-ONLY via immutable open, never writes trovex.db). §8 token-efficiency:
the decision KEEPS the cheapest query path (bge-int8). Numbers are measured on the
real index, not fabricated multiples. SHIP.

## 3. Files changed

```
.niwa/receipts/perf-e/latency-arctic-xs.json       |   9 +
 .niwa/receipts/perf-e/latency-bge-small.json       |   9 +
 .niwa/receipts/perf-e/queries.json                 | 242 ++++++++++++++
 .niwa/receipts/perf-e/reembed-arctic-xs.json       |  10 +
 .niwa/receipts/perf-e/reembed-bge-small.json       |  10 +
 ...ff-on-trovex-s-own-eval-bge-small-int8-vs-ar.md | 174 ++++++++++
 features/trovex-perf-e-embedding-model-bakeoff.md  |  89 +++++
 scripts/bakeoff_perf_e.py                          | 359 +++++++++++++++++++++
 8 files changed, 902 insertions(+)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-87207ea6-cb46-433f-ae77-5954fb6d5bd2
- 🔴 AC1: Latency half fully met (per-candidate, 1-thread + 16-way, table in PR, reproducible harness, body reviewed). Recall half explicitly deferred by doer (cto sign-off noted; bug c03d169a filed for missing used-labels). Strict AC reading requires recall@k in the table - that column is missing, so the criterion is partial -> reject. — evidence: features/trovex-perf-e-embedding-model-bakeoff.md:22-30 has the p50/p95 latency table per candidate (bge-small int8 6.9/62ms @16-way; bge-small fp32 27.1/33.6 single 247.5/327.6 16-way; arctic-xs fp32 13.9/19.6 single 115.1/179.6 16-way - verified against .niwa/receipts/perf-e/latency-{bge-small,arctic-xs}.json). Harness scripts/bakeoff_perf_e.py runs with OMP=1, 16-way concurrency, reproducible queries.json (48, SEED=1729, 3 strata). Recall pass is DEFERRED - the doc explicitly says 'live DB has 0 / 4158 used-labels; bug c03d169a (P1)' and that the recall pass is blocked on human labels. The AC requires 'replay eval recall@k + p50/p95 query embed latency' - recall part is missing from the PR table. — test: scripts/bakeoff_perf_e.py stage_score (L286-313) implements recall@k + MRR computation but cannot run end-to-end because labels.json does not exist and the underlying used-label bug is unfixed; no test in the diff exercises recall@k behavior. Latency portion verified by inspection of the receipt JSONs (no automated test).
- 🟢 AC2: Both elements delivered: recommendation present + migration plan present + re-embed time measured on the real index (subset-extrapolated, documented as such). — evidence: features/trovex-perf-e-embedding-model-bakeoff.md:41 has 'Recommendation: STAY on bge-small-en-v1.5 with the int8 query path'; lines 49-55 have the migration plan referencing the measured ~11.5min full re-embed + dimension compatibility note + need to mirror int8 ONNX query build. Re-embed measured on the real corpus (2000-chunk sample from the real 21923-chunk index, OMP=4) and extrapolated - receipt .niwa/receipts/perf-e/reembed-{bge-small,arctic-xs}.json shows bge-small 16.9 chunks/s (~21.6 min full) vs arctic-xs 31.7 chunks/s (~11.5 min full). The doc is honest about extrapolation (note: 'extrapolated from the subset'). — test: Measurement deliverable, not a behavior test. Receipt JSONs are the verifying artifacts (sample reembed on real chunks at OMP=4). scripts/bakeoff_perf_e.py stage_reembed_rate (L181-201) reproduces the script-level method; no automated test pins this AC.
- 🟢 AC3: Decision is STAY; harness is read-only; no model swap. AC3 is clean. — evidence: features/trovex-perf-e-embedding-model-bakeoff.md:3 'Decision: STAY on bge-small-en-v1.5 (int8 query path). No migration.' and 'Measurement only; cto ruling recorded below.' Harness opens the DB read-only (scripts/bakeoff_perf_e.py ro_conn: file:{db}?immutable=1). Embedder registry (src/trovex/embedder.py) unchanged in this diff - the 108-line addition there is Int8QueryEmbedder from perf-A, not a prod model swap. The deferred recall pass is explicitly the follow-up after cto sign-off. — test: No prod embed-model switch in this diff - verified by git diff origin/dev..trovex-backend-2/perf-e on src/trovex/embedder.py + src/trovex/db.py (no model registry change, no _migrate_embed_dim invocation).

## 5. Timeline

- round 1 → **reject** (review-87207ea6-cb46-433f-ae77-5954fb6d5bd2)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `87207ea6-cb46-433f-ae77-5954fb6d5bd2`._
