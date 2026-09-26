"""/api/stats carries per-partition capacity numbers (task 4c89b89a AC3) —
docs, chunks, ceiling ratio, and whether the partition is on the usearch
escape hatch. Also pins capacity.capacity_report/log_capacity_warnings'
usearch_partitions exclusion (a partition on HNSW no longer trips the
chunk-ceiling warning — that's the risk the index resolves).

Hermetic: BagEmbedder, no network, no real model download.
"""

from __future__ import annotations

import hashlib
import logging
import re

import numpy as np
import sqlite_vec
from fastapi.testclient import TestClient

from trovex import capacity
from trovex import state as state_mod
from trovex.config import Settings
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.server import build_app
from trovex.state import AppState
from trovex.store import SqliteStore

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


def _seed_partition(db, source_id: str, n: int) -> None:
    """n synthetic vec_chunks rows on source_id, no parent docs needed — this
    module only exercises capacity's grouped COUNT and the /api/stats read
    path, neither of which joins back to docs/chunks."""
    rng = np.random.default_rng(hash(source_id) % (2**31))
    for i in range(n):
        v = rng.normal(size=DIM).astype(np.float32)
        v /= np.linalg.norm(v)
        blob = sqlite_vec.serialize_float32(v.tolist())
        db.execute(
            "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status) "
            "VALUES (?, ?, ?, '', 'active', 'canonical')",
            (i + 1 + hash(source_id) % 1_000_000, source_id, blob),
        )
    db.commit()


def test_api_stats_carries_per_partition_capacity(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "none.yaml",
        usearch_partitions=["hot"],
    )
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)
    _seed_partition(store.db, "hot", 4200)  # past the 4096 ceiling, flagged
    _seed_partition(store.db, "cold", 10)  # small, unflagged

    state_mod._state = AppState(
        settings=settings,
        embedder=embedder,
        searcher=Searcher(settings, embedder=embedder),
        indexer=Indexer(settings, embedder=embedder),
        store=store,
    )
    try:
        client = TestClient(build_app())
        r = client.get("/api/stats")
        assert r.status_code == 200
        body = r.json()
        assert "capacity" in body
        by_source = {row["source_id"]: row for row in body["capacity"]}

        hot = by_source["hot"]
        assert hot["chunks"] == 4200
        assert hot["ceiling_ratio"] == round(4200 / capacity.VEC0_K_CEILING, 3)
        assert hot["usearch"] is True

        cold = by_source["cold"]
        assert cold["chunks"] == 10
        assert cold["usearch"] is False
    finally:
        state_mod.reset_state()


def test_capacity_report_skips_ceiling_warning_for_usearch_partition(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "none.yaml",
    )
    store = SqliteStore(settings, embedder=BagEmbedder())
    _seed_partition(store.db, "trovex", 4200)

    unflagged = capacity.capacity_report(store.db)
    assert any(w["source_id"] == "trovex" for w in unflagged)  # warns by default

    flagged = capacity.capacity_report(store.db, usearch_partitions=["trovex"])
    assert not any(w["source_id"] == "trovex" for w in flagged)  # HNSW covers it


def test_log_capacity_warnings_respects_usearch_partitions(tmp_path, caplog):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "none.yaml",
    )
    store = SqliteStore(settings, embedder=BagEmbedder())
    _seed_partition(store.db, "trovex", 4200)

    with caplog.at_level(logging.WARNING):
        n = capacity.log_capacity_warnings(store.db, usearch_partitions=["trovex"])
    assert n == 0
    assert not any("trovex" in r.message for r in caplog.records)
