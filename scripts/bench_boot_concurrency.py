#!/usr/bin/env python
"""Concurrency bench for /api/boot — the fleet's hot path (task b02389c2 AC6).

Fires N concurrent /api/boot requests at the in-process ASGI app via httpx's
ASGITransport (real event-loop + offload-pool concurrency, NO live server) and
reports p50/p95/max latency, error rate, and shed/empty rate.

Tree-runnable by design: it builds a synthetic store with the deterministic
BagEmbedder, so it needs no model download and never touches the live service
or ~/.trovex-data. Run it on origin/dev for the baseline and on this branch for
the 'after' to get an honest before/after on the same host:

    uv run --extra dev python scripts/bench_boot_concurrency.py \
        --concurrency 30 --requests 300 --docs 200 [--json receipt.json]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import statistics
import tempfile
import time
from pathlib import Path

import numpy as np

DIM = 384


class BagEmbedder:
    name = "bag"
    dim = DIM

    def embed(self, texts):
        for t in texts:
            v = np.zeros(DIM, dtype=np.float32)
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                idx = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                v[idx % DIM] += 1.0
            norm = float(np.linalg.norm(v)) or 1.0
            yield v / norm


def _build_app(n_docs: int, n_agents: int):
    """A FastAPI app backed by a synthetic store of n_docs owner records spread
    over n_agents, with the state injected the same way tests do."""
    from trovex import state as state_mod
    from trovex.config import Settings
    from trovex.indexer import Indexer
    from trovex.search import Searcher
    from trovex.server import build_app
    from trovex.state import AppState
    from trovex.store import SqliteStore

    try:  # perf-B's background writer; absent on the pre-perf-B baseline
        from trovex.usage import start_query_log_writer
    except ImportError:
        start_query_log_writer = None

    tmp = Path(tempfile.mkdtemp(prefix="trovex-bench-"))
    settings = Settings(
        data_dir=tmp,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp / "no-such-sources.yaml",
        # Disable the per-IP rate limiter for the bench — all requests share one
        # ASGI client, so the default 30/minute would just measure the limiter.
        rate_limit_search="100000000/minute",
        rate_limit_write="100000000/minute",
    )
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)
    agents = [f"agent{i}" for i in range(n_agents)]
    for i in range(n_docs):
        store.put(
            f"# record {i}\n\ncurrent state resume open work in flight next steps gotchas {i}",
            kind="record",
            tags=[f"owner/{agents[i % n_agents]}"],
        )
    state_mod._state = AppState(
        settings=settings,
        embedder=embedder,
        searcher=Searcher(settings, embedder=embedder),
        indexer=Indexer(settings, embedder=embedder),
        store=store,
    )
    # Start the background query-log writer so the boot path enqueues (prod path)
    # instead of the synchronous fallback. Absent on the pre-perf-B baseline.
    if start_query_log_writer is not None:
        start_query_log_writer(settings.data_dir)
    return build_app(), agents


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = max(0, min(len(values) - 1, int(round((p / 100.0) * (len(values) - 1)))))
    return values[k]


async def _run(concurrency: int, requests: int, n_docs: int, n_agents: int) -> dict:
    import httpx

    app, agents = _build_app(n_docs, n_agents)
    sem = asyncio.Semaphore(concurrency)
    latencies_ms: list[float] = []
    errors = 0
    empty = 0

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://bench") as client:
        async def one(i: int) -> None:
            nonlocal errors, empty
            agent = agents[i % len(agents)]
            async with sem:
                t0 = time.perf_counter()
                try:
                    r = await client.get("/api/boot", params={"agent": agent, "floor": 0.0})
                except Exception:
                    errors += 1
                    return
                latencies_ms.append((time.perf_counter() - t0) * 1000)
                if r.status_code != 200:
                    errors += 1
                elif not r.json().get("pointers"):
                    empty += 1

        wall0 = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(requests)))
        wall_s = time.perf_counter() - wall0

    return {
        "concurrency": concurrency,
        "requests": requests,
        "docs": n_docs,
        "agents": n_agents,
        "wall_s": round(wall_s, 3),
        "throughput_rps": round(requests / wall_s, 1) if wall_s else 0,
        "p50_ms": round(_pct(latencies_ms, 50), 1),
        "p95_ms": round(_pct(latencies_ms, 95), 1),
        "max_ms": round(max(latencies_ms), 1) if latencies_ms else 0,
        "mean_ms": round(statistics.mean(latencies_ms), 1) if latencies_ms else 0,
        "errors": errors,
        "empty_or_shed": empty,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--concurrency", type=int, default=30)
    ap.add_argument("--requests", type=int, default=300)
    ap.add_argument("--docs", type=int, default=200)
    ap.add_argument("--agents", type=int, default=30)
    ap.add_argument("--json", type=str, default="", help="write the receipt to this path")
    args = ap.parse_args()

    result = asyncio.run(_run(args.concurrency, args.requests, args.docs, args.agents))
    text = json.dumps(result, indent=2)
    print(text)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(text + "\n")


if __name__ == "__main__":
    main()
