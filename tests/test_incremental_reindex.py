"""Incremental re-index — mtime fast-path (task af919fe2 / ticket df1f17a7).

reindex() must re-embed ONLY changed/added docs, prune deleted docs' vectors,
and keep the sqlite-vec index consistent (no orphan vectors, no dupes). The
mtime fast-path lets an unchanged file cost one stat() instead of a full
read()+sha256 every run.

Hermetic: a deterministic bag-of-words embedder that also RECORDS which texts
it was asked to embed, so we can assert exactly which docs were re-embedded.
"""

from __future__ import annotations

import hashlib
import os
import re

import numpy as np
import pytest

from trovex.config import Settings, Source
from trovex.indexer import Indexer
from trovex.search import Searcher

DIM = 384


class CountingEmbedder:
    """BagEmbedder that appends every embedded text to `self.embedded`."""

    name = "bag"
    dim = DIM

    def __init__(self) -> None:
        self.embedded: list[str] = []

    def embed(self, texts):
        for t in texts:
            self.embedded.append(t)
            v = np.zeros(DIM, dtype=np.float32)
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                idx = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                v[idx % DIM] += 1.0
            norm = float(np.linalg.norm(v)) or 1.0
            yield v / norm


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",  # dim 384, matches CountingEmbedder
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


def _reindex(settings, root, embedder):
    return Indexer(settings, embedder=embedder).reindex(sources=_src(root))


def _counts(db):
    docs = db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
    vecs = db.execute("SELECT COUNT(*) AS c FROM vec_docs").fetchone()["c"]
    return docs, vecs


def test_only_changed_doc_is_reembedded(settings, source_root):
    """Change 1 doc in a store of many → only that doc re-embeds (not a full rebuild)."""
    _write(source_root, "a.md", "# Alpha\n\nalpha content", mtime=1000)
    _write(source_root, "b.md", "# Bravo\n\nbravo content", mtime=1000)
    _write(source_root, "c.md", "# Charlie\n\ncharlie content", mtime=1000)

    first = CountingEmbedder()
    stats1 = _reindex(settings, source_root, first)
    assert stats1["added"] == 3
    assert len(first.embedded) == 3

    # Edit b.md only; bump its mtime so the fast-path re-reads it.
    _write(source_root, "b.md", "# Bravo\n\nbravo REVISED content", mtime=2000)

    second = CountingEmbedder()
    stats2 = _reindex(settings, source_root, second)
    assert (stats2["added"], stats2["updated"], stats2["unchanged"], stats2["removed"]) == (
        0,
        1,
        2,
        0,
    )
    # Exactly one doc re-embedded, and it is b.md.
    assert len(second.embedded) == 1
    assert "REVISED" in second.embedded[0]


def test_mtime_fastpath_skips_read(settings, source_root):
    """The documented tradeoff, asserted: a content edit that PRESERVES mtime is
    NOT detected — which proves the fast-path skips read()+sha256 when mtime matches."""
    _write(source_root, "a.md", "# Alpha\n\noriginal body", mtime=1000)
    _reindex(settings, source_root, CountingEmbedder())

    # Overwrite content but restore the identical mtime (same-second write / touch -r).
    _write(source_root, "a.md", "# Alpha\n\ntotally different body", mtime=1000)

    second = CountingEmbedder()
    stats2 = _reindex(settings, source_root, second)
    assert stats2["unchanged"] == 1
    assert stats2["updated"] == 0
    assert second.embedded == []  # never even read the new content


def test_mtime_moved_same_content_no_reembed(settings, source_root):
    """mtime moved but content identical (e.g. git checkout) → no re-embed, and the
    stored mtime is refreshed so the next run's fast-path hits."""
    _write(source_root, "a.md", "# Alpha\n\nstable body", mtime=1000)
    _reindex(settings, source_root, CountingEmbedder())

    _write(source_root, "a.md", "# Alpha\n\nstable body", mtime=5000)  # same bytes, new mtime

    second = CountingEmbedder()
    stats2 = _reindex(settings, source_root, second)
    assert stats2["unchanged"] == 1
    assert stats2["updated"] == 0
    assert second.embedded == []

    idx = Indexer(settings, embedder=CountingEmbedder())
    row = idx.db.execute("SELECT mtime FROM docs WHERE path = 'a.md'").fetchone()
    assert row["mtime"] == 5000  # refreshed → fast-path hits next time


