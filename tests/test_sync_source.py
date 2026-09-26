"""sync_source + gc_source job kinds on the index_jobs applier, and the
source_runs journal (task 960a4b64, design 61a37a82 6.3). Hermetic: BagEmbedder.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time

import numpy as np
import pytest

from trovex import connectors, index_jobs
from trovex import sources as sources_mod
from trovex.config import Settings
from trovex.connectors.base import Cursor, SlimRef
from trovex.index_jobs import Applier
from trovex.indexer import Indexer

DIM = 384
BASE_NS = 1_700_000_000 * 10**9
DAY = 86400


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


def _write(root, rel, text, mtime_ns):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    os.utime(p, ns=(mtime_ns, mtime_ns))
    return p


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    settings = Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    idx = Indexer(settings, embedder=BagEmbedder())
    sources_mod.add_source(idx.db, id="code", root=root)
    return idx, Applier(idx), root


def _run(idx, applier, kind, source_key="code"):
    r = index_jobs.enqueue(idx.db, applier.lock, kind, source_key=source_key)
    assert applier.run_one() is True
    job = index_jobs.get_job(idx.db, r["job_id"])
    assert job["state"] == "succeeded", job
    row = idx.db.execute(
        "SELECT * FROM source_runs WHERE source_id = ? ORDER BY id DESC LIMIT 1", (source_key,)
    ).fetchone()
    return dict(row)


def _doc(idx, path):
    return idx.db.execute(
        "SELECT * FROM docs WHERE source_id = 'code' AND path = ?", (path,)
    ).fetchone()


def _seed(root, n):
    for i in range(n):
        _write(root, f"d{i}.md", f"# Doc {i}\n\nbody number {i}", BASE_NS + i + 1)


# ── job kinds ──────────────────────────────────────────────────────────────


def test_sync_and_gc_are_job_kinds_that_coalesce_per_source(env):
    idx, applier, _root = env
    assert "sync_source" in index_jobs.KINDS and "gc_source" in index_jobs.KINDS
    r1 = index_jobs.enqueue(idx.db, applier.lock, "sync_source", source_key="code")
    r2 = index_jobs.enqueue(idx.db, applier.lock, "sync_source", source_key="code")
    r3 = index_jobs.enqueue(idx.db, applier.lock, "gc_source", source_key="code")
    assert r1["job_id"] == r2["job_id"] and r2["coalesced"] is True
    assert r3["job_id"] != r1["job_id"]


def test_sync_job_for_unknown_source_fails_the_job_not_the_applier(env):
    idx, applier, _root = env
    r = index_jobs.enqueue(idx.db, applier.lock, "sync_source", source_key="no-such")
    assert applier.run_one() is True
    job = index_jobs.get_job(idx.db, r["job_id"])
    assert job["state"] == "failed" and "no-such" in job["error"]


# ── sync_source ────────────────────────────────────────────────────────────


def test_sync_source_indexes_files_and_journals_a_source_run(env):
    idx, applier, root = env
    _seed(root, 3)

    run = _run(idx, applier, "sync_source")

    assert run["kind"] == "sync" and run["ended"] is not None
    assert (run["added"], run["updated"], run["removed"]) == (3, 0, 0)
    assert (run["ok"], run["failed"]) == (3, 0)
    assert json.loads(run["failures_json"]) == []
    assert json.loads(run["cursor_json"])["opaque"] == {"mtime_ns": BASE_NS + 3}
    assert run["error"] is None
    assert idx.db.execute("SELECT COUNT(*) c FROM docs WHERE source_id = 'code'").fetchone()["c"] == 3
    assert idx.db.execute("SELECT COUNT(*) c FROM vec_docs WHERE source_id = 'code'").fetchone()["c"] == 3


def test_sync_source_resumes_from_the_last_cursor(env):
    idx, applier, root = env
    _seed(root, 3)
    _run(idx, applier, "sync_source")

    quiet = _run(idx, applier, "sync_source")
    assert (quiet["added"], quiet["updated"], quiet["ok"]) == (0, 0, 0)

    _write(root, "d1.md", "# Doc 1\n\nrewritten body", BASE_NS + 50)
    _write(root, "new.md", "# New\n\nfresh", BASE_NS + 51)
    run = _run(idx, applier, "sync_source")
    assert (run["added"], run["updated"], run["ok"]) == (1, 1, 2)
    assert json.loads(run["cursor_json"])["opaque"] == {"mtime_ns": BASE_NS + 51}


def test_sync_source_records_failures_and_replays_only_the_failed_ids(env):
    idx, applier, root = env
    _seed(root, 3)
    bad = root / "d1.md"
    bad.chmod(0)
    try:
        run = _run(idx, applier, "sync_source")
    finally:
        bad.chmod(stat.S_IRUSR | stat.S_IWUSR)

    assert (run["ok"], run["failed"], run["added"]) == (2, 1, 2)
    failures = json.loads(run["failures_json"])
    assert [f["external_id"] for f in failures] == ["d1.md"]
    assert failures[0]["retryable"] is True and failures[0]["error"]
    assert _doc(idx, "d1.md") is None

    # File is readable again; the cursor already moved past it, so ONLY the replay of
    # the recorded failed id can pick it up.
    replay = _run(idx, applier, "sync_source")
    assert (replay["added"], replay["ok"], replay["failed"]) == (1, 1, 0)
    assert _doc(idx, "d1.md") is not None


def test_sync_source_commits_in_short_batches_never_corpus_wide(env, monkeypatch):
    idx, applier, root = env
    _seed(root, 7)
    monkeypatch.setattr("trovex.sync.SYNC_BATCH", 3)
    calls = []
    real = idx.reindex_paths

    def spy(paths, **kw):
        calls.append(len(paths))
        return real(paths, **kw)

    monkeypatch.setattr(idx, "reindex_paths", spy)
    run = _run(idx, applier, "sync_source")
    assert calls == [3, 3, 1]
    assert run["added"] == 7


# ── gc_source ──────────────────────────────────────────────────────────────


def test_gc_below_safety_ratio_aborts_and_journals_the_reason(env):
    idx, applier, root = env
    _seed(root, 10)
    _run(idx, applier, "sync_source")
    for i in range(2, 10):  # 8 of 10 vanish: listing/known = 0.2 < 0.5
        (root / f"d{i}.md").unlink()

    run = _run(idx, applier, "gc_source")

    assert run["kind"] == "gc" and run["removed"] == 0
    assert "deletion_safety_ratio" in run["error"]
    lifecycles = {r["lifecycle"] for r in idx.db.execute("SELECT lifecycle FROM docs WHERE source_id='code'")}
    assert lifecycles == {"active"}
    assert idx.db.execute("SELECT COUNT(*) c FROM docs WHERE source_id='code'").fetchone()["c"] == 10


def test_gc_over_ratio_moves_losers_to_pending_delete_and_hides_them(env):
    idx, applier, root = env
    _seed(root, 10)
    _run(idx, applier, "sync_source")
    (root / "d0.md").unlink()
    (root / "d1.md").unlink()

    run = _run(idx, applier, "gc_source")

    assert run["removed"] == 2 and run["error"] is None
    assert sorted(json.loads(run["removed_ids"])) == ["d0.md", "d1.md"]
    for path in ("d0.md", "d1.md"):
        d = _doc(idx, path)
        assert d["lifecycle"] == "pending_delete" and d["lifecycle_changed_at"] > 0
        v = idx.db.execute("SELECT lifecycle FROM vec_docs WHERE rowid = ?", (d["id"],)).fetchone()
        assert v["lifecycle"] == "pending_delete", "vec0 metadata must follow so search hides it"
    assert _doc(idx, "d2.md")["lifecycle"] == "active"


def test_gc_restores_a_pending_delete_doc_whose_file_returns(env):
    idx, applier, root = env
    _seed(root, 10)
    _run(idx, applier, "sync_source")
    gone = root / "d0.md"
    gone.unlink()
    _run(idx, applier, "gc_source")
    assert _doc(idx, "d0.md")["lifecycle"] == "pending_delete"

    _write(root, "d0.md", "# Doc 0\n\nbody number 0", BASE_NS + 1)
    _run(idx, applier, "gc_source")
    d = _doc(idx, "d0.md")
    assert d["lifecycle"] == "active"
    assert idx.db.execute("SELECT lifecycle FROM vec_docs WHERE rowid = ?", (d["id"],)).fetchone()[
        "lifecycle"
    ] == "active"


def test_gc_hard_deletes_after_the_grace_window_only(env):
    idx, applier, root = env
    _seed(root, 10)
    _run(idx, applier, "sync_source")
    (root / "d0.md").unlink()
    _run(idx, applier, "gc_source")
    doc_id = _doc(idx, "d0.md")["id"]

    _run(idx, applier, "gc_source")  # still inside the grace window
    assert _doc(idx, "d0.md") is not None

    grace = idx.settings.hard_delete_grace_days
    idx.db.execute(
        "UPDATE docs SET lifecycle_changed_at = ? WHERE id = ?", (time.time() - (grace + 1) * DAY, doc_id)
    )
    idx.db.commit()
    run = _run(idx, applier, "gc_source")

    assert _doc(idx, "d0.md") is None
    assert idx.db.execute("SELECT COUNT(*) c FROM vec_docs WHERE rowid = ?", (doc_id,)).fetchone()["c"] == 0
    assert "d0.md" in json.loads(run["removed_ids"])


class StubConnector:
    """A non-fs connector: only list_slim matters to gc_source."""

    kind = "stub"

    def __init__(self, source, indexer):
        self.listing = ["k0", "k1", "k2", "k3", "k4", "k5", "k6", "k7", "k8", "k9"]

    def list_slim(self):
        for i in self.listing:
            yield SlimRef(i, "v1", [], [])

    def poll(self, cursor):  # pragma: no cover - not exercised by gc
        return Cursor({}, 0)
        yield

    def fetch(self, ref):  # pragma: no cover
        raise NotImplementedError


def _insert_stub_doc(idx, ext, content):
    now = time.time()
    idx.db.execute(
        """INSERT INTO docs (source_id, path, absolute_path, content_hash, size_bytes, tokens_est,
                             mtime, first_indexed, last_indexed, title, content, external_id)
           VALUES ('ext', ?, '', ?, ?, 1, ?, ?, ?, ?, ?, ?)""",
        (ext, ext, len(content), now, now, now, ext, content, ext),
    )
    idx.db.commit()


def test_gc_tombstones_docs_whose_content_lives_in_the_db(env, monkeypatch, tmp_path):
    idx, applier, _root = env
    monkeypatch.setitem(connectors.REGISTRY, "stub", StubConnector)
    ext_root = tmp_path / "ext"
    ext_root.mkdir()
    sources_mod.add_source(idx.db, id="ext", kind="stub", root=ext_root)
    for i in range(10):
        _insert_stub_doc(idx, f"k{i}", f"remote body {i}")
    # k9 vanishes upstream: listing has 9 of 10 known ids.
    monkeypatch.setattr(StubConnector, "__init__", lambda self, s, i: setattr(self, "listing", [f"k{n}" for n in range(9)]))

    run = _run(idx, applier, "gc_source", source_key="ext")

    assert run["removed"] == 1 and json.loads(run["removed_ids"]) == ["k9"]
    doc = idx.db.execute("SELECT lifecycle FROM docs WHERE source_id='ext' AND path='k9'").fetchone()
    assert doc["lifecycle"] == "pending_delete"
    tomb = idx.db.execute("SELECT * FROM doc_tombstones WHERE ext_id = 'k9'").fetchone()
    assert tomb["content"] == "remote body 9" and tomb["source_id"] == "ext"
    # A file-backed (content IS NULL) loser gets no tombstone: its bytes stay on disk.
    assert idx.db.execute("SELECT COUNT(*) c FROM doc_tombstones WHERE source_id = 'code'").fetchone()["c"] == 0
