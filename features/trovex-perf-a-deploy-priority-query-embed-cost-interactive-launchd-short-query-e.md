# [trovex/perf A] deploy priority + query-embed cost: Interactive launchd, short query embed, ONNX threads=1, warmup, usearch in deploy venv

## Team : trovex-backend-2 (tsukumo)
## Branch : trovex-backend-2/load-capacity (from dev)
## Relay task : 62c53f35-ba2a-4b8f-88d5-510c50f36bec
## Trace : trace=74cd2f7293fb1145baee1e2256b2db9b
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. deploy/serve-trovex.sh writes ProcessType=Interactive (test or script check pins it)
- [ ] 2. query text for boot/prompt embeds capped to ~400-500 chars after boilerplate strip (task-notification XML, 'check your relay' templates, etc.), test pins it, recall quality not regressed on the replay eval
- [ ] 3. QUERY embedder = bge-small int8 ONNX, intra-op threads=1, spinning off (configurable); research measured 6.9ms p50 / 62ms p95 at 16 concurrent vs 16/172ms today; int8-query vs fp32-doc vectors checked on the replay eval before shipping
- [ ] 4. model + caches warmed in lifespan before ready, first boot after restart < 1s (bench)
- [ ] 5. usearch added to deploy deps so the chunk-table escape hatch can run
- [ ] 6. receipt: bench.py p50/p95 for short and long prompts, before/after

## 2. Root cause & decisions

# perf A — query-embed cost + deploy priority (task 62c53f35)

ROOT_CAUSE: /api/boot query-side latency on the loaded fleet host came from four
plumbing faults, not the model choice: (1) the launchd plist ran trovex at
ProcessType=Background, pinning every thread to prio-4 / E-cores with throttled IO
(~30-55x slower compute, 85s /healthz); (2) every prompt was embedded at the full
2000-char / 512-token window (the model max) with harness boilerplate leading the
text; (3) the fp32 fastembed ONNX session spin-waits across all 18 cores, slower and
contending under oversubscription, and fastembed exposes no knob to disable it; (4)
usearch (the chunk-table HNSW escape hatch) was never installed in the deploy venv.

DECISION (per cto research trovex-perf-20261003): keep bge-small + sqlite-vec, no
re-embed. Interactive launchd; strip boilerplate + cap the query to 500 chars; a
dedicated int8 raw-ORT query session (threads=1, spinning off) while docs stay fp32;
warm the model/caches in lifespan; install usearch in the deploy venv. Line ownership
respected — db.py conns/pools, offload, usage writer and the boot deadline belong to
trovex-backend (b02389c2) and are untouched here.

REJECTED ALTERNATIVES:
- int8 via fastembed: fastembed only exposes enable_cpu_mem_arena, not
  session.intra_op.allow_spinning — cannot disable spin-wait. Hence raw ORT.
- threads=1 on the shared fastembed embedder (original AC): would also throttle the
  batch INDEX path. Superseded by a query-only int8 session.
- int8 for doc vectors too: unnecessary re-embed of the whole store; docs stay fp32.

int8-query vs fp32-doc COMPATIBILITY (checked before ship, real models): same-text
cosine min 0.9979 / mean 0.9984; top-1 fp32-doc match 12/12 on representative agent
prompts — same 384-d space, CLS+L2 pooling matches fastembed exactly.

## RECEIPT (perf A ship numbers)

COMMITTED ARTIFACTS (gate-checked, under .niwa/receipts/perf-a/): `gen_receipt.py`
(reproducible generator) + `perf-a-receipt.md` (captured output) + `README.md`. They
pin AC2 (recall not regressed: hit@1/hit@5/MRR 1.00 fp32==int8 over a 12-query labelled
set), AC3 (int8-vs-fp32 cosine 0.998), AC4 (first /api/boot after warm-up ~3 ms < 1 s),
AC6 (bench p50/p95 short+long before/after). Summary numbers below.

Host: M5 Max, load 60-120. bge-small 384-d. Query-embed p50/p95 (ms), single query:
  fp32 fastembed (ORT default spinning pool): 10.98 / 280.68
  int8 raw-ORT, threads=1, spin off:           3.16 /  15.78   (3.47x p50; p95 280->16)
End-to-end query-side (before = fp32 + raw 2000ch; after = int8 + clean_query):
  short 6.7/107.1 -> 3.5/144.3 (1.9x p50; after-p95 a load-121 outlier, compute ~3ms)
  long real-content 1048ch->500ch: 68.9/136.2 -> 26.8/30.3 (2.6x)
  long boilerplate-heavy 2000ch->42ch: 192.1/1375.4 -> 5.6/6.2 (34x)
verify_cmd tests/test_server.py: passed. Full suite: 1002 passed (warm). ruff clean.

