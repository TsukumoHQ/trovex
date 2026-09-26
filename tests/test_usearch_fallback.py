"""The sqlite-vec fallback when `usearch` is absent (task 52532317). Forces the
absent path via monkeypatch — independent of whether the optional dep is
actually installed in this environment — so it's the one usearch-adjacent test
that always runs, proving the fallback works on a plain `uv sync` (no extras)
checkout without needing CI to run twice."""

from __future__ import annotations

import numpy as np
import pytest

from trovex import usearch_index
from trovex.config import Settings
from trovex.store import SqliteStore

DIM = 384


class _TinyEmbedder:
    name = "tiny"
    dim = DIM

    def embed(self, texts):
        for t in texts:
            v = np.zeros(DIM, dtype=np.float32)
            v[abs(hash(t)) % DIM] = 1.0
            yield v


@pytest.fixture(autouse=True)
def _reset_registry():
    usearch_index._indexes.clear()
    yield
    usearch_index._indexes.clear()


def test_available_is_false_when_usearch_unimportable(monkeypatch):
    monkeypatch.setattr(usearch_index, "_Index", None)
    assert usearch_index.available() is False


def test_rebuild_partition_is_a_noop_when_usearch_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(usearch_index, "_Index", None)
    from trovex.db import open_db

    db = open_db(tmp_path / "trovex.db", DIM)
    n = usearch_index.rebuild_partition(db, "vec_chunks", "trovex", DIM)
    assert n == 0
    assert usearch_index.get_index("vec_chunks", "trovex") is None


def test_search_chunks_falls_back_to_sqlite_vec_for_a_flagged_partition(monkeypatch, tmp_path):
    """The whole point of `available()`-gating: a partition FLAGGED for usearch
    (Settings.usearch_partitions) still answers correctly from sqlite-vec brute
    force when the optional dep isn't there — never a hard failure, never a
    silent empty result."""
    monkeypatch.setattr(usearch_index, "_Index", None)
    assert usearch_index.available() is False

    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "none.yaml",
        usearch_partitions=["trovex"],  # flagged, but the dep is "absent"
    )
    store = SqliteStore(settings, embedder=_TinyEmbedder())
    doc_id = store.put("# Flagged\n\nhnsw partition marker content", tags=["t"])

    n = usearch_index.rebuild_partition(store.db, "vec_chunks", "trovex", settings.resolved_embed_dim())
    assert n == 0
    assert usearch_index.get_index("vec_chunks", "trovex") is None

    hits = store.search_chunks("marker content", limit=5, source="trovex", tags=["t"])
    assert any(h["path"] == doc_id for h in hits)  # served via sqlite-vec, unaffected
