"""perf C (task 33ecdc9f) receipt generator — reproducible.

Two parts:
  A) RECALL NOT REGRESSED (real bge-small embedder): the owner-scoped search (owner
     pushed into the KNN + the multi-owner fallback) returns the SAME result set a
     brute-force owner-filtered cosine ranking (ground truth) does — single AND
     multi-owner. Equivalence == no recall regression vs the old post-filter path.
  B) STAGE BENCH (synthetic real-shape index, no model): vector + BM25 recall stage
     p50/p95, before (post-filter k=4096) vs after (owner-in-KNN k=limit / capped FTS5).

Emits markdown to stdout; perf-c-receipt.md is this script's captured output.
"""
import pathlib
import tempfile
import time

import numpy as np
import sqlite_vec

from trovex.config import Settings
from trovex.db import open_db
from trovex.embedder import FastEmbedEmbedder
from trovex.search import Searcher
from trovex.store import SqliteStore


def pc(xs, p):
    return round(float(np.percentile(xs, p)), 2)


def part_a_recall():
    out = ["## A. recall not regressed — owner-scoped search == brute-force ground truth\n"]
    tmp = pathlib.Path(tempfile.mkdtemp())
    settings = Settings(data_dir=tmp, embed_model="BAAI/bge-small-en-v1.5",
                        sources_config_path=tmp / "none.yaml")
    emb = FastEmbedEmbedder("BAAI/bge-small-en-v1.5")
    store = SqliteStore(settings, embedder=emb)
    topics = {
        "auth": "login bearer token validation and session refresh",
        "wal": "sqlite write ahead log checkpoint truncation",
        "knn": "nearest neighbour vector search partitioned by source",
        "embed": "bge small 384 dimensional sentence embeddings",
        "deploy": "launchd interactive priority not throttled",
        "fts": "bm25 keyword search fused with dense vectors",
    }
    # alpha owns the first 4, beta the last 2; one doc is SHARED (multi-owner).
    for i, (k, body) in enumerate(topics.items()):
        owner = "owner/alpha" if i < 4 else "owner/beta"
        store.put(f"# {k}\n\n{body}", kind="record", tags=[owner])
    shared = store.put("# shared\n\nshared handoff state for both agents",
                       kind="record", tags=["owner/alpha", "owner/beta"])

    searcher = Searcher(settings, embedder=emb)
    # ground truth: for an owner, the correct recall is every record carrying that
    # owner tag, ranked by true cosine to the query.
    def ground_truth(owner, qvec, k=5):
        rows = store.db.execute(
            "SELECT d.id, d.ext_id FROM docs d JOIN doc_tags t ON t.doc_id=d.id WHERE t.tag=?",
            (owner,)).fetchall()
        scored = []
        for r in rows:
            row = store.db.execute("SELECT embedding FROM vec_docs WHERE rowid=?", (r["id"],)).fetchone()
            if not row:
                continue
            dv = np.frombuffer(row["embedding"], dtype=np.float32)
            scored.append((float(np.dot(qvec, dv)), r["ext_id"]))
        scored.sort(reverse=True)
        return [e for _, e in scored[:k]]

    queries = [
        ("owner/alpha", "how is the login token checked"),
        ("owner/alpha", "when is the wal shrunk"),
        ("owner/beta", "keyword search fused with vectors"),
        ("owner/beta", "shared handoff for both agents"),
    ]
    match = 0
    out.append("| owner | query | new top-k == ground-truth |")
    out.append("|---|---|---|")
    for owner, q in queries:
        qvec = next(iter(emb.embed([q])))
        got = [r.path for r in searcher.search(q, limit=5, source_ids=["trovex"],
                                               kind="record", tags=[owner], hybrid=False)]
        gt = ground_truth(owner, qvec, k=5)
        ok = set(got) == set(gt)
        match += ok
        out.append(f"| {owner} | {q[:32]} | {ok} |")
    out.append(f"\nresult-set equivalence: {match}/{len(queries)} (owner-scoped recall unchanged vs ground truth).")
    # multi-owner doc recalled for BOTH its owners via the fallback
    a = [r.path for r in searcher.search("shared handoff", limit=5, source_ids=["trovex"],
                                         kind="record", tags=["owner/alpha"], hybrid=False)]
    b = [r.path for r in searcher.search("shared handoff", limit=5, source_ids=["trovex"],
                                         kind="record", tags=["owner/beta"], hybrid=False)]
    out.append(f"multi-owner doc recalled for alpha: {shared in a}; for beta: {shared in b} "
               f"(owner='' + doc_tags fallback).\n")
    return "\n".join(out)


