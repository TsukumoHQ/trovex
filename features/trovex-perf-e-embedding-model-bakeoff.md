# perf E — embedding model bake-off (87207ea6)

**Decision: STAY on bge-small-en-v1.5 (int8 query path). No migration.**
_Measurement only; cto ruling recorded below. Recall pass deferred (see end)._

## Question
Pick the document+query embedding model for trovex by MEASURED latency, migration
cost, and recall on trovex's OWN corpus (not MTEB). Candidates: current
`BAAI/bge-small-en-v1.5` (int8 query, perf A) vs `snowflake/snowflake-arctic-embed-xs`
vs `MongoDB/mdbr-leaf-ir`.

## Method
- Live corpus, READ-ONLY (immutable): `~/.trovex-data/trovex.db` — 5070 docs,
  **21923 chunks**, 4158 logged queries.
- 48 real queries sampled, stratified: general-short 16 / owner-short 16 / owner-long 16
  (mcp tool queries are all short; boot/prompt are owner-scoped). Persisted for reproducibility.
- Query latency: raw single-query embed, `OMP_NUM_THREADS=1`, p50/p95 over 100 runs +
  16-way concurrency. Re-embed: full-corpus rate at `OMP_NUM_THREADS=4` in a niwa slot.
- Harness: `scripts/bakeoff_perf_e.py` (stages embed / reembed_rate / latency / pool / score).

## Query-embed latency (the HOT path — every /api/boot + search)
| model | query repr | single p50 | single p95 | 16-way p50 | 16-way p95 |
|---|---|---|---|---|---|
| **bge-small int8** (PROD, perf A) | int8 ONNX, threads=1 | **6.9 ms** | — | **6.9 ms** | **62 ms** |
| bge-small fp32 (this run) | fp32 fastembed | 27.1 | 33.6 | 247.5 | 327.6 |
| arctic-xs fp32 | fp32 fastembed | 13.9 | 19.6 | 115.1 | 179.6 |
| mdbr-leaf-ir | — | deferred | | | |

The incumbent's **int8 query path beats every fp32 alternative** — arctic-xs fp32
(13.9 ms single / 115 ms p95 @16-way) is ~2× slower than bge-int8 (6.9 / 62 ms).
arctic/mdbr ship no int8 query build; matching bge's hot-path latency would itself
require an int8 export per candidate (extra work, not done here).

## Re-embed (migration) cost — one-time, `OMP_NUM_THREADS=4`, 21923 chunks
| model | chunks/s | full re-embed |
|---|---|---|
| bge-small | 16.9 | ~21.6 min |
| arctic-xs | 31.7 | **~11.5 min** (~1.9× faster) |
| mdbr-leaf-ir | deferred | |

arctic-xs is ~2× faster to re-embed — a ONE-TIME migration cost, irrelevant to
steady-state serving. Not a reason to switch on its own.

## Fairness note (asymmetric prompts)
arctic-embed and mdbr-leaf-ir are ASYMMETRIC IR models: the query side needs the
instruction `"Represent this sentence for searching relevant passages: "` (doc side
empty). The first harness pass embedded queries with plain `.embed()` (no prompt) —
unfair to those models — and was discarded. The harness now uses fastembed
`query_embed()`/`passage_embed()` and the mdbr prompt + mean pooling (its
`config_sentence_transformers.json`), so any future recall pass is apples-to-apples.
`bge-small-en-v1.5` is effectively symmetric.

## Recommendation
**STAY on bge-small-en-v1.5 with the int8 query path.** It wins the steady-state hot
path (query latency) outright and needs zero migration. arctic-xs's only measured
advantage is one-time re-embed speed; mdbr-leaf-ir's claimed +2 BEIR is on MTEB, not
trovex's corpus, and its shipped fp32 ONNX is slow (its quantized q4/fp16 variants
untested here). No evidence yet that either recalls enough better on trovex's own
corpus to justify losing the int8 query-latency win plus a full re-embed.

### Migration plan (only if a future recall pass justifies a switch)
dim is 384 for all three → sqlite-vec vec_docs/vec_chunks stay dimensionally
compatible, but a model swap still forces a FULL re-embed (clear content_hash;
`db._migrate_embed_dim` drops+rebuilds both vec tables). Budget ~11.5 min (arctic,
OMP=4) to re-embed. To keep the hot-path latency, also export the new model to an
int8 ONNX query build (mirror of perf A's `Int8QueryEmbedder`); otherwise accept
fp32 query latency.

## Recall pass — DEFERRED
trovex has NO relevance labels over the real corpus: replay eval needs `used=1` rows
(session read-back) and the live DB has **0 / 4158** — a real feedback-loop bug,
filed separately as **c03d169a** (P1). Per cto, recall is deferred to a cheap TREC-style
**blind-pooled 20-query sample** run when the host is quiet. The reproducible seed is
committed: `queries.json` (the stratified sample), `pool_to_label.json` (shuffled,
model-identity-hidden union pool), and `scripts/bakeoff_perf_e.py {pool,score}`.
Running it (host quiet, in-slot): `embed bge-small` / `embed arctic-xs` /
`embed mdbr-leaf-ir` (fixed harness — asymmetric prompts) → `pool` →
hand-label `pool_to_label.json` → `labels.json` → `score`.

## Artifacts (committed)
- `scripts/bakeoff_perf_e.py` — the bake-off harness (prompt-correct: query_embed /
  passage_embed; mdbr raw-ORT mean-pool + query prompt).
- `.niwa/receipts/perf-e/queries.json` — the 48-query stratified sample (seed 1729),
  the reproducible eval seed.
- `.niwa/receipts/perf-e/latency-*.json`, `reembed-*.json` — the measured tables above.

The deferred recall pass regenerates `embed-*.json` + `pool_to_label.json` with the
prompt-correct harness (the first plain-`.embed()` top-10 was discarded as unfair, so
it is NOT committed as a seed).
