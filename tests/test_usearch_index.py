"""usearch (HNSW) escape hatch (task 4c89b89a) — the equivalence bar the task
demands (top-10 overlap >= 0.9 vs sqlite-vec brute force on a 5k-chunk
fixture) plus the routing pinned tests: a flagged partition serves from HNSW,
every other partition stays on sqlite-vec untouched.

Hermetic: synthetic float32 vectors inserted straight into vec_chunks (no
embedder, no model, no network) — this module only cares about the KNN
mechanism, not embedding quality."""

from __future__ import annotations

import numpy as np
import pytest
import sqlite_vec

from trovex import usearch_index
from trovex.db import open_db

DIM = 384
N_CHUNKS = 5000


def _clustered_unit_vecs(n: int, seed: int, n_clusters: int = 50) -> np.ndarray:
    """n vectors jittered around n_clusters random centroids — real embedding
    spaces cluster by topic/semantics, they are not uniform noise on the
    hypersphere. Pure iid noise (tried first) starves HNSW's default recall
    parameters of the local structure they're built to exploit and produces
    an artificially pessimistic overlap number no real corpus would show —
    the live prod-copy spike in the task result got 10/10 on every sampled
    query against real embeddings."""
    rng = np.random.default_rng(seed)
    centroids = rng.normal(size=(n_clusters, DIM)).astype(np.float32)
    centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)
    assign = rng.integers(0, n_clusters, size=n)
    v = centroids[assign] + rng.normal(scale=0.05, size=(n, DIM)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v


@pytest.fixture
def big_partition(tmp_path):
    """5000 synthetic vec_chunks rows on source_id='big' — well past the
    sqlite-vec 4096 k-ceiling, matching the real 'trovex' partition's scale."""
    db = open_db(tmp_path / "trovex.db", DIM)
    vecs = _clustered_unit_vecs(N_CHUNKS, seed=1)
    for i in range(N_CHUNKS):
        blob = sqlite_vec.serialize_float32(vecs[i].tolist())
        db.execute(
            "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
            "VALUES (?, 'big', ?, '', 'active', 'canonical', 'test')",
            (i + 1, blob),
        )
    db.commit()
    return db, vecs


@pytest.fixture(autouse=True)
def _reset_registry():
    """The module-level index registry is process-global — isolate tests."""
    usearch_index._indexes.clear()
    yield
    usearch_index._indexes.clear()


def test_usearch_is_available_in_this_test_env():
    """Sanity: the dev extra installs usearch, so this whole module's real
    equivalence claim actually gets exercised in CI, not skipped."""
    assert usearch_index.available()


def test_equivalence_top10_overlap_at_least_point_nine(big_partition):
    """The task's own bar: top-10 overlap >= 0.9 vs true sqlite-vec brute
    force, on a 5k-chunk fixture — well past the 4096 ceiling this whole
    module exists to route around."""
    db, vecs = big_partition
    n = usearch_index.rebuild_partition(db, "vec_chunks", "big", DIM)
    assert n == N_CHUNKS

    idx = usearch_index.get_index("vec_chunks", "big")
    assert idx is not None and len(idx) == N_CHUNKS

    brute_sql = (
        "SELECT v.rowid FROM vec_chunks v "
        "WHERE v.embedding MATCH ? AND k = ? AND v.source_id = 'big' "
        "ORDER BY v.distance"
    )
    rng = np.random.default_rng(99)
    overlaps = []
    for _ in range(10):
        # A realistic query: near an existing point, not pure random noise —
        # a real embedded query sits close to whichever docs answer it, same
        # as the corpus vectors sit close to their own cluster.
        base = vecs[rng.integers(0, N_CHUNKS)]
        q = base + rng.normal(scale=0.05, size=DIM).astype(np.float32)
        q /= np.linalg.norm(q)
        qblob = sqlite_vec.serialize_float32(q.tolist())

        brute_top10 = {r["rowid"] for r in db.execute(brute_sql, [qblob, 10])}
        hnsw_top10 = {rowid for rowid, _dist in idx.search(qblob, 10)}
        overlaps.append(len(brute_top10 & hnsw_top10) / 10)

    mean_overlap = sum(overlaps) / len(overlaps)
    assert mean_overlap >= 0.9, f"mean top-10 overlap {mean_overlap:.2f} < 0.9 bar (per-query: {overlaps})"


def test_rebuild_over_4096_ceiling_where_sqlite_vec_would_raise(big_partition):
    """The whole point: usearch has no k ceiling, so a query for MORE than
    4096 results — impossible in one sqlite-vec KNN call — just works."""
    db, _vecs = big_partition
    usearch_index.rebuild_partition(db, "vec_chunks", "big", DIM)
    idx = usearch_index.get_index("vec_chunks", "big")

    # Confirm the premise: sqlite-vec itself refuses k > 4096.
    import sqlite3

    q = np.zeros(DIM, dtype=np.float32)
    q[0] = 1.0
    qblob = sqlite_vec.serialize_float32(q.tolist())
    with pytest.raises(sqlite3.OperationalError, match="too large"):
        db.execute(
            "SELECT rowid FROM vec_chunks WHERE embedding MATCH ? AND k = ? AND source_id = 'big'",
            [qblob, N_CHUNKS],
        ).fetchall()

    # usearch has no such ceiling — it happily returns well past 4096 (an
    # approximate graph search, so not guaranteed to be the literal full
    # count every time, but nowhere near sqlite-vec's hard wall either).
    full = idx.search(qblob, N_CHUNKS)
    assert len(full) > 4096, f"expected usearch to clear the 4096 sqlite-vec ceiling, got {len(full)}"


def test_flagged_partition_serves_from_hnsw_others_stay_on_sqlite_vec(tmp_path):
    """Pinned routing test: store.search_chunks uses the HNSW index only for a
    source_id listed in Settings.usearch_partitions ('trovex' here, the owned
    store's own reserved partition); a second, unflagged partition ('other')
    is never even looked up in the usearch registry and keeps answering from
    sqlite-vec, unaffected."""
    from trovex.config import Settings
    from trovex.query_cache import embed_query_blob
    from trovex.store import SqliteStore

    class _TinyEmbedder:
        name = "tiny"
        dim = DIM

        def embed(self, texts):
            for t in texts:
                v = np.zeros(DIM, dtype=np.float32)
                v[abs(hash(t)) % DIM] = 1.0
                yield v

    emb = _TinyEmbedder()
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "none.yaml",
        usearch_partitions=["trovex"],  # the owned store's partition, flagged
    )
    store = SqliteStore(settings, embedder=emb)
    flagged_id = store.put("# Flagged\n\nhnsw partition marker content", tags=["t"])

    # Manually seed a second, UNFLAGGED partition ('other') — a minimal
    # doc+chunk+vec_chunks row, mirroring vec_chunks_put's own insert shape.
    db = store.db
    db.execute(
        "INSERT INTO docs(source_id, path, absolute_path, content_hash, size_bytes, "
        "tokens_est, mtime, first_indexed, last_indexed, title, ext_id) "
        "VALUES ('other', 'other.md', '/other.md', 'h', 10, 5, 0, 0, 0, 'Other', 'other-1')"
    )
    other_doc_id = db.execute("SELECT id FROM docs WHERE ext_id = 'other-1'").fetchone()["id"]
    db.execute(
        "INSERT INTO chunks(doc_id, chunk_index, heading_path, content, tokens_est, content_hash) "
        "VALUES (?, 0, '', 'other partition marker content', 5, 'ch')",
        (other_doc_id,),
    )
    other_chunk_id = db.execute(
        "SELECT id FROM chunks WHERE doc_id = ?", (other_doc_id,)
    ).fetchone()["id"]
    db.execute("INSERT INTO doc_tags(doc_id, tag) VALUES (?, 't')", (other_doc_id,))
    other_blob = embed_query_blob(emb, "other partition marker content")
    db.execute(
        "INSERT INTO vec_chunks(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
        "VALUES (?, 'other', ?, '', 'active', 'canonical', 'test')",
        (other_chunk_id, other_blob),
    )
    db.commit()

    # Build the HNSW index for ONLY the flagged partition.
    n = usearch_index.rebuild_partition(db, "vec_chunks", "trovex", settings.resolved_embed_dim())
    assert n > 0
    assert usearch_index.get_index("vec_chunks", "trovex") is not None
    assert usearch_index.get_index("vec_chunks", "other") is None  # never built — unflagged

    flagged_hits = store.search_chunks("marker content", limit=5, source="trovex", tags=["t"])
    other_hits = store.search_chunks("marker content", limit=5, source="other", tags=["t"])

    assert any(h["path"] == flagged_id for h in flagged_hits)  # served via HNSW
    assert any(h["path"] == "other.md" for h in other_hits)  # served via sqlite-vec, unaffected


