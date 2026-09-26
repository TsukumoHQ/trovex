"""db.rebuild_vec_shadow (task 6851d755): a model/dim change is swapped in
without ever holding a write lock for the expensive part (the embedder
calls), and a concurrent reader on a SEPARATE connection sees a consistent
snapshot — the OLD tables throughout the rebuild, the NEW ones only once the
final (short, mechanical) swap transaction commits, never a torn read.

Hermetic: deterministic fixed-vector embedders, no real model/network."""

from __future__ import annotations

import re
import threading
import time

import numpy as np

from trovex import db
from trovex.config import Settings
from trovex.store import SqliteStore


class _FixedEmbedder:
    """Every text embeds to the SAME unit vector — deterministic, no model."""

    def __init__(self, dim: int, value: float, name: str):
        self.dim = dim
        self.name = name
        self._value = value

    def embed(self, texts):
        for _ in texts:
            v = np.full(self.dim, self._value, dtype=np.float32)
            v /= np.linalg.norm(v)
            yield v


def _vec_dim(conn, table: str) -> int:
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()["sql"]
    return int(re.search(r"float\[(\d+)\]", ddl).group(1))


def test_rebuild_vec_shadow_builds_shadow_and_swaps(tmp_path):
    settings = Settings(
        data_dir=tmp_path, embed_model="old-model", sources_config_path=tmp_path / "none.yaml"
    )
    old = _FixedEmbedder(dim=384, value=1.0, name="old-model")
    store = SqliteStore(settings, embedder=old)
    store.put("# Doc one\n\nfirst body", tags=["t"])
    store.put("# Doc two\n\nsecond body, a bit longer than the first one", tags=["t"])
    n_docs_before = store.db.execute("SELECT COUNT(*) c FROM docs").fetchone()["c"]
    n_chunks_before = store.db.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
    assert n_docs_before == 2 and n_chunks_before >= 2

    new = _FixedEmbedder(dim=8, value=2.0, name="new-model")
    result = db.rebuild_vec_shadow(store.db, new, 8, batch_size=1)

    assert result["docs"] == n_docs_before
    assert result["chunks"] == n_chunks_before
    assert _vec_dim(store.db, "vec_docs") == 8
    assert _vec_dim(store.db, "vec_chunks") == 8

    row = store.db.execute("SELECT embed_model FROM vec_docs LIMIT 1").fetchone()
    assert row["embed_model"] == "new-model"
    crow = store.db.execute("SELECT embed_model FROM vec_chunks LIMIT 1").fetchone()
    assert crow["embed_model"] == "new-model"

    # Every doc/chunk still has a live vector row — nothing silently dropped.
    assert store.db.execute("SELECT COUNT(*) c FROM vec_docs").fetchone()["c"] == n_docs_before
    assert store.db.execute("SELECT COUNT(*) c FROM vec_chunks").fetchone()["c"] == n_chunks_before

    assert db.get_store_meta(store.db, "embed_model") == "new-model"


