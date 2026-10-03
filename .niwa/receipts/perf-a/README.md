# perf A — deploy priority + query-embed cost — receipts

Task 62c53f35. Artifacts proving the receipt-bearing acceptance criteria.

- **gen_receipt.py** — reproducible generator (real bge-small fp32 doc embedder + the
  int8 raw-ORT query embedder; models cached, no network at query time). Run:
  `uv run --extra dev python .niwa/receipts/perf-a/gen_receipt.py`.
- **perf-a-receipt.md** — its captured output on an M-series host under live fleet load.

Covers:
- **AC2** query cap + boilerplate strip: recall NOT regressed — hit@1/hit@5/MRR identical
  for the fp32 baseline and the int8+clean_query run over a 12-query labelled set.
- **AC3** int8 query embedder: int8-query vs fp32-doc same-text cosine ≈ 0.998 (negligible
  drift, same 384-d CLS+L2 space); embedder knobs (threads=1, spin off, pooling) pinned by
  tests in tests/test_server.py.
- **AC4** warm-up: first `/api/boot` after the lifespan warm-up is ~3 ms (< 1 s).
- **AC6** bench p50/p95 for short + long prompts, before (fp32, raw) / after (int8, capped+
  stripped): ~1.4–1.5x on real content, ~12x on a boilerplate-heavy prompt; single-query
  embed fp32 10.98/280.68 → int8 3.16/15.78 ms (3.47x p50) measured separately under load.

Numbers vary with host load (noted in the capture); the ranking/recall results are
load-independent.
