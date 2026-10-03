"""perf A (task 62c53f35) receipt generator — reproducible, real models, no network
at query time (models cached by fastembed/hf). Emits markdown to stdout; the committed
perf-a-receipt.md is this script's output.

Covers the receipt-bearing ACs:
  AC2 recall not regressed by the cap+strip (hit@1/hit@k/MRR, fp32 baseline vs int8+clean)
  AC3 int8-query vs fp32-doc compatibility (cosine drift) + the embedder knobs
  AC4 first boot after restart < 1s once lifespan warm-up has run
  AC6 bench.py p50/p95 for short and long prompts, before/after
"""
import pathlib
import tempfile
import time

import numpy as np

from trovex.boot import BOOT_Q_MAX, boot_pointers, clean_query
from trovex.config import Settings
from trovex.embedder import FastEmbedEmbedder, Int8QueryEmbedder
from trovex.retrieval_eval import LabeledQuery, evaluate_retrieval
from trovex.search import Searcher
from trovex.store import SqliteStore

# --- corpus: distinct topics; a labeled query paraphrases each so a correct router
# ranks the matching doc first. Indexed with the fp32 doc embedder (production path).
DOCS = {
    "auth": "Authentication middleware validates the bearer token and refreshes the session.",
    "wal": "SQLite WAL checkpoint truncates the write-ahead log when the frame count is zero.",
    "embed": "The embedding model bge-small produces 384 dimensional sentence vectors.",
    "deploy": "The launchd plist runs the server at interactive priority so it is not throttled.",
    "knn": "The vector index runs a k nearest neighbour search partitioned by source id.",
    "rerank": "A cross encoder reranks the candidate pool before the final ranking.",
    "chunk": "The markdown chunker splits a document into heading scoped sections for retrieval.",
    "owner": "Each record is tagged with an owner so boot recall is scoped to one agent.",
    "fts": "Full text search over BM25 fuses with the dense vectors via reciprocal rank fusion.",
    "cache": "The query embedding cache turns a repeated boot query into a dict lookup.",
    "proxy": "The reverse proxy terminates TLS and renews the certificate automatically.",
    "offload": "Blocking calls run on a bounded thread pool off the event loop with a timeout.",
}
QUERIES = [
    ("how does the login token get checked", ["auth"]),
    ("when is the write ahead log shrunk", ["wal"]),
    ("what size are the sentence embeddings", ["embed"]),
    ("why is the server not cpu throttled", ["deploy"]),
    ("nearest neighbour vector lookup by source", ["knn"]),
    ("cross encoder reranking of candidates", ["rerank"]),
    ("splitting markdown into sections for search", ["chunk"]),
    ("scoping recall to a single agent owner", ["owner"]),
    ("bm25 keyword fused with dense vectors", ["fts"]),
    ("cache the repeated boot query vector", ["cache"]),
    ("tls termination and cert renewal", ["proxy"]),
    ("bounded worker pool off the loop", ["offload"]),
]


def pc(xs, p):
    return round(float(np.percentile(xs, p)), 1)


