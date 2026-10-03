# perf A receipt (task 62c53f35)

Host: `Darwin arm64`  
load: `75.18 48.59 27.22`

## AC2/AC3 — recall not regressed (fp32 baseline vs int8 query), real models

| run | n | hit@1 | hit@5 | MRR | recall@5 |
|---|---|---|---|---|---|
| fp32 query (baseline) | 12 | 1.00 | 1.00 | 1.000 | 1.00 |
| int8 query (after)    | 12 | 1.00 | 1.00 | 1.000 | 1.00 |

Recall not regressed: hit@1 int8 1.00 >= fp32 1.00 - 0.01 => True

int8-query vs fp32-doc same-text cosine: min=0.9980 mean=0.9985 (negligible drift; same 384-d space, CLS+L2 pooling).

## AC4 — first boot < 1s after lifespan warm-up

first /api/boot after warm-up: **3.1 ms** (< 1000 ms: True).

## AC6 — query-embed p50/p95 (ms), short + long, before/after

clean_query(LONG_RAW) -> 96 chars; clean_query(LONG_REAL) -> 500 chars (cap 500).

| prompt | before fp32 p50/p95 | after int8 p50/p95 | p50 speedup |
|---|---|---|---|
| short | 4.0/7.6 | 2.4/3.9 | 1.7x |
| long (real content) | 43.4/101.2 | 17.5/28.6 | 2.5x |
| long (boilerplate-heavy) | 151.9/306.4 | 10.5/21.8 | 14.5x |

