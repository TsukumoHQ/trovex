#!/usr/bin/env python3
"""Reproducible token-savings benchmark for trovex.

This is the keystone proof for the "~60% fewer tokens per doc lookup" claim.
It does NOT invent a number — it drives the REAL trovex search over a real repo
and reports the per-lookup savings using trovex's OWN model
(`Searcher.savings_estimate`, the same code path the live dashboard uses).

The model (see src/trovex/savings.py):

    Without trovex, an agent triages a question by Read-ing the top ~3 candidate
    .md files. With trovex, it reads the trovex() pointer line + the 1 canonical
    doc. So per lookup:

        saved  = top3_tokens - top1_tokens - pointer_tokens
        ratio  = saved / top3_tokens

Everything is run against a throwaway index in a temp dir, so the benchmark is
deterministic and leaves no state behind. Anyone can re-run it:

    python benchmarks/token-savings/run.py                 # this repo, local embedder
    python benchmarks/token-savings/run.py --repo /path    # any repo of .md docs
    python benchmarks/token-savings/run.py --json out.json  # machine-readable result

Default embedder is a LOCAL fastembed model (BAAI/bge-small-en-v1.5) so it runs
with no API key and no per-token cost (one-time ~90MB model download on first
run). Pass --model text-embedding-3-large to use OpenAI (needs OPENAI_API_KEY);
the savings ratio is governed by token *volume*, not the embedder, so the
headline number is stable across embedders.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

# Repo root = two levels up from benchmarks/token-savings/run.py
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUERIES = Path(__file__).with_name("queries.txt")


def load_queries(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="trovex token-savings benchmark")
    ap.add_argument("--repo", type=Path, default=REPO_ROOT,
                    help="repo of .md docs to index (default: this repo)")
    ap.add_argument("--queries", type=Path, default=DEFAULT_QUERIES,
                    help="newline-delimited query file (# comments allowed)")
    ap.add_argument("--model", default="BAAI/bge-small-en-v1.5",
                    help="embedder model (local fastembed by default)")
    ap.add_argument("--limit", type=int, default=5,
                    help="results per query (top-3 drive the savings model)")
    ap.add_argument("--json", type=Path, default=None,
                    help="write the full per-query result set as JSON")
    args = ap.parse_args()

    repo = args.repo.expanduser().resolve()
    if not repo.exists():
        print(f"error: repo not found: {repo}", file=sys.stderr)
        return 2
    queries = load_queries(args.queries)
    if not queries:
        print(f"error: no queries in {args.queries}", file=sys.stderr)
        return 2

    # Throwaway, isolated index — deterministic + no side effects on the user's
    # real ~/.trovex-data. env vars are read by Settings (env_prefix TROVEX_).
    tmp = Path(tempfile.mkdtemp(prefix="trovex-bench-"))
    os.environ["TROVEX_DATA_DIR"] = str(tmp)
    os.environ["TROVEX_EMBED_MODEL"] = args.model

    try:
        from trovex.config import Settings
        from trovex.embedder import build_embedder, model_dim
        from trovex.indexer import Indexer
        from trovex.search import Searcher
    except ImportError as e:
        print(f"error: trovex not importable ({e}).\n"
              f"Install it first:  pip install -e .  (from the repo root)", file=sys.stderr)
        return 2

    settings = Settings(data_dir=tmp, embed_model=args.model, embed_dim=model_dim(args.model))
    embedder = build_embedder(settings.embed_model)
    indexer = Indexer(settings, embedder=embedder)

    print(f"indexing {repo} (.md/.mdx/.markdown) into a throwaway index…", file=sys.stderr)
    idx = indexer.reindex(root=repo)
    n_docs = idx.get("added", 0) + idx.get("updated", 0) + idx.get("unchanged", 0)
    if not n_docs:
        print(f"error: indexed 0 docs under {repo} — nothing to benchmark", file=sys.stderr)
        return 2

    searcher = Searcher(settings, embedder=embedder)

    rows = []
    for q in queries:
        results = searcher.search(q, limit=args.limit)
        est = searcher.savings_estimate(results)
        if not est:
            rows.append({"query": q, "results": 0, "skipped": "no results"})
            continue
        rows.append({
            "query": q,
            "results": len(results),
            "top_doc": results[0].path,
            "would_have_read": est["would_have_read"],
            "actual_read": est["actual_read"],
            "response": est["response"],
            "saved": est["saved"],
            "ratio": round(est["ratio"], 4),
        })

    scored = [r for r in rows if "ratio" in r]
    if not scored:
        print("error: every query returned no results — check the repo/queries", file=sys.stderr)
        return 2

    ratios = [r["ratio"] for r in scored]
    total_whr = sum(r["would_have_read"] for r in scored)
    total_saved = sum(r["saved"] for r in scored)
    pooled = total_saved / total_whr if total_whr else 0.0
    median = statistics.median(ratios)
    mean = statistics.fmean(ratios)

    # ---- report -------------------------------------------------------------
    print()
    print(f"trovex token-savings benchmark  ·  repo={repo.name}  ·  model={args.model}")
    print(f"corpus: {n_docs} docs indexed  ·  queries: {len(scored)}/{len(queries)} returned results")
    print()
    qw = min(46, max(len(r["query"]) for r in scored))
    print(f"  {'query':<{qw}}  {'top3':>6}  {'top1':>6}  {'ptr':>4}  {'saved':>6}  {'ratio':>6}")
    print(f"  {'-' * qw}  {'-'*6}  {'-'*6}  {'-'*4}  {'-'*6}  {'-'*6}")
    for r in scored:
        qd = (r["query"][:qw - 1] + "…") if len(r["query"]) > qw else r["query"]
        print(f"  {qd:<{qw}}  {r['would_have_read']:>6}  {r['actual_read']:>6}  "
              f"{r['response']:>4}  {r['saved']:>6}  {r['ratio'] * 100:>5.0f}%")
    print()
    print(f"  per-lookup savings (median) : {median * 100:.0f}%   ← headline")
    print(f"  per-lookup savings (mean)   : {mean * 100:.0f}%")
    print(f"  pooled (Σsaved / Σtop3)     : {pooled * 100:.0f}%")
    print(f"  total tokens: would-read {total_whr:,} → saved {total_saved:,}")
    print()

    if args.json:
        payload = {
            "repo": str(repo),
            "model": args.model,
            "docs_indexed": n_docs,
            "queries_total": len(queries),
            "queries_scored": len(scored),
            "median_ratio": round(median, 4),
            "mean_ratio": round(mean, 4),
            "pooled_ratio": round(pooled, 4),
            "total_would_have_read": total_whr,
            "total_saved": total_saved,
            "per_query": rows,
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
