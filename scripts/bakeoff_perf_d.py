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


class _StaticReplaySearcher:
    """Minimal Searcher-shaped object for replay_eval over the STATIC vectors: a
    global (unscoped) doc KNN against vec_docs_static, returning rows with `.path`
    — the same shape eval_replay reads off the dense Searcher."""

    def __init__(self, conn: sqlite3.Connection, model):
        from types import SimpleNamespace

        self.db = conn
        self._model = model
        self._ns = SimpleNamespace

    def search(self, query: str, limit: int = 20, **_):
        import sqlite_vec

        vec = _norm(np.array(self._model.encode([query[:2000]]), dtype=np.float32))[0]
        blob = sqlite_vec.serialize_float32(vec.tolist())
        rows = self.db.execute(
            """SELECT d.path AS path, v.distance AS distance
               FROM vec_docs_static v JOIN docs d ON d.id = v.rowid
               WHERE v.embedding MATCH ? AND k = ? AND v.source_id = 'trovex'
               ORDER BY v.distance""",
            (blob, max(limit, 1)),
        ).fetchall()
        return [self._ns(path=r["path"], score=1.0 - (r["distance"] or 0.0)) for r in rows]


def replay() -> dict:
    """AC3 (literal): run the REAL eval_replay.replay_eval for the dense AND the
    static recall paths over trovex's own logged queries, and report both reports'
    recall numbers. Operates on a COPY of the live DB (never mutates it): the copy
    gets its vec_docs_static populated with potion, then dense and static searchers
    replay the same query log. With 0 used-labelled rows (bug c03d169a) both report
    n_used_labeled=0 ⇒ hit@1/MRR 0.0 — the literal recall@k is DEFERRED, which this
    receipt makes self-evident from the named tool's own output (see overlap.json
    for the computable static-vs-dense signal in the meantime)."""
    import shutil
    import tempfile

    from trovex.config import Settings
    from trovex.db import vec_docs_static_put
    from trovex.eval_replay import replay_eval
    from trovex.embedder import embedder_from_settings, query_embedder_from_settings
    from trovex.search import Searcher

    tmp = Path(tempfile.mkdtemp())
    shutil.copy(DB_PATH, tmp / "trovex.db")
    for ext in ("-wal", "-shm"):
        src = Path(DB_PATH + ext)
        if src.exists():
            shutil.copy(src, tmp / ("trovex.db" + ext))
    settings = Settings(
        data_dir=tmp,
        sources_config_path=tmp / "no.yaml",
        static_embed_enabled=True,
        static_embed_dim=512,
    )
    dense = embedder_from_settings(settings)
    qembed = query_embedder_from_settings(settings, dense)
    searcher = Searcher(settings, embedder=qembed)

    # Populate static doc vectors on the copy so the static searcher has an index.
    stat = _static_model()
    conn = searcher.db
    docs = [(r["id"], f'{r["title"]}\n\n{r["content"]}'[:8000])
            for r in conn.execute("SELECT id, title, content FROM docs")]
    vecs = _norm(np.array(stat.encode([t for _, t in docs]), dtype=np.float32))
    import sqlite_vec
    for (did, _), v in zip(docs, vecs, strict=True):
        vec_docs_static_put(conn, did, sqlite_vec.serialize_float32(v.tolist()), "static")
    conn.commit()

    static_searcher = _StaticReplaySearcher(conn, stat)
    window = 10 * 365 * 24 * 3600  # all history
    dense_rep = replay_eval(conn, searcher, since_seconds=window, limit=200, k=5)
    static_rep = replay_eval(conn, static_searcher, since_seconds=window, limit=200, k=5)

    def _row(rep) -> dict:
        return {
            "n": rep.n,
            "n_used_labeled": rep.n_used_labeled,
            "hit_at_1_used": round(rep.hit_at_1_used, 3),
            "hit_at_k_used": round(rep.hit_at_k_used, 3),
            "mrr_used": round(rep.mrr_used, 3),
        }

    out = {
        "tool": "trovex.eval_replay.replay_eval",
        "k": 5,
        "dense": _row(dense_rep),
        "static": _row(static_rep),
        "recall_status": "DEFERRED — 0 used-labelled rows (bug c03d169a); hit@1/MRR "
        "are 0.0 for BOTH paths because the replay eval has no relevance signal, not "
        "because recall is zero. Absolute recall@k runs on the blind pool once "
        "c03d169a lands; overlap.json is the computable static-vs-dense signal now.",
    }
    (OUT / "replay.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("reembed_rate", "all"):
        reembed_rate()
    if stage in ("overlap", "all"):
        overlap()
    if stage in ("replay", "all"):
        replay()
