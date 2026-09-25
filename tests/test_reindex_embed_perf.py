"""Reindex embed-outside-txn + embed_cache + per-phase timing (task cbb8e8fb,
fast-follow to 67ebd68c).

Root cause: prod after 67ebd68c had zero 'database is locked' errors (the lock
goal was met) but reindex wall time was still ~137s for 6-7 changed docs out
of 2005 — indexer.py's _flush_embeddings ran the ONNX embedder INSIDE the
still-open sqlite transaction from the preceding doc-row INSERT/UPDATE, so the
WAL writer slot stayed held for the whole (seconds-to-minutes, CPU-bound)
model call, and identical/renamed content had no way to skip re-embedding.

Fix:
  - _embed_texts_cached commits any pending row writes BEFORE calling
    embedder.embed(), so no transaction is open while the model runs.
  - embed_cache (content_hash-of-the-embedded-text, embed_model,
    chunker_version) -> serialized vector blob: a hit skips the model call
    entirely.
  - index_runs.phase_ms (json: scan/chunk/embed/write/status) and
    embed_cache_hits/misses make a slow run's dominant phase visible without
    re-profiling live.

Hermetic: CountingEmbedder (BagEmbedder + records every text it's asked to
embed), no network, no real model download.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3

import numpy as np
import pytest

from trovex.config import Settings, Source
from trovex.indexer import Indexer

DIM = 384


class CountingEmbedder:
    name = "bag"
    dim = DIM

    def __init__(self) -> None:
        self.embedded: list[str] = []
        self.saw_open_transaction = False

    def embed(self, texts):
        self.embedded.extend(texts)
        for t in texts:
            v = np.zeros(DIM, dtype=np.float32)
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                idx = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                v[idx % DIM] += 1.0
            norm = float(np.linalg.norm(v)) or 1.0
            yield v / norm


class TxnCheckingEmbedder(CountingEmbedder):
    """Records whether the caller's sqlite connection had an open transaction
    at the moment embed() was invoked — the AC2 assertion needs a live view
    of the connection at call time, not after the fact."""

    def __init__(self, db: sqlite3.Connection) -> None:
        super().__init__()
        self._db = db

    def embed(self, texts):
        if self._db.in_transaction:
            self.saw_open_transaction = True
        yield from super().embed(texts)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


@pytest.fixture
def source_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    return root


def _write(root, rel: str, text: str, *, mtime: float | None = None):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def _src(root):
    return [Source(id="code", label="repo", root=root)]


def test_no_transaction_open_during_embed(settings, source_root):
    """AC: embedding runs with no sqlite transaction open."""
    for i in range(5):
        _write(source_root, f"doc{i}.md", f"# Doc {i}\n\nunique body {i}", mtime=1000)

    idx = Indexer(settings, embedder=CountingEmbedder())
    embedder = TxnCheckingEmbedder(idx.db)
    idx.embedder = embedder

    idx.reindex(sources=_src(source_root))

    assert embedder.embedded, "the fixture must actually exercise embed()"
    assert not embedder.saw_open_transaction, (
        "a transaction was open on the indexer's connection when embed() ran — "
        "a concurrent trovex_write would have waited out the model call"
    )


def test_embed_cache_hits_on_identical_content_across_docs(settings, source_root):
    """AC: identical content re-indexed (here: two different paths with the
    same body) hits the cache — the model is called once, not twice."""
    _write(source_root, "a.md", "# Shared\n\nexact same body text", mtime=1000)
    _write(source_root, "b.md", "# Shared\n\nexact same body text", mtime=1000)
    # a.md and b.md get DIFFERENT titles from their filename? No — title comes
    # from the H1, both "Shared" here, so _embed_text (title + body) hashes
    # identically for both → a genuine cache hit on the 2nd.

    embedder = CountingEmbedder()
    idx = Indexer(settings, embedder=embedder)
    stats = idx.reindex(sources=_src(source_root))

    assert stats["added"] == 2
    assert len(embedder.embedded) == 1, "2nd doc's identical text must hit embed_cache"
    assert stats["embed_cache_hits"] == 1
    assert stats["embed_cache_misses"] == 1


def test_embed_cache_misses_on_changed_content(settings, source_root):
    """AC: changed content misses the cache and is actually re-embedded."""
    _write(source_root, "a.md", "# Alpha\n\noriginal body", mtime=1000)
    first = CountingEmbedder()
    Indexer(settings, embedder=first).reindex(sources=_src(source_root))

    _write(source_root, "a.md", "# Alpha\n\ncompletely different body now", mtime=2000)
    second = CountingEmbedder()
    stats2 = Indexer(settings, embedder=second).reindex(sources=_src(source_root))

    assert len(second.embedded) == 1
    assert stats2["embed_cache_misses"] == 1
    assert stats2["embed_cache_hits"] == 0


def test_index_runs_row_carries_phase_ms_and_cache_counts(settings, source_root):
    """AC: index_runs rows carry per-phase timings (scan, chunk, embed, write)
    and cache hit/miss counts; pinned on the row shape."""
    _write(source_root, "a.md", "# Alpha\n\nalpha body", mtime=1000)
    idx = Indexer(settings, embedder=CountingEmbedder())
    stats = idx.reindex(sources=_src(source_root))

    assert set(stats["phase_ms"].keys()) >= {"scan", "chunk", "embed", "write", "status"}
    assert all(v >= 0 for v in stats["phase_ms"].values())
    assert stats["embed_cache_hits"] == 0
    assert stats["embed_cache_misses"] == 1

    row = idx.db.execute(
        "SELECT phase_ms, embed_cache_hits, embed_cache_misses FROM index_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    row_phase_ms = json.loads(row["phase_ms"])
    assert set(row_phase_ms.keys()) >= {"scan", "chunk", "embed", "write", "status"}
    assert row["embed_cache_misses"] == 1
    assert row["embed_cache_hits"] == 0


def test_unchanged_2000_doc_corpus_reindex_under_5s(settings, source_root):
    """AC: unchanged-corpus reindex on a 2000-doc fixture completes under 5s wall."""
    for i in range(2000):
        _write(source_root, f"doc{i}.md", f"# Doc {i}\n\nbody text for doc {i}", mtime=1000)

    idx = Indexer(settings, embedder=CountingEmbedder())
    idx.reindex(sources=_src(source_root))  # warm the store

    second = CountingEmbedder()
    idx2 = Indexer(settings, embedder=second)
    stats2 = idx2.reindex(sources=_src(source_root))

    assert stats2["unchanged"] == 2000
    assert second.embedded == []
    assert stats2["wall_ms"] < 5000, f"unchanged 2000-doc reindex took {stats2['wall_ms']:.0f}ms"
