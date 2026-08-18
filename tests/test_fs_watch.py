"""Live fs-watch incremental re-index (task 3a34769b).

Two layers, both hermetic:
- Indexer.reindex_paths — the scoped, mtime-bypassing re-index of only the paths
  a file event names (bag embedder, no model download).
- Watcher — the debounce core, driven by calling notify()/_flush() directly so
  the tests never depend on real, timing-flaky watchdog events. One light
  start()/stop() integration check exercises the watchdog wiring.
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
from trovex.watch import Watcher

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


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.md").write_text("# Alpha\n\nalpha body", encoding="utf-8")
    (root / "b.md").write_text("# Bravo\n\nbravo body", encoding="utf-8")
    return Source(id="code", label="repo", root=root)


def _indexer(settings):
    return Indexer(settings, embedder=BagEmbedder())


def _counts(db):
    docs = db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
    vecs = db.execute("SELECT COUNT(*) AS c FROM vec_docs").fetchone()["c"]
    return docs, vecs


# ── reindex_paths: scoped, mtime-bypassing ────────────────────────────────


def test_reindex_paths_change(settings, source):
    idx = _indexer(settings)
    idx.reindex(sources=[source])

    (source.root / "a.md").write_text("# Alpha\n\nalpha REVISED", encoding="utf-8")
    stats = idx.reindex_paths([source.root / "a.md"], sources=[source])
    assert (stats["updated"], stats["added"], stats["removed"]) == (1, 0, 0)
    assert _counts(idx.db) == (2, 2)  # 1:1, b.md untouched


def test_reindex_paths_add_and_remove(settings, source):
    idx = _indexer(settings)
    idx.reindex(sources=[source])

    (source.root / "c.md").write_text("# Charlie\n\ncharlie", encoding="utf-8")
    add = idx.reindex_paths([source.root / "c.md"], sources=[source])
    assert add["added"] == 1
    assert _counts(idx.db) == (3, 3)

    (source.root / "b.md").unlink()
    rem = idx.reindex_paths([source.root / "b.md"], sources=[source])
    assert rem["removed"] == 1
    docs, vecs = _counts(idx.db)
    assert docs == vecs == 2  # b pruned, no orphan vector


def test_reindex_paths_catches_mtime_preserving_edit(settings, source):
    """The whole point: a content edit that PRESERVES mtime is missed by the
    full reindex() fast-path but caught by reindex_paths (an fs event proves it)."""
    idx = _indexer(settings)
    idx.reindex(sources=[source])
    a = source.root / "a.md"
    keep = a.stat().st_mtime

    a.write_text("# Alpha\n\ncompletely different body", encoding="utf-8")
    os.utime(a, (keep, keep))  # restore the exact mtime

    # A full reindex misses it (mtime unchanged → fast-path skips).
    missed = idx.reindex(sources=[source])
    assert missed["updated"] == 0 and missed["unchanged"] == 2

    # reindex_paths re-hashes unconditionally → catches it.
    caught = idx.reindex_paths([a], sources=[source])
    assert caught["updated"] == 1

    hits = Searcher(settings, embedder=BagEmbedder()).search(
        "completely different", limit=1, source_ids=["code"]
    )
    assert hits and hits[0].path == "a.md"


def test_reindex_paths_no_op_when_bytes_unchanged(settings, source):
    """An event that didn't actually change bytes refreshes mtime, no re-embed."""
    idx = _indexer(settings)
    idx.reindex(sources=[source])
    stats = idx.reindex_paths([source.root / "a.md"], sources=[source])
    assert (stats["updated"], stats["added"], stats["unchanged"]) == (0, 0, 1)


def test_reindex_paths_ignores_paths_outside_sources(settings, source, tmp_path):
    idx = _indexer(settings)
    idx.reindex(sources=[source])
    outsider = tmp_path / "elsewhere" / "x.md"
    outsider.parent.mkdir()
    outsider.write_text("# nope\n\nbody", encoding="utf-8")
    stats = idx.reindex_paths([outsider], sources=[source])
    assert (stats["added"], stats["updated"], stats["removed"]) == (0, 0, 0)
    assert _counts(idx.db) == (2, 2)


# ── Watcher: debounce + lifecycle ─────────────────────────────────────────


class _RecordingIndexer:
    """Stands in for Indexer to make the debounce logic deterministic."""

    def __init__(self):
        self.calls: list[set[str]] = []

    def reindex_paths(self, batch, sources=None):
        self.calls.append(set(map(str, batch)))
        return {"added": 0, "updated": 0, "unchanged": 0, "removed": 0, "duration_sec": 0.0}


def test_watcher_debounce_coalesces_a_burst(source):
    rec = _RecordingIndexer()
    # Long debounce so the timer never fires during the test; we flush by hand.
    w = Watcher(rec, [source], debounce_sec=100)
    a, b = source.root / "a.md", source.root / "b.md"
    w.notify(a)
    w.notify(b)
    assert w._pending == {str(a), str(b)}  # both queued, no reindex yet
    assert rec.calls == []
    w._flush()
    assert rec.calls == [{str(a), str(b)}]  # exactly one pass over the union
    w.stop()


def test_watcher_stop_flushes_pending_and_is_idempotent(source):
    rec = _RecordingIndexer()
    w = Watcher(rec, [source], debounce_sec=100)
    w.notify(source.root / "a.md")
    w.stop()  # must flush the queued change, not drop it
    assert rec.calls == [{str(source.root / "a.md")}]
    w.stop()  # idempotent — no crash, nothing new
    assert len(rec.calls) == 1


def test_watcher_start_stop_is_graceful(settings, source):
    """The watchdog wiring starts and stops cleanly (no busy-loop, no leak)."""
    idx = _indexer(settings)
    idx.reindex(sources=[source])
    w = Watcher(idx, [source], debounce_sec=0.05)
    w.start()
    try:
        assert w._observer is not None
    finally:
        w.stop()
    assert w._observer is None  # released on stop