def test_rebuild_vec_shadow_never_blocks_a_concurrent_reader_and_swaps_atomically(tmp_path, monkeypatch):
    """The core AC: a reader on a SEPARATE connection must (1) never be
    blocked while the rebuild's embedder calls run, (2) see the OLD table
    (dim) throughout that phase, and (3) see the NEW table only after the
    whole call returns — never a partially-swapped or errored read at any
    point."""
    settings = Settings(
        data_dir=tmp_path, embed_model="old-model", sources_config_path=tmp_path / "none.yaml"
    )
    old = _FixedEmbedder(dim=384, value=1.0, name="old-model")
    store = SqliteStore(settings, embedder=old)
    store.put("# Doc\n\nbody text for the reader-consistency check", tags=["t"])

    # A second, independent connection — simulates a live Searcher/reader.
    reader = db.open_db(tmp_path / "trovex.db", 384, "old-model")
    assert _vec_dim(reader, "vec_docs") == 384

    new = _FixedEmbedder(dim=16, value=3.0, name="new-model")
    mid_rebuild = threading.Event()
    real_embed = new.embed

    def _slow_embed(texts):
        mid_rebuild.set()
        time.sleep(0.3)
        yield from real_embed(texts)

    monkeypatch.setattr(new, "embed", _slow_embed)

    result: dict = {}

    def _run():
        result["stats"] = db.rebuild_vec_shadow(store.db, new, 16)

    thread = threading.Thread(target=_run)
    t0 = time.perf_counter()
    thread.start()
    assert mid_rebuild.wait(timeout=5.0), "rebuild never reached the embedder call"

    # Mid-rebuild: the reader's own read must be immediate (no lock held for
    # the embedder call) and see the OLD dim — vec_docs hasn't been touched
    # yet, only staged.
    read_t0 = time.perf_counter()
    dim_during = _vec_dim(reader, "vec_docs")
    read_elapsed = time.perf_counter() - read_t0
    assert dim_during == 384
    assert read_elapsed < 0.2, f"reader waited {read_elapsed:.2f}s — the embedder call held a lock"

    thread.join(timeout=10.0)
    total_elapsed = time.perf_counter() - t0
    assert not thread.is_alive()
    assert total_elapsed > 0.25, "the sleep never actually happened — test isn't exercising anything"
    assert result["stats"]["docs"] == 1

    # After the swap: the SAME reader connection now sees the NEW dim.
    assert _vec_dim(reader, "vec_docs") == 16
    reader.close()


def test_rebuild_vec_shadow_skips_a_doc_whose_file_vanished(tmp_path):
    """A file-backed doc whose absolute_path no longer exists must be skipped
    (logged, not raised) — the rest of the rebuild completes."""
    settings = Settings(
        data_dir=tmp_path, embed_model="old-model", sources_config_path=tmp_path / "none.yaml"
    )
    old = _FixedEmbedder(dim=384, value=1.0, name="old-model")
    store = SqliteStore(settings, embedder=old)
    store.put("# Owned\n\nan owned doc, content lives in the db row")

    missing_path = tmp_path / "gone.md"
    store.db.execute(
        "INSERT INTO docs (source_id, path, absolute_path, content_hash, size_bytes, "
        "tokens_est, mtime, first_indexed, last_indexed, title) "
        "VALUES ('code', 'gone.md', ?, 'h', 1, 1, 0, 0, 0, 'Gone')",
        (str(missing_path),),
    )
    store.db.commit()
    assert not missing_path.exists()

    new = _FixedEmbedder(dim=8, value=2.0, name="new-model")
    result = db.rebuild_vec_shadow(store.db, new, 8)

    assert result["docs"] == 2  # both doc rows counted...
    # ...but only the owned one actually made it into vec_docs.
    assert store.db.execute("SELECT COUNT(*) c FROM vec_docs").fetchone()["c"] == 1


def test_rebuild_vec_needed_detects_same_dim_model_swap(tmp_path):
    """The task's own validation scenario: bge-small-en-v1.5 and
    paraphrase-multilingual-MiniLM-L12-v2 are BOTH 384-dim, so a pure dim
    check would never see this swap — store_meta['embed_model'] must."""
    settings = Settings(
        data_dir=tmp_path, embed_model="model-a", sources_config_path=tmp_path / "none.yaml"
    )
    embedder = _FixedEmbedder(dim=384, value=1.0, name="model-a")
    store = SqliteStore(settings, embedder=embedder)
    store.put("# Doc\n\nbody")
    assert db.get_store_meta(store.db, "embed_model") == "model-a"

    assert db.rebuild_vec_needed(store.db, embed_dim=384, embed_model="model-a") is False
    assert db.rebuild_vec_needed(store.db, embed_dim=384, embed_model="model-b") is True


def test_rebuild_vec_needed_false_on_empty_store(tmp_path):
    conn = db.open_db(tmp_path / "trovex.db", 384, "model-a")
    assert db.rebuild_vec_needed(conn, embed_dim=384, embed_model="model-b") is False
