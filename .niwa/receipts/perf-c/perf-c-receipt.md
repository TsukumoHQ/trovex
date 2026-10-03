# perf C receipt (task 33ecdc9f)

Host: `Darwin arm64`  load: `16.85 38.89 29.15`

## A. recall not regressed — owner-scoped search == brute-force ground truth

| owner | query | new top-k == ground-truth |
|---|---|---|
| owner/alpha | how is the login token checked | True |
| owner/alpha | when is the wal shrunk | True |
| owner/beta | keyword search fused with vector | True |
| owner/beta | shared handoff for both agents | True |

result-set equivalence: 4/4 (owner-scoped recall unchanged vs ground truth).
multi-owner doc recalled for alpha: True; for beta: True (owner='' + doc_tags fallback).

## B. stage bench — vector + BM25 p50/p95 (ms), before/after

index: 8000 docs, 40 owners (~200/owner), 1 partition
| stage | before p50/p95 | after p50/p95 | p50 speedup |
|---|---|---|---|
| vector (owner-scoped) | 13.43/17.9 | 2.59/2.84 | 5.2x |
| BM25 (owner-scoped) | 19.06/20.64 | 10.89/11.44 | 1.8x |

