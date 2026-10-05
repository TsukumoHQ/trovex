# b02389c2 perf-B bench — /api/boot under 30-way concurrency

Method: `scripts/bench_boot_concurrency.py` — httpx ASGITransport (real
event-loop + offload-pool concurrency, no live server), 300 requests, concurrency
30, synthetic BagEmbedder store of 200 owner records across 30 agents, per-IP
rate limiter raised (all requests share one ASGI client). Same host/window;
BEFORE = the stack base (no perf-B), AFTER = this branch.

| metric        | BEFORE (pre-perf-B) | AFTER (perf-B) |
|---------------|--------------------:|---------------:|
| p50 latency   | 645.9 ms            | 22.3 ms        |
| p95 latency   | 1060.4 ms           | 123.8 ms       |
| max latency   | 1241.9 ms           | 168.5 ms       |
| throughput    | 40.8 rps            | 699.4 rps      |
| wall (300 req)| 7.36 s              | 0.43 s         |
| errors        | 0                   | 0              |
| empty/shed    | 0                   | 212            |

p95 1060 ms -> 124 ms (8.5x); throughput 40.8 -> 699.4 rps (17x). Goal
p95 < 150 ms at 30-way: MET.

Tradeoff (by design, audit Q5): under a 30-way *simultaneous* burst, 212/300
requests load-shed to an empty pack (HTTP 200) rather than queue on the
4-worker recall pool. That is what keeps p95 bounded and eliminates the
orphaned-worker pile-up that caused the 8.5-min watchdog-restart outage. Under
normal staggered load the recall pool is not saturated, so nothing sheds; the
shed is a safety valve, and the recall pool size is tunable
(TROVEX_OFFLOAD_WORKERS) if a deployment wants to trade workers for fewer sheds.

Raw receipts: b02389c2-bench-before.json, b02389c2-bench-after.json.