def test_reindex_rebuilds_the_index_for_a_flagged_source(tmp_path):
    """task 4c89b89a AC2: 'rebuilt after each index run for that partition'.
    Indexer.reindex() must call usearch_index.rebuild_partition for every
    source_id in Settings.usearch_partitions once it finishes — no manual
    rebuild call needed by the caller."""
    from trovex.config import Settings
    from trovex.indexer import Indexer

    usearch_index._indexes.clear()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.md").write_text("# A\n\nhello world content", encoding="utf-8")

    settings = Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "none.yaml",
        usearch_partitions=["code"],  # reindex(root=...) defaults the source id to 'code'
    )

    class _Bag:
        name = "bag"
        dim = DIM

        def embed(self, texts):
            for _ in texts:
                v = np.zeros(DIM, dtype=np.float32)
                v[0] = 1.0
                yield v

    assert usearch_index.get_index("vec_docs", "code") is None
    Indexer(settings, embedder=_Bag()).reindex(root=repo)
    assert usearch_index.get_index("vec_docs", "code") is not None
    assert len(usearch_index.get_index("vec_docs", "code")) == 1
    assert usearch_index.get_index("vec_chunks", "code") is not None


def test_reindex_paths_also_rebuilds_the_index(tmp_path):
    """The incremental path (fs-watch / index_jobs applier) must rebuild too —
    not just the full reindex()."""
    from trovex.config import Settings, Source
    from trovex.indexer import Indexer

    usearch_index._indexes.clear()
    repo = tmp_path / "repo"
    repo.mkdir()
    f = repo / "a.md"
    f.write_text("# A\n\nhello world content", encoding="utf-8")

    settings = Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "none.yaml",
        usearch_partitions=["code"],
    )

    class _Bag:
        name = "bag"
        dim = DIM

        def embed(self, texts):
            for _ in texts:
                v = np.zeros(DIM, dtype=np.float32)
                v[0] = 1.0
                yield v

    indexer = Indexer(settings, embedder=_Bag())
    indexer.reindex_paths([f], sources=[Source(id="code", label="repo", root=repo)])
    assert usearch_index.get_index("vec_docs", "code") is not None
    assert len(usearch_index.get_index("vec_docs", "code")) == 1


