"""perf E (87207ea6) embedding model bake-off harness — MEASUREMENT ONLY.

TREC-style blind pooling over trovex's real corpus (no MTEB):
  stage 1 (embed): for each candidate model, L2-normalised doc embeddings over all
    chunks (timed = re-embed wall) + per-query top-10 by brute-force cosine +
    query-embed latency (threads=1, single + 16-way concurrent).
  stage 2 (pool):  union the per-query top-10 across all models, shuffle, write a
    BLIND labeling file (model identity hidden) BEFORE any score is computed.
  stage 3 (score): read human relevance labels, compute recall@k / MRR per model.

Reads the live corpus READ-ONLY (immutable) — never writes trovex.db.
Candidates are added incrementally (bge-small fp32 prod, arctic-embed-xs; mdbr-leaf-ir
after its ONNX re-export). Run: `python scripts/bakeoff_perf_e.py <stage> [args]`.
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import threading
import time
from pathlib import Path

import numpy as np

DB = str(Path.home() / ".trovex-data" / "trovex.db")
OUT = Path(__file__).resolve().parent.parent / ".niwa" / "receipts" / "perf-e"
SEED = 1729
K = 10

# model_name -> fastembed id (None = needs a custom raw-ORT embedder, handled in build_embedder)
CANDIDATES = {
    "bge-small": "BAAI/bge-small-en-v1.5",
    "arctic-xs": "snowflake/snowflake-arctic-embed-xs",
    # "mdbr-leaf-ir": None,  # added after ONNX re-export
}


def ro_conn(db: str) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
    c.row_factory = sqlite3.Row
    return c


def load_chunks(db: str) -> tuple[list[int], list[str]]:
    c = ro_conn(db)
    rows = c.execute("SELECT id, content FROM chunks ORDER BY id").fetchall()
    c.close()
    return [r["id"] for r in rows], [r["content"] for r in rows]


def sample_queries(db: str, n: int = 50) -> list[dict]:
    """~n DISTINCT real queries stratified by (type: owner-scoped boot/prompt vs
    general mcp) x (length: short<=60 / long>400, dropping mid to sharpen the
    contrast). Deterministic via SEED. Persisted so the sample is reproducible."""
    c = ro_conn(db)
    rows = c.execute(
        "SELECT DISTINCT query, source FROM mcp_queries WHERE LENGTH(query) > 0"
    ).fetchall()
    c.close()
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        q = r["query"]
        scoped = "owner" if r["source"] in ("boot", "prompt") else "general"
        L = len(q)
        length = "short" if L <= 60 else ("long" if L > 400 else "mid")
        if length == "mid":
            continue
        buckets.setdefault(f"{scoped}-{length}", []).append({"query": q, "source": r["source"]})
    rng = random.Random(SEED)
    per = max(1, n // max(1, len(buckets)))
    out: list[dict] = []
    for key, qs in sorted(buckets.items()):
        rng.shuffle(qs)
        for item in qs[:per]:
            item["stratum"] = key
            out.append(item)
    return out


MDBR_QUERY_PROMPT = "Represent this sentence for searching relevant passages: "


class FastEmbedCand:
    """fastembed candidate — ASYMMETRIC-correct: passage_embed for docs,
    query_embed for queries (applies the model's registered query prompt). Using
    plain .embed() for queries would drop the prompt and unfairly sink recall for
    arctic/e5-style models."""

    def __init__(self, fe_id: str):
        import fastembed

        self._c = fastembed.TextEmbedding(model_name=fe_id)

    def passage(self, texts):
        return self._c.passage_embed(list(texts))

    def query(self, texts):
        return self._c.query_embed(list(texts))


class MdbrOnnxCand:
    """MongoDB/mdbr-leaf-ir via its shipped ONNX (raw ORT, threads from OMP env).
    BERT + MEAN pooling (masked) + L2. Asymmetric: query gets the
    'Represent this sentence...' prompt, document prompt is empty (per the model's
    config_sentence_transformers.json). model_file picks fp32/quantized variant."""

    def __init__(self, model_file: str = "onnx/model.onnx"):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        mid = "MongoDB/mdbr-leaf-ir"
        self._tok = Tokenizer.from_file(hf_hub_download(mid, "tokenizer.json"))
        self._tok.enable_truncation(max_length=512)
        so = ort.SessionOptions()
        self._sess = ort.InferenceSession(
            hf_hub_download(mid, model_file), sess_options=so, providers=["CPUExecutionProvider"]
        )
        self._inames = {i.name for i in self._sess.get_inputs()}

    def _embed(self, texts, prompt: str):
        texts = [prompt + t for t in texts]
        encs = self._tok.encode_batch(texts)
        if not encs:
            return np.zeros((0, 384), dtype=np.float32)
        maxlen = max(len(e.ids) for e in encs)
        ids = np.zeros((len(encs), maxlen), dtype=np.int64)
        mask = np.zeros((len(encs), maxlen), dtype=np.int64)
        for r, e in enumerate(encs):
            n = len(e.ids)
            ids[r, :n] = e.ids
            mask[r, :n] = e.attention_mask
        feeds = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._inames:
            feeds["token_type_ids"] = np.zeros_like(ids)
        feeds = {k: v for k, v in feeds.items() if k in self._inames}
        last = self._sess.run(None, feeds)[0]  # (B, T, H)
        m = mask[:, :, None].astype(np.float32)
        summed = (last * m).sum(axis=1)
        counts = np.clip(m.sum(axis=1), 1e-9, None)
        return (summed / counts).astype(np.float32)  # mean pool; L2 done by caller

    def passage(self, texts):
        yield from self._embed(list(texts), "")

    def query(self, texts):
        yield from self._embed(list(texts), MDBR_QUERY_PROMPT)


def build_embedder(name: str, fe_id: str | None):
    """Candidate with .passage(texts) and .query(texts) → iterables of raw vectors
    (caller L2-normalises). fastembed id when given; else the mdbr ONNX path."""
    if fe_id is not None:
        return FastEmbedCand(fe_id)
    if name == "mdbr-leaf-ir":
        return MdbrOnnxCand()
    raise NotImplementedError(f"{name}: no embedder wired")


def l2(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


def stage_embed(model: str):
    fe_id = CANDIDATES[model]
    ids, texts = load_chunks(DB)
    queries = sample_queries(DB)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "queries.json").write_text(json.dumps(queries, indent=2))

    embed = build_embedder(model, fe_id)

    # Re-embed wall = migration cost, at the PROCESS's default thread settings
    # (run this stage WITHOUT OMP_NUM_THREADS=1 so it reflects a real prod re-embed,
    # not a single-threaded lower bound). top-10 ordering is thread-independent.
    t0 = time.perf_counter()
    doc_vecs = np.array(list(embed.passage(texts)), dtype=np.float32)
    reembed_wall = time.perf_counter() - t0
    doc_vecs = l2(doc_vecs)
    np.save(OUT / f"docvecs-{model}.npy", doc_vecs)

    qtexts = [q["query"] for q in queries]
    qvecs = l2(np.array(list(embed.query(qtexts)), dtype=np.float32))
    sims = qvecs @ doc_vecs.T  # (Q, N) cosine (both L2)
    top = {}
    for i in range(len(queries)):
        idx = np.argsort(-sims[i])[:K]
        top[str(i)] = [{"chunk_id": int(ids[j]), "score": float(sims[i][j])} for j in idx]

    result = {
        "model": model,
        "fastembed_id": fe_id,
        "dim": int(doc_vecs.shape[1]),
        "n_chunks": len(ids),
        "reembed_wall_sec": round(reembed_wall, 1),
        "reembed_chunks_per_sec": round(len(ids) / reembed_wall, 1),
        "top10": top,
    }
    (OUT / f"embed-{model}.json").write_text(json.dumps(result, indent=2))
    print(f"{model}: reembed {reembed_wall:.1f}s ({result['reembed_chunks_per_sec']}/s, "
          f"default threads), dim={result['dim']}, top10 saved")


def stage_reembed_rate(model: str, sample: int = 2000):
    """Clean re-embed RATE on a real-corpus subset (run in-slot at OMP=4). The
    full reniced embed gives an unreliable absolute wall; this times `sample` real
    chunks at the sanctioned thread cap and extrapolates to the whole index."""
    fe_id = CANDIDATES[model]
    ids, texts = load_chunks(DB)
    sub = texts[:sample]
    embed = build_embedder(model, fe_id)
    list(embed.passage(sub[:16]))  # warm
    t0 = time.perf_counter()
    _ = np.array(list(embed.passage(sub)), dtype=np.float32)
    wall = time.perf_counter() - t0
    rate = sample / wall
    full = len(ids) / rate
    out = {
        "model": model, "sample": sample, "sample_wall_sec": round(wall, 1),
        "chunks_per_sec_omp4": round(rate, 1), "n_chunks": len(ids),
        "extrapolated_full_reembed_sec": round(full, 1),
        "extrapolated_full_reembed_min": round(full / 60, 1),
        "note": "OMP_NUM_THREADS=4 in a niwa slot; extrapolated from the subset.",
    }
    (OUT / f"reembed-{model}.json").write_text(json.dumps(out, indent=2))
    print(f"{model}: {rate:.1f} chunks/s @OMP4 -> full re-embed ~{full/60:.1f} min ({len(ids)} chunks)")


def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(p / 100 * (len(xs) - 1)))]


def stage_latency(model: str):
    """Query-embed latency: single-thread p50/p95 + 16-way concurrency.
    RUN WITH OMP_NUM_THREADS=1 so the ORT session is single-threaded (the prod
    query hot-path config, perf A). No corpus embed — just the query probe."""
    fe_id = CANDIDATES[model]
    embed = build_embedder(model, fe_id)
    queries = json.loads((OUT / "queries.json").read_text())
    probe = [q["query"] for q in queries][len(queries) // 2]
    list(embed.query([probe]))  # warm
    single = []
    for _ in range(100):
        s = time.perf_counter()
        list(embed.query([probe]))
        single.append((time.perf_counter() - s) * 1000)
    conc: list[float] = []
    lock = threading.Lock()

    def worker():
        for _ in range(20):
            s = time.perf_counter()
            list(embed.query([probe]))
            with lock:
                conc.append((time.perf_counter() - s) * 1000)

    ths = [threading.Thread(target=worker) for _ in range(16)]
    t = time.perf_counter()
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    conc_wall = time.perf_counter() - t
    out = {
        "model": model,
        "single_p50": round(_pct(single, 50), 2),
        "single_p95": round(_pct(single, 95), 2),
        "conc16_p50": round(_pct(conc, 50), 2),
        "conc16_p95": round(_pct(conc, 95), 2),
        "conc16_wall_sec": round(conc_wall, 2),
        "note": "fp32 fastembed, OMP=1. bge-small prod query path is int8 (perf A: 6.9/62ms p50/p95 @16-way).",
    }
    (OUT / f"latency-{model}.json").write_text(json.dumps(out, indent=2))
    print(f"{model} latency: single p50/p95 {out['single_p50']}/{out['single_p95']}ms, "
          f"16-way p50/p95 {out['conc16_p50']}/{out['conc16_p95']}ms")


def stage_pool():
    """Union per-query top-10 across all embed-*.json, shuffle, emit a BLIND
    labeling file (model identity + score hidden). Chunk excerpts included so a
    judge can rate relevance from the text alone."""
    queries = json.loads((OUT / "queries.json").read_text())
    embeds = {}
    for f in OUT.glob("embed-*.json"):
        r = json.loads(f.read_text())
        embeds[r["model"]] = r["top10"]
    c = ro_conn(DB)
    excerpt = {}

    def text_of(cid: int) -> str:
        if cid not in excerpt:
            row = c.execute("SELECT content FROM chunks WHERE id=?", (cid,)).fetchone()
            excerpt[cid] = (row["content"][:400] if row else "")
        return excerpt[cid]

    rng = random.Random(SEED)
    pool = []
    for i, q in enumerate(queries):
        cids = set()
        for top in embeds.values():
            for hit in top.get(str(i), []):
                cids.add(hit["chunk_id"])
        docs = [{"chunk_id": cid, "excerpt": text_of(cid)} for cid in cids]
        rng.shuffle(docs)
        pool.append({"qi": i, "query": q["query"], "stratum": q["stratum"], "candidates": docs})
    c.close()
    (OUT / "pool_to_label.json").write_text(json.dumps(pool, indent=2))
    n_pairs = sum(len(p["candidates"]) for p in pool)
    print(f"pool: {len(pool)} queries, {n_pairs} (query,doc) pairs to label -> {OUT/'pool_to_label.json'}")


def stage_score():
    """labels.json: {qi: {chunk_id: 0|1|2}} (graded relevance). Compute recall@k
    and MRR per model from the per-model top-10 (relevant = label>=1)."""
    labels = {int(k): {int(c): v for c, v in d.items()} for k, d in json.loads((OUT / "labels.json").read_text()).items()}
    embeds = {}
    for f in OUT.glob("embed-*.json"):
        r = json.loads(f.read_text())
        embeds[r["model"]] = r["top10"]
    print(f"{'model':12} {'recall@1':>9} {'recall@5':>9} {'recall@10':>10} {'MRR@10':>8}  (over queries with >=1 relevant)")
    for model, top in sorted(embeds.items()):
        r1 = r5 = r10 = mrr = 0.0
        nq = 0
        for qi, rel in labels.items():
            relevant = {cid for cid, g in rel.items() if g >= 1}
            if not relevant:
                continue
            nq += 1
            ranked = [h["chunk_id"] for h in top.get(str(qi), [])]
            hit_ranks = [i + 1 for i, cid in enumerate(ranked) if cid in relevant]
            if hit_ranks:
                first = hit_ranks[0]
                r1 += first == 1
                r5 += first <= 5
                r10 += first <= 10
                mrr += 1.0 / first
        if nq:
            print(f"{model:12} {r1/nq:9.3f} {r5/nq:9.3f} {r10/nq:10.3f} {mrr/nq:8.3f}  (n={nq})")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "embed"
    if stage == "embed":
        stage_embed(sys.argv[2])
    elif stage == "latency":
        stage_latency(sys.argv[2])
    elif stage == "reembed_rate":
        stage_reembed_rate(sys.argv[2])
    elif stage == "pool":
        stage_pool()
    elif stage == "score":
        stage_score()
    else:
        print(f"unknown stage {stage}")
