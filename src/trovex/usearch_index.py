"""Per-partition usearch (HNSW) escape hatch — the adapter capacity.py
documents but defers building until a partition actually crosses the
sqlite-vec brute-force ceiling (task 4c89b89a; 'trovex' crossed it 2.4x:
9969 vec_chunks vs the hard k=4096 cap).

sqlite-vec's `k = ?` in a MATCH query is capped at 4096 (a hard limit, not a
soft one — asking for more raises `k value in knn query too large`). A
tag-scoped query needs to consider EVERY chunk in the partition (tags are
post-filtered, not a vec0 column), so once a partition's chunk count passes
4096 that query can no longer see the whole partition in one sqlite-vec KNN —
chunks ranked past the cutoff are silently unreachable, no matter their tag.
Measured on the real 'trovex' partition (9969 chunks): a boot-style query
found only 42/194 (22%) of one agent's own owner-tagged chunks inside the
top-4096 — the other 78% could never surface via search_chunks(tags=...),
regardless of --limit. See the task result for the full repro.

usearch (HNSW, approximate) has no such k ceiling and, measured against true
sqlite-vec brute force on the same real partition, top-10 overlap was 10/10
on every sampled query — comfortably clearing the >=0.9 equivalence bar this
module is tested against (see tests/test_usearch_index.py).

Opt-in and per-partition (Settings.usearch_partitions / env
TROVEX_USEARCH_PARTITIONS, JSON list of source_ids). `usearch` itself is an
optional dependency — `available()` is False when it's not installed, and
every caller must fall back to sqlite-vec unchanged in that case. Default
empty partitions list = sqlite-vec everywhere, zero behavior change.
"""

from __future__ import annotations

import logging
import sqlite3
import threading

import numpy as np

log = logging.getLogger(__name__)

try:
    from usearch.index import Index as _Index
except ImportError:  # optional dep absent — the whole module is a no-op
    _Index = None


def available() -> bool:
    return _Index is not None


class PartitionIndex:
    """An in-memory HNSW index over ONE partition's vectors, rebuilt wholesale
    (never incrementally patched) each time `build()` is called — cheap next
    to a reindex, and it keeps this seam free of delete/update bookkeeping.
    """

    def __init__(self, dim: int):
        if _Index is None:
            raise RuntimeError("usearch is not installed (pip install usearch)")
        self._dim = dim
        self._lock = threading.Lock()
        self._index = _Index(ndim=dim, metric="cos")
        self._size = 0

    def build(self, rows: list[tuple[int, bytes]]) -> None:
        """rows: [(rowid, embedding_blob), ...], the sqlite_vec-serialized
        float32 blob straight from a vec0 column. Replaces the index."""
        idx = _Index(ndim=self._dim, metric="cos")
        if rows:
            keys = np.array([r[0] for r in rows], dtype=np.int64)
            vecs = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.float32).reshape(
                len(rows), self._dim
            )
            idx.add(keys, vecs)
        with self._lock:
            self._index = idx
            self._size = len(rows)

    def __len__(self) -> int:
        with self._lock:
            return self._size

    def search(self, query_blob: bytes, k: int) -> list[tuple[int, float]]:
        """Nearest-first [(rowid, distance), ...]; distance = cosine distance
        (1 - cosine similarity), the same sense sqlite-vec's `cos` metric
        reports so callers can treat the two sources interchangeably."""
        with self._lock:
            idx, size = self._index, self._size
        if size == 0:
            return []
        vec = np.frombuffer(query_blob, dtype=np.float32)
        matches = idx.search(vec, min(k, size))
        return list(zip(matches.keys.tolist(), matches.distances.tolist(), strict=True))


# Registry of live indexes, keyed "{table}:{source_id}" — a process-wide cache
# so a rebuild (after reindex, or at startup) is visible to every request
# without threading a handle through the whole call chain.
_indexes: dict[str, PartitionIndex] = {}
_indexes_lock = threading.Lock()


def _key(table: str, source_id: str) -> str:
    return f"{table}:{source_id}"


def get_index(table: str, source_id: str) -> PartitionIndex | None:
    """The live index for (table, source_id), or None if it was never built
    (dep absent, partition not flagged, or build() not called yet) — callers
    treat None as 'fall back to sqlite-vec', never as an error."""
    with _indexes_lock:
        return _indexes.get(_key(table, source_id))


def rebuild_partition(db: sqlite3.Connection, table: str, source_id: str, dim: int) -> int:
    """(Re)build the in-memory index for one partition from its vec table.
    Returns the row count indexed (0 and a no-op when usearch isn't
    installed). Safe to call repeatedly — after every reindex of a flagged
    partition, and once at server startup for each configured partition."""
    if not available():
        return 0
    # Static SQL per table (no interpolated table name — same pattern as
    # capacity.partition_counts, keeps the security guard happy and `table` is
    # never user input anyway, only ever the two literals below).
    if table == "vec_docs":
        cur = db.execute("SELECT rowid, embedding FROM vec_docs WHERE source_id = ?", (source_id,))
    elif table == "vec_chunks":
        cur = db.execute("SELECT rowid, embedding FROM vec_chunks WHERE source_id = ?", (source_id,))
    else:
        raise ValueError(f"unknown vec table {table!r}")  # a caller bug, not reachable in practice
    rows = [(r["rowid"], r["embedding"]) for r in cur]
    idx = PartitionIndex(dim)
    idx.build(rows)
    with _indexes_lock:
        _indexes[_key(table, source_id)] = idx
    log.info("usearch: rebuilt %s index for partition %r (%d vectors)", table, source_id, len(rows))
    return len(rows)
