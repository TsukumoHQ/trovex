# perf C — filter inside the vector search — receipts

Task 33ecdc9f. Artifacts for the receipt-bearing acceptance criteria.

- **gen_receipt.py** — reproducible generator. Run:
  `uv run --extra dev python .niwa/receipts/perf-c/gen_receipt.py`.
- **perf-c-receipt.md** — its captured output.

Covers:
- **Recall not regressed** (AC "recall quality not regressed on the replay eval"): the
  owner-scoped search (owner pushed into the KNN + the multi-owner fallback) returns the
  SAME result set that a brute-force owner-filtered cosine ranking (ground truth) does —
  4/4 queries, single and multi-owner. A multi-owner doc (owner='' in the vec0 column) is
  recalled for each of its owners via the doc_tags fallback.
- **Stage bench** (AC "vector + BM25 stage p50/p95 before/after", real-shape 8000-doc
  partition): vector owner-scoped ~5x (post-filter k=4096 → owner-in-KNN k=limit); BM25
  owner-scoped ~1.8x (24-term LIMIT 4096 → stopworded 8-term + owner filter LIMIT 50).

Numbers vary with host load (noted in the capture); the recall-equivalence result is
load-independent.
