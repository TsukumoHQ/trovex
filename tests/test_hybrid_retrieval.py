"""Hybrid BM25+dense RRF on the doc-router search (task b255b086).

Proves the flagship `search()` fuses vector + BM25 (docs_fts) and that the fusion
RESCUES exact-token queries a dense-only ranking misses — the error codes, fn/API
names, ids, flags an embedding blurs. Hermetic (no model download): a fully-blurred
ConstEmbedder isolates the BM25 signal; a token-sensitive BagEmbedder shows the
hybrid never regresses.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

from trovex.config import Settings
from trovex.retrieval_eval import LabeledQuery, evaluate_retrieval
from trovex.search import Searcher
from trovex.store import SqliteStore

DIM = 384


class ConstEmbedder:
    """Every text → the SAME unit vector: dense retrieval is blind, so any ranking
    signal must come from BM25. Models the real failure mode (a dense model that
    can't tell exact rare tokens apart) in a deterministic, hermetic way."""

    name = "const"
    dim = DIM

    def embed(self, texts):
        v = np.zeros(DIM, dtype=np.float32)
        v[0] = 1.0
        for _ in texts:
            yield v.copy()


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


class _DenseOnly:
    """Wraps a Searcher to force hybrid=False — the retrieval_eval baseline."""

    def __init__(self, searcher: Searcher):
        self._s = searcher

    def search(self, query, limit=5, source_ids=None, kind=None, tags=None):
        return self._s.search(
            query, limit=limit, source_ids=source_ids, kind=kind, tags=tags, hybrid=False
        )


CORPUS = [
    ("# Auth\n\njwt signature validation flow", "auth"),
    ("# Deploy\n\nkubernetes rollback on ERR_ROLL_4213 during rollout", "deploy"),
    ("# Billing\n\nstripe webhook retries need an idempotency_key header", "billing"),
    ("# Config\n\nthe ENABLE_NEW_UI feature flag defaults to false", "config"),
]
QUERIES = [
    ("ERR_ROLL_4213", "deploy"),
    ("idempotency_key", "billing"),
    ("ENABLE_NEW_UI", "config"),
    ("jwt signature", "auth"),
]


def _build(tmp_path, embedder, dup_threshold: float = 0.90):
    # ConstEmbedder maps every doc to the SAME vector, so the write-path dedup
    # (cosine > dup_cosine_threshold) would flag all-but-one CORPUS doc as a
    # duplicate — a harness artifact, not real behaviour (distinct docs get
    # distinct embeddings). A >1.0 threshold disables that flagging so these
    # BM25-fusion tests see the whole corpus, which is the point they measure.
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
        dup_cosine_threshold=dup_threshold,
    )
    store = SqliteStore(settings, embedder=embedder)
    ids = {tag: store.put(body, tags=[f"topic/{tag}"]) for body, tag in CORPUS}
    return settings, ids


def _labeled(ids):
    return [LabeledQuery(query=q, relevant=[ids[tag]]) for q, tag in QUERIES]


def test_hybrid_beats_dense_on_exact_tokens(tmp_path):
    """With dense blind (ConstEmbedder), BM25 must carry every exact-token query."""
    settings, ids = _build(tmp_path, ConstEmbedder(), dup_threshold=1.1)
    searcher = Searcher(settings, embedder=ConstEmbedder())
    labeled = _labeled(ids)

    dense = evaluate_retrieval(_DenseOnly(searcher), labeled, source_ids=["trovex"])
    hybrid = evaluate_retrieval(searcher, labeled, source_ids=["trovex"])

    assert hybrid.hit_at_1 > dense.hit_at_1
    assert hybrid.hit_at_1 == 1.0  # BM25 finds every exact token
    assert hybrid.mrr >= dense.mrr


def test_hybrid_rescues_a_query_dense_ranks_wrong(tmp_path):
    """Sharp mechanism check: dense (blind) puts the wrong doc first; hybrid fixes it."""
    settings, ids = _build(tmp_path, ConstEmbedder(), dup_threshold=1.1)
    searcher = Searcher(settings, embedder=ConstEmbedder())

    dense = searcher.search("ERR_ROLL_4213", limit=1, source_ids=["trovex"], hybrid=False)
    hybrid = searcher.search("ERR_ROLL_4213", limit=1, source_ids=["trovex"], hybrid=True)
    assert dense and dense[0].path != ids["deploy"]  # dense misses (arbitrary order)
    assert hybrid and hybrid[0].path == ids["deploy"]  # BM25 fusion rescues it


def test_hybrid_no_regression_with_token_sensitive_dense(tmp_path):
    """With a token-sensitive dense embedder, hybrid must not do worse than dense."""
    settings, ids = _build(tmp_path, BagEmbedder())
    searcher = Searcher(settings, embedder=BagEmbedder())
    labeled = _labeled(ids)

    dense = evaluate_retrieval(_DenseOnly(searcher), labeled, source_ids=["trovex"])
    hybrid = evaluate_retrieval(searcher, labeled, source_ids=["trovex"])
    assert hybrid.hit_at_1 >= dense.hit_at_1
    assert hybrid.hit_at_k >= dense.hit_at_k


def test_boot_recall_survives_hybrid_default_floor(tmp_path):
    """Regression (review r1): the flagship search went hybrid RRF, whose scores are
    ~10x smaller than cosine. boot_pointers floors on an ABSOLUTE cosine score
    (default 0.62), so it must use the dense path — else a scoped record floors out
    and Active-Memory boot returns empty for every agent. (The existing boot tests
    passed floor=0.0 and never caught this.)"""
    from trovex.boot import boot_pointers

    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    store = SqliteStore(settings, embedder=BagEmbedder())
    store.put(
        "# Resume\n\ncurrent state resume open work in flight next steps gotchas",
        kind="record",
        tags=["owner/backend"],
    )
    # DEFAULT floor (0.62) — the /api/boot value, not the test-only floor=0.0.
    boot = boot_pointers(Searcher(settings, embedder=BagEmbedder()), "backend")
    assert boot["pointers"], "a scoped record must clear the default cosine floor"
    assert boot["pointers"][0]["title"] == "Resume"


def test_freshness_status_weighting_preserved(tmp_path):
    """A stale doc must not outrank a canonical one for the same query — the
    status/freshness reweight still applies on top of the RRF score. (Uses
    'stale', not 'duplicate': duplicates are now dropped from the pool entirely,
    so the weighting invariant is exercised with a status that stays in-pool.)"""
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
        # Two identical-vector docs would auto-flag one as a duplicate (excluded);
        # disable that here so BOTH stay in the pool and the test isolates the
        # status WEIGHT, not the duplicate filter.
        dup_cosine_threshold=1.1,
    )
    store = SqliteStore(settings, embedder=BagEmbedder())
    good = store.put("# Runbook\n\ndeploy rollback procedure canonical")
    weak = store.put("# Runbook copy\n\ndeploy rollback procedure canonical")
    # Force the second into 'stale' (down-weighted 0.5, but still retrievable).
    store.db.execute("UPDATE docs SET status='stale' WHERE ext_id=?", (weak,))
    store.db.commit()

    hits = Searcher(settings, embedder=BagEmbedder()).search(
        "deploy rollback procedure", limit=2, source_ids=["trovex"]
    )
    assert hits and hits[0].path == good  # canonical outranks the stale doc
    assert {h.path for h in hits} == {good, weak}  # both stay in the pool