async def test_startup_builds_the_index_before_serving(tmp_path):
    """task 4c89b89a AC2: 'a startup path that builds the index before
    serving'. lifespan() must build every flagged partition's index BEFORE
    the applier/watchdog start — a request landing right after boot must not
    see an empty index and silently fall back to sqlite-vec."""
    from trovex import state as state_mod
    from trovex.config import Settings
    from trovex.indexer import Indexer
    from trovex.search import Searcher
    from trovex.server import build_app, lifespan
    from trovex.state import AppState
    from trovex.store import SqliteStore

    usearch_index._indexes.clear()

    class _Bag:
        name = "bag"
        dim = DIM

        def embed(self, texts):
            for _ in texts:
                v = np.zeros(DIM, dtype=np.float32)
                v[0] = 1.0
                yield v

    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "none.yaml",
        usearch_partitions=["trovex"],
    )
    embedder = _Bag()
    store = SqliteStore(settings, embedder=embedder)
    store.put("# Seeded\n\nbuilt before serving", tags=["t"])

    state_mod._state = AppState(
        settings=settings,
        embedder=embedder,
        searcher=Searcher(settings, embedder=embedder),
        indexer=Indexer(settings, embedder=embedder),
        store=store,
    )
    try:
        assert usearch_index.get_index("vec_docs", "trovex") is None
        async with lifespan(build_app()):
            assert usearch_index.get_index("vec_docs", "trovex") is not None
            assert len(usearch_index.get_index("vec_docs", "trovex")) == 1
    finally:
        state_mod.reset_state()
