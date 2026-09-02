"""Regression for task 3771564e (prod P1, 2026-09-02).

Two bugs, both required for the fix to actually work:

1. ignore_dirs listed the bare "worktrees" but the fleet's real per-PR
   worktree convention always uses the dot-prefixed ".worktrees/" — the
   string never matched (config.py).
2. Even with the right name, the OLD scan() couldn't have skipped it anyway:
   it called `root.rglob(f"*.{ext}")` once per extension, and rglob has no
   directory-pruning hook — ignore_dirs was only ever consulted in _accept()
   AFTER rglob had already walked (and paid the full os.scandir cost of)
   every ignored directory. On prod: 49 agent .worktrees / ~58k files across
   3 repos, walked in full on every reindex regardless of ignore_dirs,
   ballooning scan duration to 100-600s (index_runs) for near-zero real
   corpus changes.

That slow scan held an open write transaction on the shared connection for
its duration (the first changed doc's UPDATE opens it; reindex's commit
batching is change-COUNT-based, not time-based, so a low-change run never
hits it) — starving concurrent trovex_write past its 30s busy_timeout and
pinning the WAL checkpoint at zero backfilled frames the whole time
(verified live: `PRAGMA wal_checkpoint(PASSIVE)` = 0|120724|0, persistent).

Fix: (1) add ".worktrees" to ignore_dirs (config.py) alongside the
pre-existing bare "worktrees" entry; (2) replace the per-extension rglob
loop with `_walk_files` (indexer.py), a single recursive `os.scandir` walk
that PRUNES an ignore_dirs-listed directory before ever entering it, instead
of filtering its contents after the fact."""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time

import numpy as np
import pytest

from trovex.config import Settings, Source
from trovex.indexer import Indexer, _walk_files
from trovex.store import SqliteStore

DIM = 384


class BagEmbedder:
    """Hermetic stand-in — scan() never calls it, but Indexer.__init__ needs one."""

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


def test_dot_worktrees_dir_is_skipped(settings, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# real doc\n", encoding="utf-8")
    stray = root / ".worktrees" / "some-task" / "notes.md"
    stray.parent.mkdir(parents=True)
    stray.write_text("agent workspace scratch\n", encoding="utf-8")

    indexer = Indexer(settings, embedder=BagEmbedder())
    found = {p.relative_to(root).as_posix() for p in indexer.scan(root)}

    assert "README.md" in found
    assert not any(f.startswith(".worktrees/") for f in found)


def test_bare_worktrees_dir_is_also_skipped(settings, tmp_path):
    """The pre-existing bare "worktrees" entry stays effective too — belt and
    braces for a differently-named setup, not a regression on the old rule."""
    root = tmp_path / "repo"
    root.mkdir()
    stray = root / "worktrees" / "some-task" / "notes.md"
    stray.parent.mkdir(parents=True)
    stray.write_text("agent workspace scratch\n", encoding="utf-8")

    indexer = Indexer(settings, embedder=BagEmbedder())
    found = {p.relative_to(root).as_posix() for p in indexer.scan(root)}

    assert not any(f.startswith("worktrees/") for f in found)


def test_ignored_dir_is_never_descended_into(tmp_path, monkeypatch):
    """AC1 mechanism proof: an ignored directory must not be *entered* at
    all — filtering its files out after listing them (the pre-fix behavior:
    rglob had already paid the full os.scandir cost) is not the same fix as
    never walking it. Deterministic (scandir-call count), not a timing
    assertion, so it can't be CI-flaky while still proving the walk was
    pruned rather than filtered."""
    root = tmp_path / "repo"
    (root / ".worktrees" / "w1").mkdir(parents=True)
    for i in range(500):
        (root / ".worktrees" / "w1" / f"f{i}.md").write_text("x")
    (root / "README.md").write_text("# real\n")

    calls = 0
    real_scandir = os.scandir

    def counting_scandir(path):
        nonlocal calls
        calls += 1
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", counting_scandir)

    found = list(_walk_files(root, {".worktrees", "worktrees"}))

    # Exactly root + README.md's parent (root again, no subdir) = 1 scandir
    # call. If .worktrees/w1 had been entered even once, this would be >= 2.
    assert calls == 1, f"walked into an ignored directory ({calls} scandir calls)"
    assert [p.name for p in found] == ["README.md"]


def test_reindex_stays_fast_with_large_ignored_subtree(tmp_path):
    """AC2/AC3 mechanism proof: reindex() duration must not scale with an
    ignored subtree's size, and the WAL must not balloon from walking it.
    5000 decoy files (bounded for CI speed; live prod was ~58k across 49
    worktrees — same mechanism, larger N) under .worktrees alongside a
    handful of real docs. Pre-fix (rglob-per-extension, no pruning), this
    scan would have paid os.scandir cost for every decoy file; post-fix it
    must complete in a small bounded time regardless of N."""
    root = tmp_path / "repo"
    root.mkdir()
    decoys = root / ".worktrees" / "some-task"
    decoys.mkdir(parents=True)
    for i in range(5000):
        (decoys / f"f{i}.md").write_text(f"decoy {i}\n")
    for i in range(5):
        (root / f"doc{i}.md").write_text(f"# Doc {i}\n\nreal content {i}\n")

    settings = Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    indexer = Indexer(settings, embedder=BagEmbedder())

    t0 = time.perf_counter()
    stats = indexer.reindex(sources=[Source(id="t", label="t", root=root)])
    elapsed = time.perf_counter() - t0

    assert stats["added"] == 5
    # Generous bound for a slow CI box — the point is independence from decoy
    # count, not a tight number; pre-fix this walked 5000+ extra files per
    # extension checked and, at prod scale (58k), took 100-600s (index_runs).
    assert elapsed < 5.0, f"reindex took {elapsed:.2f}s — scan is not skipping the ignored subtree"


def test_concurrent_write_stays_fast_during_reindex_with_large_worktrees(tmp_path):
    """End-to-end AC2 proof, same shape as the prod incident: a real
    trovex_write (SqliteStore.put on a separate connection to the same db
    file) issued WHILE a reindex is scanning a source with a large
    .worktrees subtree must complete in well under the 30s tool_timeout —
    not wait out the scan the way it did on prod pre-fix."""
    root = tmp_path / "repo"
    root.mkdir()
    decoys = root / ".worktrees" / "some-task"
    decoys.mkdir(parents=True)
    for i in range(5000):
        (decoys / f"f{i}.md").write_text(f"decoy {i}\n")
    (root / "doc0.md").write_text("# Doc 0\n\nreal content\n")

    settings = Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    embedder = BagEmbedder()
    indexer = Indexer(settings, embedder=embedder)
    # Open the writer's connection before reindex starts (migrations issue
    # their own write statements — opening it mid-reindex would itself block
    # on a held lock and silently absorb the wait this test measures).
    writer_store = SqliteStore(settings, embedder=embedder)

    result: dict = {}

    def _run_reindex():
        result["stats"] = indexer.reindex(sources=[Source(id="t", label="t", root=root)])

    thread = threading.Thread(target=_run_reindex)
    thread.start()

    write_t0 = time.perf_counter()
    writer_store.put("# Concurrent probe\n\nmust not wait out the scan", tags=["probe"])
    write_elapsed = time.perf_counter() - write_t0

    thread.join(timeout=10.0)

    assert not thread.is_alive(), "reindex thread did not finish"
    assert "stats" in result
    assert write_elapsed < 5.0, (
        f"concurrent trovex_write took {write_elapsed:.2f}s — scan of the ignored "
        "subtree is blocking the write path"
    )
