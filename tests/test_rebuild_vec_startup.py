"""Startup wiring for a settings-level embed_model/dim change (task 6851d755
AC3): on a NON-EMPTY store, server._maybe_enqueue_rebuild_vec must enqueue a
'rebuild_vec' index job instead of letting _migrate_embed_dim run its old
inline wipe.

Tested against the standalone _maybe_enqueue_rebuild_vec function rather than
the full lifespan() context manager: the MCP StreamableHTTPSessionManager it
enters can only ever run() ONCE per process (a hard SDK guard — a second
`async with lifespan(...)` anywhere in the suite raises RuntimeError), and
that one shot is already used by test_usearch_index.py's startup test.
_maybe_enqueue_rebuild_vec is exactly the logic lifespan() calls, factored out
so this doesn't need the MCP machinery at all.

Hermetic: deterministic fixed-vector embedders, no real model/network."""

from __future__ import annotations

import numpy as np

from trovex import db
from trovex.config import Settings
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.server import _maybe_enqueue_rebuild_vec
from trovex.state import AppState
from trovex.store import SqliteStore


class _FixedEmbedder:
    def __init__(self, dim: int, value: float, name: str):
        self.dim = dim
        self.name = name
        self._value = value

    def embed(self, texts):
        for _ in texts:
            v = np.full(self.dim, self._value, dtype=np.float32)
            v /= np.linalg.norm(v)
            yield v


def test_enqueues_rebuild_vec_on_model_change_non_empty_store(tmp_path):
    # Seed a store under model-a — stamps store_meta['embed_model']='model-a'.
    settings_a = Settings(
        data_dir=tmp_path, embed_model="model-a", sources_config_path=tmp_path / "none.yaml"
    )
    embedder_a = _FixedEmbedder(dim=384, value=1.0, name="model-a")
    store_a = SqliteStore(settings_a, embedder=embedder_a)
    store_a.put("# Doc\n\nbody text", tags=["t"])
    assert db.get_store_meta(store_a.db, "embed_model") == "model-a"
    doc_count_before = store_a.db.execute("SELECT COUNT(*) c FROM docs").fetchone()["c"]
    ddl_before = store_a.db.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'vec_docs'"
    ).fetchone()["sql"]
    store_a.db.close()

    # Restart with a DIFFERENT model, SAME dim (the task's own validation
    # scenario — bge-small vs paraphrase-multilingual are both 384-dim, so a
    # pure dim check would never notice this swap at all).
    settings_b = Settings(
        data_dir=tmp_path, embed_model="model-b", sources_config_path=tmp_path / "none.yaml"
    )
    embedder_b = _FixedEmbedder(dim=384, value=2.0, name="model-b")
    state = AppState(
        settings=settings_b,
        embedder=embedder_b,
        searcher=Searcher(settings_b, embedder=embedder_b),
        indexer=Indexer(settings_b, embedder=embedder_b),
        store=SqliteStore(settings_b, embedder=embedder_b),
    )

    # NOT wiped inline by opening the store under the new settings: same DDL,
    # same row count as before restart — this is _migrate_embed_dim's own
    # non-empty-store skip (db.py), already exercised end to end just by
    # constructing `state` above.
    ddl_after = state.indexer.db.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'vec_docs'"
    ).fetchone()["sql"]
    assert ddl_after == ddl_before
    assert state.indexer.db.execute("SELECT COUNT(*) c FROM docs").fetchone()["c"] == doc_count_before

    state.applier.start()
    try:
        enqueued = _maybe_enqueue_rebuild_vec(state)
        assert enqueued is True

        job = state.indexer.db.execute(
            "SELECT kind, state FROM index_jobs WHERE kind = 'rebuild_vec'"
        ).fetchone()
        assert job is not None
        assert job["state"] in ("queued", "processing", "succeeded")
    finally:
        state.applier.stop()


def test_does_not_enqueue_when_model_unchanged(tmp_path):
    settings = Settings(
        data_dir=tmp_path, embed_model="model-a", sources_config_path=tmp_path / "none.yaml"
    )
    embedder = _FixedEmbedder(dim=384, value=1.0, name="model-a")
    store = SqliteStore(settings, embedder=embedder)
    store.put("# Doc\n\nbody text", tags=["t"])
    store.db.close()

    state = AppState(
        settings=settings,
        embedder=embedder,
        searcher=Searcher(settings, embedder=embedder),
        indexer=Indexer(settings, embedder=embedder),
        store=SqliteStore(settings, embedder=embedder),
    )
    state.applier.start()
    try:
        enqueued = _maybe_enqueue_rebuild_vec(state)
        assert enqueued is False
        job = state.indexer.db.execute("SELECT 1 FROM index_jobs WHERE kind = 'rebuild_vec'").fetchone()
        assert job is None
    finally:
        state.applier.stop()


def test_does_not_enqueue_on_a_fresh_empty_store(tmp_path):
    """No prior store at all — nothing to rebuild, _migrate_embed_dim's own
    empty-store wipe already leaves everything consistent."""
    settings = Settings(
        data_dir=tmp_path, embed_model="model-a", sources_config_path=tmp_path / "none.yaml"
    )
    embedder = _FixedEmbedder(dim=384, value=1.0, name="model-a")
    state = AppState(
        settings=settings,
        embedder=embedder,
        searcher=Searcher(settings, embedder=embedder),
        indexer=Indexer(settings, embedder=embedder),
        store=SqliteStore(settings, embedder=embedder),
    )
    state.applier.start()
    try:
        assert _maybe_enqueue_rebuild_vec(state) is False
    finally:
        state.applier.stop()