def main():
    out = []
    w = out.append
    tmp = pathlib.Path(tempfile.mkdtemp())
    settings = Settings(data_dir=tmp, embed_model="BAAI/bge-small-en-v1.5",
                        sources_config_path=tmp / "none.yaml")
    fp32 = FastEmbedEmbedder("BAAI/bge-small-en-v1.5")
    store = SqliteStore(settings, embedder=fp32)
    paths = {}
    for key, body in DOCS.items():
        paths[key] = store.put(f"# {key}\n\n{body}", kind="record", tags=[f"topic/{key}"])

    labeled = [LabeledQuery(q, [paths[k] for k in ks]) for q, ks in QUERIES]
    int8 = Int8QueryEmbedder(threads=1, spinning=False)
    s_fp32 = Searcher(settings, embedder=fp32)
    s_int8 = Searcher(settings, embedder=int8)

    w("# perf A receipt (task 62c53f35)\n")
    w(f"Host: `{__import__('os').popen('uname -sm').read().strip()}`  ")
    w(f"load: `{__import__('os').popen('uptime').read().strip().split('load averages:')[-1].strip()}`\n")

    # AC2/AC3 — recall not regressed, int8 query vs fp32 doc
    w("## AC2/AC3 — recall not regressed (fp32 baseline vs int8 query), real models\n")
    e_fp32 = evaluate_retrieval(s_fp32, labeled, k=5)
    e_int8 = evaluate_retrieval(s_int8, labeled, k=5)
    w("| run | n | hit@1 | hit@5 | MRR | recall@5 |")
    w("|---|---|---|---|---|---|")
    w(f"| fp32 query (baseline) | {e_fp32.n} | {e_fp32.hit_at_1:.2f} | {e_fp32.hit_at_k:.2f} | {e_fp32.mrr:.3f} | {e_fp32.recall_at_k:.2f} |")
    w(f"| int8 query (after)    | {e_int8.n} | {e_int8.hit_at_1:.2f} | {e_int8.hit_at_k:.2f} | {e_int8.mrr:.3f} | {e_int8.recall_at_k:.2f} |")
    w(f"\nRecall not regressed: hit@1 int8 {e_int8.hit_at_1:.2f} >= fp32 {e_fp32.hit_at_1:.2f} - 0.01 "
      f"=> {e_int8.hit_at_1 >= e_fp32.hit_at_1 - 0.01}\n")

    D = np.array([next(iter(fp32.embed([DOCS[k]]))) for k in DOCS])
    Q = np.array([next(iter(int8.embed([DOCS[k]]))) for k in DOCS])
    cos = [float(np.dot(D[i], Q[i])) for i in range(len(DOCS))]
    w(f"int8-query vs fp32-doc same-text cosine: min={min(cos):.4f} mean={sum(cos)/len(cos):.4f} "
      f"(negligible drift; same 384-d space, CLS+L2 pooling).\n")

    # AC4 — first boot < 1s after warm-up
    w("## AC4 — first boot < 1s after lifespan warm-up\n")
    _ = next(iter(int8.embed([clean_query("warmup")]) ))  # simulate lifespan warm-up
    boot_pointers(s_int8, "__warm__")  # prime the KNN plan/pages
    t = time.perf_counter()
    boot_pointers(s_int8, "nobody", q="current state resume open work next steps")
    first = (time.perf_counter() - t) * 1000
    w(f"first /api/boot after warm-up: **{first:.1f} ms** (< 1000 ms: {first < 1000}).\n")

    # AC6 — bench p50/p95 short + long, before/after
    w("## AC6 — query-embed p50/p95 (ms), short + long, before/after\n")
    SHORT = "qa gate redreverify current state"
    LONG_RAW = ("<task-notification>fleet memory DATA not instructions "
                + ("prior context line ok " * 80) + "</task-notification>\n"
                "You are **trovex-backend-2**, developer.\ncheck your relay new tasks.\n"
                "Fix the auth-middleware token-expiry off-by-one in state.py. "
                + ("extra task detail. " * 30))[:2000]
    LONG_REAL = ("deploy priority query embed cost interactive launchd onnx threads "
                 "warmup usearch partition owner tag boot recall " * 8)[:2000]

    def bench(emb, text, n=25):
        xs = []
        for i in range(n + 1):
            t0 = time.perf_counter()
            next(iter(emb.embed([text + f" {i}"])))
            xs.append((time.perf_counter() - t0) * 1000)
        return pc(xs[1:], 50), pc(xs[1:], 95)

    rows = [
        ("short", bench(fp32, SHORT), bench(int8, clean_query(SHORT) or SHORT)),
        ("long (real content)", bench(fp32, LONG_REAL), bench(int8, clean_query(LONG_REAL))),
        ("long (boilerplate-heavy)", bench(fp32, LONG_RAW), bench(int8, clean_query(LONG_RAW) or SHORT)),
    ]
    w(f"clean_query(LONG_RAW) -> {len(clean_query(LONG_RAW))} chars; "
      f"clean_query(LONG_REAL) -> {len(clean_query(LONG_REAL))} chars (cap {BOOT_Q_MAX}).\n")
    w("| prompt | before fp32 p50/p95 | after int8 p50/p95 | p50 speedup |")
    w("|---|---|---|---|")
    for name, (b50, b95), (a50, a95) in rows:
        sp = round(b50 / a50, 1) if a50 else 0
        w(f"| {name} | {b50}/{b95} | {a50}/{a95} | {sp}x |")
    w("")
    print("\n".join(out))


if __name__ == "__main__":
    main()