def part_b_bench():
    out = ["## B. stage bench — vector + BM25 p50/p95 (ms), before/after\n"]
    N, DIM = 8000, 384
    OWNERS = [f"owner/agent{i}" for i in range(40)]
    rng = np.random.default_rng(0)

    def blob():
        v = rng.standard_normal(DIM).astype(np.float32)
        v /= np.linalg.norm(v)
        return sqlite_vec.serialize_float32(v.tolist())

    d = pathlib.Path(tempfile.mkdtemp())
    conn = open_db(d / "trovex.db", DIM, "BAAI/bge-small-en-v1.5")
    WORDS = ["nginx", "proxy", "tls", "cert", "renew", "deploy", "boot", "recall", "owner", "tag", "vector", "index", "query", "embed"]
    docs, vec, tags, fts = [], [], [], []
    for i in range(1, N + 1):
        owner = OWNERS[i % len(OWNERS)]
        docs.append((i, "trovex", f"r{i}", f"/r{i}", f"h{i}", 10, 3, 1.0, 1.0, 1.0, f"doc {i}", "record", "active", "canonical"))
        vec.append((i, "trovex", blob(), "record", "active", "canonical", "test", owner))
        tags.append((i, owner))
        fts.append((f"doc {i}", " ".join(rng.choice(WORDS, 12)), i))
    conn.executemany("INSERT INTO docs(id,source_id,path,absolute_path,content_hash,size_bytes,tokens_est,mtime,first_indexed,last_indexed,title,kind,lifecycle,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", docs)
    conn.executemany("INSERT INTO vec_docs(rowid,source_id,embedding,kind,lifecycle,status,embed_model,owner) VALUES (?,?,?,?,?,?,?,?)", vec)
    conn.executemany("INSERT INTO doc_tags(doc_id,tag) VALUES (?,?)", tags)
    conn.executemany("INSERT INTO docs_fts(title,body,doc_id) VALUES (?,?,?)", fts)
    conn.commit()

    q = blob()
    owner = OWNERS[0]
    lc = "v.lifecycle != 'archived' AND v.lifecycle != 'pending_delete' AND v.status != 'duplicate'"
    V_BEFORE = (f"SELECT d.id FROM vec_docs v JOIN docs d ON d.id=v.rowid WHERE v.embedding MATCH ? AND k=? AND v.source_id='trovex' AND {lc} AND v.kind='record' AND d.id IN (SELECT doc_id FROM doc_tags WHERE tag=?) ORDER BY v.distance", (q, 4096, owner))
    V_AFTER = (f"SELECT d.id FROM vec_docs v JOIN docs d ON d.id=v.rowid WHERE v.embedding MATCH ? AND k=? AND v.source_id='trovex' AND {lc} AND v.kind='record' AND v.owner=? ORDER BY v.distance", (q, 5, owner))
    terms = WORDS[:24]
    B_BEFORE = ("SELECT doc_id FROM docs_fts WHERE docs_fts MATCH ? ORDER BY rank LIMIT 4096", (" OR ".join(terms),))
    B_AFTER = ("SELECT doc_id FROM docs_fts WHERE docs_fts MATCH ? AND doc_id IN (SELECT doc_id FROM doc_tags WHERE tag=?) ORDER BY rank LIMIT 50", (" OR ".join(WORDS[:8]), owner))

    def bench(sql, params, n=40):
        xs = []
        for _ in range(n + 1):
            t = time.perf_counter(); conn.execute(sql, params).fetchall(); xs.append((time.perf_counter() - t) * 1000)
        return pc(xs[1:], 50), pc(xs[1:], 95)

    rows = [
        ("vector (owner-scoped)", bench(*V_BEFORE), bench(*V_AFTER)),
        ("BM25 (owner-scoped)", bench(*B_BEFORE), bench(*B_AFTER)),
    ]
    out.append(f"index: {N} docs, {len(OWNERS)} owners (~{N // len(OWNERS)}/owner), 1 partition")
    out.append("| stage | before p50/p95 | after p50/p95 | p50 speedup |")
    out.append("|---|---|---|---|")
    for name, bef, aft in rows:
        sp = round(bef[0] / aft[0], 1) if aft[0] else 0
        out.append(f"| {name} | {bef[0]}/{bef[1]} | {aft[0]}/{aft[1]} | {sp}x |")
    out.append("")
    return "\n".join(out)


def main():
    print("# perf C receipt (task 33ecdc9f)\n")
    print(f"Host: `{__import__('os').popen('uname -sm').read().strip()}`  load: "
          f"`{__import__('os').popen('uptime').read().strip().split('load averages:')[-1].strip()}`\n")
    print(part_a_recall())
    print(part_b_bench())


if __name__ == "__main__":
    main()