def test_deleted_doc_vectors_pruned(settings, source_root):
    """A vanished file → its doc row AND its vector are removed (no orphan vectors)."""
    _write(source_root, "a.md", "# Alpha\n\nalpha", mtime=1000)
    _write(source_root, "b.md", "# Bravo\n\nbravo", mtime=1000)
    _reindex(settings, source_root, CountingEmbedder())

    (source_root / "b.md").unlink()
    stats2 = _reindex(settings, source_root, CountingEmbedder())
    assert stats2["removed"] == 1

    idx = Indexer(settings, embedder=CountingEmbedder())
    docs, vecs = _counts(idx.db)
    assert docs == 1  # only a.md left
    assert vecs == 1  # one vector per doc — b.md's vector pruned, none orphaned
    assert idx.db.execute("SELECT COUNT(*) AS c FROM docs WHERE path='b.md'").fetchone()["c"] == 0


def test_added_doc_indexed(settings, source_root):
    """A new file → indexed and embedded, existing docs untouched."""
    _write(source_root, "a.md", "# Alpha\n\nalpha", mtime=1000)
    _reindex(settings, source_root, CountingEmbedder())

    _write(source_root, "b.md", "# Bravo\n\nbravo new doc", mtime=1000)
    second = CountingEmbedder()
    stats2 = _reindex(settings, source_root, second)
    assert stats2["added"] == 1
    assert stats2["unchanged"] == 1
    assert len(second.embedded) == 1
    assert "Bravo" in second.embedded[0]


def test_index_consistent_no_orphans_or_dupes(settings, source_root):
    """Across a churn cycle (edit + add + delete) vec_docs stays 1:1 with docs."""
    _write(source_root, "a.md", "# Alpha\n\nalpha", mtime=1000)
    _write(source_root, "b.md", "# Bravo\n\nbravo", mtime=1000)
    _write(source_root, "c.md", "# Charlie\n\ncharlie", mtime=1000)
    _reindex(settings, source_root, CountingEmbedder())

    _write(source_root, "a.md", "# Alpha\n\nalpha revised", mtime=2000)  # edit
    _write(source_root, "d.md", "# Delta\n\ndelta", mtime=2000)  # add
    (source_root / "c.md").unlink()  # delete
    _reindex(settings, source_root, CountingEmbedder())

    idx = Indexer(settings, embedder=CountingEmbedder())
    docs, vecs = _counts(idx.db)
    assert docs == vecs == 3  # a, b, d — one vector each, no orphan from c


def test_search_correct_after_incremental_update(settings, source_root):
    """Search reflects the incremental edit: the changed doc matches its NEW topic,
    and the doc that genuinely owns the OLD topic now outranks it there."""
    _write(source_root, "a.md", "# Auth\n\njwt token signature validation", mtime=1000)
    _write(source_root, "b.md", "# Deploy\n\nkubernetes pod rollback crash", mtime=1000)
    _write(source_root, "c.md", "# Security\n\njwt token signature audit trail", mtime=1000)
    _reindex(settings, source_root, CountingEmbedder())

    # Repurpose a.md to a wholly new topic.
    _write(source_root, "a.md", "# Billing\n\nstripe invoice payment webhook", mtime=2000)
    _reindex(settings, source_root, CountingEmbedder())

    searcher = Searcher(settings, embedder=CountingEmbedder())

    # a.md's vector was re-embedded → it now matches its NEW topic best.
    new_topic = searcher.search("stripe invoice payment", limit=1, source_ids=["code"])
    assert new_topic, "expected the re-indexed doc to be searchable under its new topic"
    assert new_topic[0].path == "a.md"

    # a.md's OLD vector is gone (not stale): the jwt query now resolves to c.md,
    # the doc that actually owns that topic — a.md no longer wins it.
    old_topic = searcher.search("jwt token signature", limit=1, source_ids=["code"])
    assert old_topic and old_topic[0].path == "c.md"
