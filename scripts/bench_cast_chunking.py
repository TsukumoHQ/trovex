"""Bench: cAST code chunking vs naive (line/paragraph) chunking on trovex's own
code corpus. Per cto's ruling on 9299f37d: bench numbers on OUR corpus are
mandatory in the PR, not just the cAST paper's cited +4.3 Recall@5.

Corpus: src/trovex/*.py (this repo's own backend). Baseline chunker: feed a
.py file through chunk_markdown (paragraph-window split, no AST awareness —
what happens today if code were chunked at all). Same real embedder both
sides (Settings default), so the only variable is chunk boundaries.

Run: uv run python scripts/bench_cast_chunking.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from trovex.chunking import chunk_markdown  # noqa: E402
from trovex.chunking_code import chunk_code  # noqa: E402
from trovex.config import Settings  # noqa: E402
from trovex.embedder import embedder_from_settings  # noqa: E402

REPO_SRC = Path(__file__).resolve().parent.parent / "src" / "trovex"

# Held-out query set: real "where is X" / "how does Y work" questions against
# this repo's own symbols, confirmed to exist by direct grep before writing
# this bench (see PR body for the grep transcript).
QUERIES = [
    ("how does write authorization check the token for admin API writes", "server.py", "_write_authorized"),
    ("greedy merge AST chunks by token budget for code chunking", "chunking_code.py", "_merge_siblings"),
    ("compute doc lifecycle status and preserve superseded docs during reindex", "status.py", "compute_status"),
    ("hybrid chunk retrieval reciprocal rank fusion vector and BM25", "store.py", "search_chunks"),
    ("content-addressed Merkle incremental chunk sync reuse by hash", "db.py", "sync_doc_chunks"),
    ("collapse ephemeral numbered owner forks and tombstone the lower", "store.py", "_collapse_ephemeral_owners_locked"),
    ("reset lifecycle to active on write to resurrect an archived doc", "store.py", "put"),
    ("detect a duplicate doc via nearest neighbour vector search", "status.py", "detect_duplicate_for"),
    ("rate limit the write endpoints with slowapi", "server.py", "write_limit"),
    ("extract a title from a code file's filename fallback", "indexer.py", "_extract_title"),
    ("CLI command to backfill chunk embeddings for every doc", "cli.py", "backfill_chunks"),
    ("cache eviction put a value with a byte budget", "cache.py", "put"),
]


def _chunk_file(path: Path, use_cast: bool) -> list[tuple[str, str, str]]:
    """Returns (file, breadcrumb, embed_text) triples for one file."""
    content = path.read_text(encoding="utf-8", errors="replace")
    chunks = chunk_code(content, "python") if use_cast else chunk_markdown(content)
    out = []
    for ch in chunks:
        bc = " > ".join(ch.heading_path) or path.name
        out.append((path.name, bc, ch.embed_text(path.name)))
    return out


def _cosine_topk(query_vec: np.ndarray, mat: np.ndarray, k: int) -> list[int]:
    sims = mat @ query_vec
    return list(np.argsort(-sims)[:k])


def run() -> None:
    settings = Settings()
    embedder = embedder_from_settings(settings)
    files = sorted(REPO_SRC.glob("*.py"))
    print(f"corpus: {len(files)} files under {REPO_SRC}")

    for label, use_cast in (("baseline (chunk_markdown on .py)", False), ("cAST (chunk_code)", True)):
        triples: list[tuple[str, str, str]] = []
        for f in files:
            triples.extend(_chunk_file(f, use_cast))
        embed_texts = [t[2] for t in triples]
        mat = np.array(list(embedder.embed(embed_texts)), dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = mat / norms

        hits_at_1 = 0
        hits_at_5 = 0
        for query, target_file, target_symbol in QUERIES:
            qvec = np.array(next(iter(embedder.embed([query]))), dtype=np.float32)
            qn = np.linalg.norm(qvec) or 1.0
            qvec = qvec / qn
            top5 = _cosine_topk(qvec, mat, 5)

            def is_correct(
                i: int, triples=triples, target_file=target_file, target_symbol=target_symbol
            ) -> bool:
                fname, _bc, text = triples[i]
                return fname == target_file and target_symbol in text

            if is_correct(top5[0]):
                hits_at_1 += 1
            if any(is_correct(i) for i in top5):
                hits_at_5 += 1

        n = len(QUERIES)
        print(
            f"  {label:35s} chunks={len(triples):4d} "
            f"hit@1={hits_at_1}/{n} ({hits_at_1 / n:.2f})  "
            f"recall@5={hits_at_5}/{n} ({hits_at_5 / n:.2f})"
        )


if __name__ == "__main__":
    run()
