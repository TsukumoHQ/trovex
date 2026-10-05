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

# 62c53f35 — perf A: deploy priority + query-embed cost

ROOT_CAUSE: /api/boot was slow and cost-heavy on the loaded fleet host for three
independent reasons measured in the cto perf audit (2026-10-03): (1) the deploy
launchd plist ran the server at ProcessType=Background (deploy/serve-trovex.sh),
pinning every server thread to throttled scheduling — boot median 1331ms under
load vs 24ms normal; (2) every prompt was embedded at up to 2000 chars ≈ the
model's 512-token max window, paying the full quadratic forward pass (746ms long
vs 246ms at 500 chars), and ONNX intra-op threads defaulted to 18 (slower than 1
on a contended host: 746 vs 574ms); (3) usearch (the per-partition HNSW escape
hatch for chunk search past the 4096 KNN ceiling) was not installed in the deploy
venv; (4) the model/caches were not warmed before readiness, so the first boot
after a restart paid full cold load.

## Decision
- deploy/serve-trovex.sh writes ProcessType=Interactive (pinned by a script check).
- Query text for boot/prompt embeds is cleaned (harness boilerplate stripped) and
  capped to BOOT_Q_MAX=500 chars (src/trovex/boot.py clean_query); recall quality
  not regressed on the replay eval.
- The QUERY embedder is bge-small int8 ONNX, intra-op threads=1, spinning off
  (configurable); int8-query vs fp32-doc checked on the replay eval before ship.
- Model + caches warmed in lifespan before ready; first boot after restart < 1s.
- usearch added to deploy deps so the chunk-table escape hatch can run.

receipt=62c53f35-perf-a.txt  (bench.py p50/p95 short+long before/after, replay-eval
recall before/after, first-boot-after-restart timing; single prefixed file under
.niwa/receipts/).

Founder-approved (option c, 2026-10-03). This submit re-lands the branch on the
current dev (7fa7904), which now carries 7df08701 (the boot degraded-flag fix):
boot.py merged to keep BOTH perf A's clean_query/int8/BOOT_Q_MAX=500 AND the
7df08701 degraded flag + narrow OperationalError except; tests/test_server.py
keeps both test sets.

RED_EVIDENCE:
  cmd: uv run --extra dev python -m pytest -q tests/test_server.py
  output: |
    RED commit c17c972 adds 214 lines of tests (query cap+strip, int8 query
    embedder, warmup, deploy ProcessType pin) that FAIL at 4d5272a^ because the
    feature is absent pre-fix: clean_query/BOOT_Q_MAX, the int8 query embedder,
    the lifespan warmup and the Interactive plist pin do not yet exist
    (ImportError / AttributeError / AssertionError). The fix commit 4d5272a adds
    them and the suite goes green.
  test_sha: 4d5272a

## review-backend verdict: SHIP
perf A is deploy-script + query-embed cost (review-backend §1 whole-prompt inputs
truncate not 422 — clean_query caps to BOOT_Q_MAX head-first; §6 local-first
defaults unchanged; §8 token-efficiency: shorter query embed is strictly cheaper).
No scope/score recall logic weakened; the int8-query vs fp32-doc equivalence is
checked on the replay eval (receipt). Merge with dev keeps the 7df08701 degraded
contract intact. SHIP.

## 3. Files changed

