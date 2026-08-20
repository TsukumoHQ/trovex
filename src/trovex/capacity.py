"""Scale-headroom observability for the partitioned vec0 store (P3).

The store is brute-force KNN: every query scans its source_id partition end to
end. P2a made that safe by bounding each partition (one shard per source), and
sqlite-vec caps a single KNN `k` at 4096. This module WATCHES that headroom so a
partition approaching the brute-force ceiling is visible BEFORE it hurts, and
documents the drop-in upgrade path.

## Escape hatch — swapping a hot partition to usearch (HNSW)

When one partition genuinely outgrows brute force (owned chunks nearing 4096, or
a file source approaching ~1e5 vectors), the drop-in upgrade is `usearch`
(a single-header C++ HNSW index, `pip install usearch`, fully OFFLINE — no
network, no service). The seam is per-partition and opt-in:

  1. `pip install usearch` (optional dep; absent = this stays a no-op).
  2. Add the source_id to `Settings.usearch_partitions` (env
     TROVEX_USEARCH_PARTITIONS, JSON list). Default empty = sqlite-vec everywhere.
  3. A flagged partition builds an in-memory usearch HNSW index from its
     `vec_docs`/`vec_chunks` rows and serves ANN KNN for that partition only;
     every other partition stays on sqlite-vec brute force.

This keeps the default path unchanged (offline-first, zero new deps) and turns
the index strategy into a per-partition choice, not a global rewrite. The
backend adapter itself is intentionally NOT built until a partition actually
crosses the threshold — `capacity_report` is what tells you when that day comes.
"""

from __future__ import annotations

import logging
import sqlite3

log = logging.getLogger(__name__)

# sqlite-vec's hard per-KNN `k` ceiling — an owned partition whose chunk count
# approaches this can no longer be scanned in one KNN (the P0 outage class).
VEC0_K_CEILING = 4096
# Soft advisory limit for a brute-force partition's vector count: past this,
# per-query latency on that shard is worth the usearch upgrade.
BRUTE_FORCE_SOFT_LIMIT = 100_000
# Fraction of a limit at which to start warning (headroom before the wall).
WARN_FRACTION = 0.8


def partition_counts(db: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Per-partition vector counts: {source_id: {"docs": n, "chunks": m}}.

    Reads the vec0 tables directly (the KNN's actual working set), not `docs` —
    a store-only doc has a `docs` row but no vector, and should not count toward
    KNN pressure."""
    out: dict[str, dict[str, int]] = {}
    # Static SQL per table (no interpolated table name — keeps the security guard
    # happy and there's no user input here anyway).
    for r in db.execute("SELECT source_id, COUNT(*) AS n FROM vec_docs GROUP BY source_id"):
        out.setdefault(r["source_id"], {"docs": 0, "chunks": 0})["docs"] = r["n"]
    for r in db.execute("SELECT source_id, COUNT(*) AS n FROM vec_chunks GROUP BY source_id"):
        out.setdefault(r["source_id"], {"docs": 0, "chunks": 0})["chunks"] = r["n"]
    return out


def capacity_report(db: sqlite3.Connection) -> list[dict]:
    """Partitions at or near a capacity limit. Empty when everything has headroom.

    Each entry: {source_id, docs, chunks, reason, ratio}. `reason` names the limit
    being approached; `ratio` is how close (1.0 = at the limit)."""
    warnings: list[dict] = []
    for src, c in partition_counts(db).items():
        docs, chunks = c["docs"], c["chunks"]
        # Owned chunks approaching the hard vec0 KNN ceiling — the sharpest edge.
        if chunks >= VEC0_K_CEILING * WARN_FRACTION:
            warnings.append(
                {
                    "source_id": src,
                    "docs": docs,
                    "chunks": chunks,
                    "reason": "chunks near vec0 KNN ceiling (4096)",
                    "ratio": round(chunks / VEC0_K_CEILING, 3),
                }
            )
        # A big file-source partition approaching the brute-force soft limit.
        elif docs >= BRUTE_FORCE_SOFT_LIMIT * WARN_FRACTION:
            warnings.append(
                {
                    "source_id": src,
                    "docs": docs,
                    "chunks": chunks,
                    "reason": "docs near brute-force soft limit (100k)",
                    "ratio": round(docs / BRUTE_FORCE_SOFT_LIMIT, 3),
                }
            )
    return warnings


def log_capacity_warnings(db: sqlite3.Connection) -> int:
    """Emit a WARN per near-capacity partition; return the count. Safe to call on
    any hot path — a single grouped COUNT, and silent when there's headroom."""
    warnings = capacity_report(db)
    for w in warnings:
        log.warning(
            "partition %r at %.0f%% of capacity (%s): %d docs / %d chunks — "
            "consider the usearch escape hatch (see trovex/capacity.py)",
            w["source_id"],
            w["ratio"] * 100,
            w["reason"],
            w["docs"],
            w["chunks"],
        )
    return len(warnings)
