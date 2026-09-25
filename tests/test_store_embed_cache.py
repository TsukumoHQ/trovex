"""SqliteStore embed_cache reuse (task cbb8e8fb fast-follow finding #1):
store.put()/put_batch() had the same bug class as indexer.py — _embed/
_embed_chunks called the ONNX embedder while the row-write transaction was
still open, inside self._lock. Live incident: a batch of large trovex_write
calls each hit the 30s TOOL_TIMEOUT, serialized behind self._lock, launchd
watchdog restarted the serve process.

This file pins: put()/put_batch() reuse embed_cache (a real speedup even
without touching the lock), the cache is SHARED with Indexer (same text, same
model → one vector, regardless of which write path produced it first), and
put() stays a single atomic write — no mid-flow commit was introduced (that
half of the original fix was deliberately NOT applied to store.py; see
db.resolve_embedding_blobs's docstring for why: a single trovex_write must
stay all-or-nothing, unlike Indexer's periodic-commit reindex).

Hermetic: BagEmbedder + a CountingEmbedder that records every text it's
asked to embed, no network, no real model download. A single put() of a
markdown doc can call embed() more than once (doc-level + chunk-level via
chunk_markdown) — tests assert no TEXT is ever embedded twice, not a fixed
call count, so they don't couple to chunk_markdown's exact chunk boundaries.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex.config import Settings, Source
from trovex.indexer import Indexer
from trovex.store import SqliteStore

DIM = 384


class CountingEmbedder:
    name = "bag"
    dim = DIM

    def __init__(self) -> None:
        self.embedded: list[str] = []

    def embed(self, texts):
        self.embedded.extend(texts)
        for t in texts:
            v = np.zeros(DIM, dtype=np.float32)
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                idx = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                v[idx % DIM] += 1.0
            norm = float(np.linalg.norm(v)) or 1.0
            yield v / norm


class TxnStillOpenEmbedder(CountingEmbedder):
    """Records whether the caller's sqlite connection STILL had the row-write
    transaction open at the moment embed() was invoked. store.py deliberately
    keeps this true (commit_before_embed=False) — put() stays one atomic
    write; only Indexer took the transaction-narrowing half of the fix."""

    def __init__(self, db) -> None:
        super().__init__()
        self._db = db
        self.saw_open_transaction = False

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


def test_put_hits_embed_cache_on_identical_content(settings):
    embedder = CountingEmbedder()
    store = SqliteStore(settings, embedder=embedder)

    store.put("# Report\n\nexact same body", kind="record")
    n_after_first = len(embedder.embedded)
    assert n_after_first >= 1

    store.put("# Report\n\nexact same body", kind="record")  # 2nd doc, same text
    new_texts = embedder.embedded[n_after_first:]
    assert new_texts == [], f"2nd put()'s identical text(s) must all hit embed_cache, got {new_texts}"


def test_put_batch_hits_embed_cache_on_identical_content(settings):
    embedder = CountingEmbedder()
    store = SqliteStore(settings, embedder=embedder)

    ext_ids = store.put_batch(
        [
            {"content": "# Dup\n\nexact same body", "kind": "record"},
            {"content": "# Dup\n\nexact same body", "kind": "record"},
        ]
    )
    assert len(ext_ids) == 2
    # Whatever texts this content produces (doc-level, maybe chunk-level too),
    # none may repeat — two identical docs in one batch must dedupe.
    assert len(embedder.embedded) == len(set(embedder.embedded))


def test_embed_cache_shared_between_store_and_indexer(settings, tmp_path):
    """Same (title, content), same model, either write path first → the OTHER
    path's write is a cache hit. Proves DOC_EMBED_NS is genuinely shared."""
    text_body = "# Shared Topic\n\nidentical content across both write paths"

    idx_embedder = CountingEmbedder()
    idx = Indexer(settings, embedder=idx_embedder)
    src_root = tmp_path / "repo"
    src_root.mkdir()
    (src_root / "a.md").write_text(text_body, encoding="utf-8")
    idx.reindex(sources=[Source(id="code", label="repo", root=src_root)])
    doc_level_text = "Shared Topic\n\n# Shared Topic\n\nidentical content across both write paths"
    assert doc_level_text in idx_embedder.embedded

    store_embedder = CountingEmbedder()
    store = SqliteStore(settings, embedder=store_embedder)
    store.put(text_body, kind="record")

    assert doc_level_text not in store_embedder.embedded, (
        "store.put()'s doc-level embed must hit the cache the indexer already warmed"
    )


def test_put_keeps_transaction_open_during_embed(settings):
    """store.py did NOT take the transaction-narrowing half of the fix (see
    module docstring) — the row-write transaction is still open when embed()
    runs, by design, so put() stays a single atomic commit."""
    store = SqliteStore(settings, embedder=CountingEmbedder())  # warm nothing
    embedder = TxnStillOpenEmbedder(store.db)
    store.embedder = embedder

    store.put("# Alpha\n\nsome body text that will actually embed", kind="record")

    assert embedder.embedded, "the fixture must actually exercise embed()"
    assert embedder.saw_open_transaction