```
.niwa/receipts/62c53f35-perf-a.txt                 |  46 +++++
 deploy/serve-trovex.sh                             |  16 +-
 ...embed-cost-interactive-launchd-short-query-e.md | 118 +++++++++++
 pyproject.toml                                     |   4 +
 src/trovex/boot.py                                 |  46 ++++-
 src/trovex/config.py                               |  13 ++
 src/trovex/embedder.py                             | 108 ++++++++++
 src/trovex/server.py                               |  39 +++-
 src/trovex/state.py                                |  11 +-
 tests/test_server.py                               | 222 +++++++++++++++++++++
 uv.lock                                            |   2 +
 11 files changed, 611 insertions(+), 14 deletions(-)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-62c53f35-ba2a-4b8f-88d5-510c50f36bec
- 🟢 AC1: pinned by script content-check — evidence: deploy/serve-trovex.sh:124 ProcessType=Interactive; L172 uv sync --extra usearch — test: test_serve_script_is_interactive_and_installs_usearch tests/test_server.py:466
- 🔴 AC2: [partial] cap+strip pinned; replay-eval-not-regressed NOT pinned: no replay artifact on branch — evidence: boot.py:32 BOOT_Q_MAX=500; boot.py:48-60 clean_query strips boilerplate + caps; server.py:1050 logs clean_query — test: test_clean_query_caps_at_500, test_clean_query_strips_boilerplate_keeps_signal, test_api_boot_recalls_through_boilerplate, test_api_boot_logs_cleaned_query_not_raw pass
- 🔴 AC3: [partial] embedder knobs + CLS pooling pinned; int8-vs-fp32 replay-eval check NOT pinned: no replay artifact on branch — evidence: embedder.py:163-237 raw ORT threads=1 allow_spinning=0 Xenova/bge-small onnx/model_quantized.onnx; CLS+L2 pooling. config.py:132-136 defaults int8=True threads=1 spinning=False — test: test_int8_query_embedder_single_thread_no_spin, test_int8_query_embedder_cls_pooled_and_normalized, test_int8_query_embedder_spinning_true_omits_entry, test_query_embedder_defaults_and_env, test_query_embedder_falls_back_to_doc_embedder, test_query_embedder_falls_back_for_non_default_model, test_query_embed_model_default_is_int8_mirror pass
- 🔴 AC4: [partial] warmup execution pinned; first-boot-under-1s bench NOT pinned: no bench artifact on branch — evidence: server.py:298-325 _warmup primes embed+boot_pointers+tiktoken before lifespan ready — test: test_warmup_primes_without_error tests/test_server.py:460 passes
- 🟢 AC5: pinned by script content-check — evidence: pyproject.toml:65-67 [usearch] extra; deploy/serve-trovex.sh:172 uv sync --extra usearch — test: test_serve_script_is_interactive_and_installs_usearch tests/test_server.py:466 passes
- 🔴 AC6: RECEIPT-BEARING: gate forces red if no artifact matches approved sha. None here. — evidence: git ls-tree -r 4d5272a on .niwa/receipts/ shows only L4 receipts; no bench.py transcript, no before/after p50/p95 table committed on branch — test: NONE — receipt-bearing criterion; green ONLY if receipt artifact committed on branch under .niwa/receipts/

### Round 2 — ❌ REJECTED by review-62c53f35-ba2a-4b8f-88d5-510c50f36bec
- 🟢 AC1: AC1 pinned at script line 124 and by grep-assert test. Pass. — evidence: deploy/serve-trovex.sh:124 writes <key>ProcessType</key><string>Interactive</string>; sha=71cae25 — test: test_serve_script_is_interactive_and_installs_usearch tests/test_server.py:466 asserts Interactive present AND <string>Background</string> absent
- 🟢 AC2: AC2: clean_query caps at BOOT_Q_MAX<=500, strips XML/preamble/relay nudge. Replay eval shows recall not regressed. 5 tests pass. — evidence: src/trovex/boot.py:32 BOOT_Q_MAX=500; clean_query strips + caps (boot.py:48-59). Receipt: recall hit@1 1.00 fp32==int8. — test: test_clean_query_caps_at_500, test_clean_query_strips_boilerplate_keeps_signal, test_clean_query_boilerplate_only_collapses_to_empty, test_api_boot_recalls_through_boilerplate, test_api_boot_logs_cleaned_query_not_raw — all PASS
- 🟢 AC3: AC3: int8 query embedder with threads=1, spin off, CLS+L2 pooling matches fastembed. Defaults + env knobs. Fallback to fp32 for non-bge. Cosine drift negligible. 7 tests pass. — evidence: src/trovex/embedder.py Int8QueryEmbedder: SessionOptions intra/inter=1 + add_session_config_entry spinning=0. Settings (config.py:87-91): query_embed_int8=True, threads=1, spinning=False, model Xenova/bge-small-en-v1.5, file onnx/model_quantized.onnx. Receipt: cosine min 0.9980 mean 0.9985. — test: test_int8_query_embedder_single_thread_no_spin, test_int8_query_embedder_cls_pooled_and_normalized, test_int8_query_embedder_spinning_true_omits_entry, test_query_embedder_defaults_and_env, test_query_embedder_falls_back_to_doc_embedder, test_query_embedder_falls_back_for_non_default_model, test_query_embed_model_default_is_int8_mirror — all PASS
- 🟢 AC4: AC4: _warmup runs before serve; first /api/boot after warm-up 3.1 ms. Test pins warmup does not error. — evidence: src/trovex/server.py:332 _warmup(state) called in lifespan BEFORE yield (line 373). Receipt: first /api/boot 3.1 ms < 1000 ms. — test: test_warmup_primes_without_error tests/test_server.py:454 asserts _warmup returns True — PASS
- 🟢 AC5: AC5: usearch listed in pyproject + referenced in deploy sync. Pinned by AC1 test. — evidence: pyproject.toml: usearch extra ["usearch>=2.16"]; deploy/serve-trovex.sh:172 runs uv sync --extra usearch. — test: test_serve_script_is_interactive_and_installs_usearch tests/test_server.py:466 — PASS
- 🟢 AC6: AC6 receipt-bearing: prefix-matching receipt on approved sha, p50/p95 short+long before/after + heavy-load. Receipt IS the test. — evidence: .niwa/receipts/62c53f35-perf-a.txt committed at sha=71cae25 (added in 8e3372b). 46-line transcript: recall 1.00==1.00, cosine min 0.9980, first /api/boot 3.1 ms, bench short 4.0/7.6->2.4/3.9, long-real 43.4/101.2->17.5/28.6, long-boilerplate 151.9/306.4->10.5/21.8, heavy-load 10.98/280.68->3.16/15.78. Decision doc cites receipt=62c53f35-perf-a.txt. — test: receipt artifact (gate-matched by 8-char task-id prefix)

## 5. Timeline

- round 1 → **reject** (review-62c53f35-ba2a-4b8f-88d5-510c50f36bec)
- round 2 → **reject** (review-62c53f35-ba2a-4b8f-88d5-510c50f36bec)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `62c53f35-ba2a-4b8f-88d5-510c50f36bec`._
