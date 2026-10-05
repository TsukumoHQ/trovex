#!/usr/bin/env python
"""perf D (task ad2ad98e) measurement harness — static-embedding fallback.

Two measurements on trovex's OWN corpus (READ-ONLY, immutable open — never writes
the live DB), emitted as receipts under .niwa/receipts/perf-d/:

  1. reembed_rate: embed every chunk with potion (Model2Vec) and report the rate —
     proves AC1 "embed 30k chunks in seconds" at real corpus scale.
  2. overlap: on sampled real boot/prompt queries, how much the DEGRADED static
     recall agrees with the DENSE recall (top-5 overlap + static-top1-in-dense-top5),
     both ranked in-memory over each agent's own record docs. This is the AC3
     static-vs-dense signal that does NOT need relevance labels — trovex has 0 used-
     labelled queries (replay eval bug c03d169a), so ABSOLUTE recall@k stays DEFERRED
     to the blind-pool method (see the report); this overlap quantifies the quality
     gap of the fallback vs the normal path on live traffic in the meantime.

Usage:  uv run python scripts/bakeoff_perf_d.py [reembed_rate|overlap|all]
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

DB_PATH = os.path.expanduser("~/.trovex-data/trovex.db")
OUT = Path(__file__).resolve().parent.parent / ".niwa" / "receipts" / "perf-d"
STATIC_MODEL = "minishlab/potion-retrieval-32M"
DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SEED = 1729
BOOT_QUERY = "current state resume open work in flight next steps gotchas"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _static_model():
    from model2vec import StaticModel

    return StaticModel.from_pretrained(STATIC_MODEL)


def reembed_rate() -> dict:
    """AC1: static-embed every chunk; report chunks/s + wall time."""
    conn = _db()
    texts = [r["content"] for r in conn.execute("SELECT content FROM chunks")]
    n = len(texts)
    m = _static_model()
    t0 = time.perf_counter()
    vecs = m.encode(texts)
    dt = time.perf_counter() - t0
    out = {
        "model": STATIC_MODEL,
        "chunks": n,
        "dim": int(vecs.shape[1]),
        "wall_s": round(dt, 3),
        "chunks_per_s": round(n / dt, 1),
        "note": f"all {n} chunks embedded in {dt:.2f}s (AC1: 'embed 30k chunks in seconds')",
    }
    (OUT / "reembed-rate.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return out


def _norm(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    return v / n


def overlap(k: int = 5, sample: int = 50) -> dict:
    """AC3 proxy: static-vs-dense top-k agreement on real boot/prompt queries.

    The query log stores no agent identity (user is the OS user), so this measures
    the EMBEDDING-SPACE quality gap directly: for each sampled real query, rank the
    record-doc pool (the boot recall universe) by dense cosine and by static cosine,
    in-memory, and report top-k overlap + whether the static #1 lands in the dense
    top-k. Higher = the degraded fallback preserves more of the normal path's
    ranking."""
    from fastembed import TextEmbedding

    conn = _db()
    recs = [
        (r["id"], f'{r["title"]}\n\n{r["content"]}'[:8000])
        for r in conn.execute("SELECT id, title, content FROM docs WHERE kind='record'")
    ]
    ids = [did for did, _ in recs]
    txts = [t for _, t in recs]

    qrows = [
        r["query"]
        for r in conn.execute(
            "SELECT query FROM mcp_queries WHERE source IN ('boot','prompt') AND query IS NOT NULL AND query != ''"
        )
    ]
    random.Random(SEED).shuffle(qrows)
    picked = [q for q in qrows[:sample]] or [BOOT_QUERY]

    dense = TextEmbedding(model_name=DENSE_MODEL)
    stat = _static_model()

    d_mat = _norm(np.array(list(dense.embed(txts)), dtype=np.float32))
    s_mat = _norm(np.array(stat.encode(txts), dtype=np.float32))

    overlaps, top1_in = [], []
    for q in picked:
        dq = _norm(np.array(list(dense.embed([q[:2000]])), dtype=np.float32))[0]
        sq = _norm(np.array(stat.encode([q[:2000]]), dtype=np.float32))[0]
        d_top = [ids[i] for i in np.argsort(-(d_mat @ dq))[:k]]
        s_top = [ids[i] for i in np.argsort(-(s_mat @ sq))[:k]]
        overlaps.append(len(set(d_top) & set(s_top)) / float(k))
        top1_in.append(1.0 if s_top and s_top[0] in d_top else 0.0)

    out = {
        "static_model": STATIC_MODEL,
        "dense_model": DENSE_MODEL,
        "k": k,
        "pool_record_docs": len(ids),
        "queries_scored": len(picked),
        "mean_overlap_at_k": round(float(np.mean(overlaps)), 3) if overlaps else None,
        "static_top1_in_dense_topk": round(float(np.mean(top1_in)), 3) if top1_in else None,
        "n_used_labelled": conn.execute(
            "SELECT COUNT(*) FROM mcp_query_results WHERE used=1"
        ).fetchone()[0],
        "note": "absolute recall@k DEFERRED (0 used-labels, bug c03d169a); this is the "
        "static-vs-dense agreement on live boot traffic — how much the degraded "
        "fallback preserves the normal path's ranking.",
    }
    (OUT / "overlap.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("reembed_rate", "all"):
        reembed_rate()
    if stage in ("overlap", "all"):
        overlap()