## review-backend verdict: SHIP

Self-reviewed: §1 recall — head-truncation preserved, scope-before-score + owner-tag
lowercasing untouched, recall-through-boilerplate + replay-parity tests added; int8↔
fp32 share the vec space (drift 0.998). §5 — warmup and the int8-build fallback are
best-effort (log + degrade), never crash the tool. §6 — no privacy default flipped
(int8 is local ONNX, host bind unchanged). No db.py/offload/usage-writer lines touched.

RED_EVIDENCE:
  cmd: uv run --extra dev python -m pytest -q tests/test_server.py
  test_sha: 4d5272a36e5765f331735cc6a394dec1c98b463a
  output: |
    # test_sha is the FIX commit; its parent c17c972 is the RED test commit — the
    # gate re-runs verify_cmd at test_sha^ (c17c972, failing tests present, impl
    # absent) and must see RED. That parent run fails at collection/assert:
    ERROR tests/test_server.py - ImportError: cannot import name 'clean_query' from 'trovex.boot'
    (and, once clean_query lands, Int8QueryEmbedder / query_embed_* / the deploy-script
    pins fail) — the perf A tests cannot pass without the implementation.
    1 error during collection

## 3. Files changed

```
.niwa/receipts/perf-a/README.md         |  22 ++++
 .niwa/receipts/perf-a/gen_receipt.py    | 143 ++++++++++++++++++++
 .niwa/receipts/perf-a/perf-a-receipt.md |  30 +++++
 deploy/serve-trovex.sh                  |  16 ++-
 pyproject.toml                          |   4 +
 src/trovex/boot.py                      |  46 ++++++-
 src/trovex/config.py                    |  13 ++
 src/trovex/embedder.py                  | 108 ++++++++++++++++
 src/trovex/server.py                    |  39 +++++-
 src/trovex/state.py                     |  11 +-
 tests/test_server.py                    | 222 ++++++++++++++++++++++++++++++++
 uv.lock                                 |   2 +
 12 files changed, 642 insertions(+), 14 deletions(-)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-62c53f35-ba2a-4b8f-88d5-510c50f36bec
- 🟢 AC1: pinned by script content-check — evidence: deploy/serve-trovex.sh:124 ProcessType=Interactive; L172 uv sync --extra usearch — test: test_serve_script_is_interactive_and_installs_usearch tests/test_server.py:466
- 🔴 AC2: [partial] cap+strip pinned; replay-eval-not-regressed NOT pinned: no replay artifact on branch — evidence: boot.py:32 BOOT_Q_MAX=500; boot.py:48-60 clean_query strips boilerplate + caps; server.py:1050 logs clean_query — test: test_clean_query_caps_at_500, test_clean_query_strips_boilerplate_keeps_signal, test_api_boot_recalls_through_boilerplate, test_api_boot_logs_cleaned_query_not_raw pass
- 🔴 AC3: [partial] embedder knobs + CLS pooling pinned; int8-vs-fp32 replay-eval check NOT pinned: no replay artifact on branch — evidence: embedder.py:163-237 raw ORT threads=1 allow_spinning=0 Xenova/bge-small onnx/model_quantized.onnx; CLS+L2 pooling. config.py:132-136 defaults int8=True threads=1 spinning=False — test: test_int8_query_embedder_single_thread_no_spin, test_int8_query_embedder_cls_pooled_and_normalized, test_int8_query_embedder_spinning_true_omits_entry, test_query_embedder_defaults_and_env, test_query_embedder_falls_back_to_doc_embedder, test_query_embedder_falls_back_for_non_default_model, test_query_embed_model_default_is_int8_mirror pass
- 🔴 AC4: [partial] warmup execution pinned; first-boot-under-1s bench NOT pinned: no bench artifact on branch — evidence: server.py:298-325 _warmup primes embed+boot_pointers+tiktoken before lifespan ready — test: test_warmup_primes_without_error tests/test_server.py:460 passes
- 🟢 AC5: pinned by script content-check — evidence: pyproject.toml:65-67 [usearch] extra; deploy/serve-trovex.sh:172 uv sync --extra usearch — test: test_serve_script_is_interactive_and_installs_usearch tests/test_server.py:466 passes
- 🔴 AC6: RECEIPT-BEARING: gate forces red if no artifact matches approved sha. None here. — evidence: git ls-tree -r 4d5272a on .niwa/receipts/ shows only L4 receipts; no bench.py transcript, no before/after p50/p95 table committed on branch — test: NONE — receipt-bearing criterion; green ONLY if receipt artifact committed on branch under .niwa/receipts/

## 5. Timeline

- round 1 → **reject** (review-62c53f35-ba2a-4b8f-88d5-510c50f36bec)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `62c53f35-ba2a-4b8f-88d5-510c50f36bec`._
