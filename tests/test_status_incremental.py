"""compute_status incremental path (task 7595a3ee, fast-follow to cbb8e8fb).

Root cause: prod measurement (index_runs id 748, right after cbb8e8fb deployed)
showed compute_status at 14236ms of a 17635ms reindex (80.7%) for only 2
changed docs of 2013 — it unconditionally re-derives plan/stale/duplicate/
canonical for EVERY non-superseded doc, every run. Profiling a copy of the
prod store (3637 docs) attributed 88.9% of a full recompute (5321/5987ms) to
Pass 2's duplicate-detection KNN loop; collision resolution + Pass 1 were a
combined ~11%.

Fix: compute_status(db, settings, touched_doc_ids=...) restricts Pass 2's
DRIVER rows, Pass 1's scan, and collision resolution's topic scope to the
touched docs (+ their existing canonical_topic peers, found via a topic
lookup) — see status.py's compute_status docstring for the exact scoping and
its one accepted gap (age-based staleness on an untouched doc). indexer.py
skips the call entirely when nothing was added/updated/removed, and falls
back to a FULL recompute (touched_doc_ids=None) whenever anything was
removed (a removed canonical's topic can't be reasoned about incrementally).

Hermetic: a deterministic bag-of-words embedder, no network.
"""

from __future__ import annotations

import hashlib
import re
import time

import numpy as np
import pytest

from typer.testing import CliRunner

from trovex.cli import app
from trovex.config import Settings, Source
from trovex.indexer import Indexer
from trovex.status import compute_status
from trovex.store import SqliteStore

DIM = 384

# Reused from test_active_memory.py's proven near-duplicate recipe: distinct
# titles (distinct canonical_topic, no SSOT collision) but near-identical
# bodies — high cosine similarity under BagEmbedder, reliably crosses the
# default dup_cosine_threshold.
DUP_BODY = "deploy rollback runbook incident response mitigation steps canonical procedure notes"


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


class CountingComputeStatusSpy:
    """Wraps status.compute_status, recording every call's touched_doc_ids."""

    def __init__(self, real):
        self.real = real
        self.calls: list[list[int] | None] = []

    def __call__(self, db, settings, touched_doc_ids=None):
        self.calls.append(touched_doc_ids)
        return self.real(db, settings, touched_doc_ids=touched_doc_ids)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


def _statuses_by_title(db) -> dict[str, tuple[str, str | None]]:
    """{title: (status, dup_of_title-or-None)} — stable across two separate
    stores whose ext_ids/ids differ but whose docs share titles."""
    rows = db.execute("SELECT id, title, status, dup_of_id FROM docs").fetchall()
    by_id = {r["id"]: r["title"] for r in rows}
    return {
        r["title"]: (r["status"], by_id.get(r["dup_of_id"]) if r["dup_of_id"] else None)
        for r in rows
    }


def test_incremental_duplicate_detection_matches_full_after_add(tmp_path):
    """Add a doc into an existing near-duplicate group: the incremental path
    (touched_doc_ids=[new doc]) must classify EXACTLY like a full recompute
    would, including demoting the pre-existing OLDER doc it didn't touch."""
    settings_a = Settings(data_dir=tmp_path / "a", embed_model="BAAI/bge-small-en-v1.5")
    settings_b = Settings(data_dir=tmp_path / "b", embed_model="BAAI/bge-small-en-v1.5")
    store_a = SqliteStore(settings_a, embedder=BagEmbedder())
    store_b = SqliteStore(settings_b, embedder=BagEmbedder())

    for store in (store_a, store_b):
        store.put(f"# Deploy rollback runbook alpha\n\n{DUP_BODY}", kind="reference")
        compute_status(store.db, store.settings)  # baseline: alpha alone, canonical

    # Add the near-duplicate to both stores identically.
    beta_a = store_a.put(f"# Deploy rollback runbook beta\n\n{DUP_BODY}", kind="reference")
    store_b.put(f"# Deploy rollback runbook beta\n\n{DUP_BODY}", kind="reference")
    beta_id_a = store_a.db.execute("SELECT id FROM docs WHERE ext_id = ?", (beta_a,)).fetchone()["id"]

    compute_status(store_a.db, store_a.settings, touched_doc_ids=[beta_id_a])  # incremental
    compute_status(store_b.db, store_b.settings)  # full

    result_a = _statuses_by_title(store_a.db)
    result_b = _statuses_by_title(store_b.db)
    assert result_a == result_b
    # Sanity: the group actually collapsed (not a vacuous equality of no-ops).
    statuses = sorted(s for s, _ in result_a.values())
    assert statuses == ["canonical", "duplicate"]


def test_incremental_canonical_topic_collision_matches_full_after_add(tmp_path):
    """Two docs land with the SAME canonical_topic (simulating the live
    2026-08-22 collision class compute_status's step 1 exists to fix — bypass
    store.put()'s own SSOT guard via a raw INSERT, since that guard would
    otherwise resolve the collision before compute_status ever sees it).
    Incremental (touched_doc_ids=[the new row]) must resolve the collision
    identically to a full recompute."""

    def _seed(settings):
        store = SqliteStore(settings, embedder=BagEmbedder())
        winner = store.put("# Auth Setup\n\nhow to configure auth", kind="reference")
        winner_row = store.db.execute(
            "SELECT id, canonical_topic FROM docs WHERE ext_id = ?", (winner,)
        ).fetchone()
        topic = winner_row["canonical_topic"]
        assert topic  # the recipe depends on this being set
        # Raw insert: a 2nd doc sharing the SAME topic, bypassing store.put()'s
        # own TopicCollisionError guard. status='plan' (not 'canonical') —
        # the partial unique index idx_docs_canonical_topic enforces
        # uniqueness AT INSERT TIME for status='canonical', so a genuine
        # collision can only exist pre-resolution with a non-canonical status;
        # compute_status's step 1 is what promotes the eventual winner.
        now = time.time()
        cur = store.db.execute(
            """INSERT INTO docs (source_id, path, absolute_path, content_hash, size_bytes,
               tokens_est, mtime, first_indexed, last_indexed, title, content, ext_id,
               kind, canonical_topic, status)
               VALUES ('trovex', ?, '', 'h2', 10, 3, ?, ?, ?, ?, ?, ?, ?, ?, 'plan')""",
            (
                "intruder-ext",
                now,
                now,
                now,
                "Auth Setup Intruder",
                "a later doc that collides on topic",
                "intruder-ext",
                "reference",
                topic,
            ),
        )
        store.db.commit()
        return store, cur.lastrowid

    store_a, intruder_id_a = _seed(Settings(data_dir=tmp_path / "ca", embed_model="BAAI/bge-small-en-v1.5"))
    store_b, _intruder_id_b = _seed(Settings(data_dir=tmp_path / "cb", embed_model="BAAI/bge-small-en-v1.5"))

    compute_status(store_a.db, store_a.settings, touched_doc_ids=[intruder_id_a])  # incremental
    compute_status(store_b.db, store_b.settings)  # full

    result_a = _statuses_by_title(store_a.db)
    result_b = _statuses_by_title(store_b.db)
    assert result_a == result_b
    statuses = sorted(s for s, _ in result_a.values())
    assert statuses == ["canonical", "duplicate"], "the topic collision must resolve to one winner"


def test_incremental_matches_full_after_update_and_remove(tmp_path):
    """An UPDATE that changes which doc is newer, and a REMOVE that changes
    the surviving canonical, must both resolve identically incremental vs
    full — remove specifically exercises the "no doc left canonical" edge."""
    settings_a = Settings(data_dir=tmp_path / "u_a", embed_model="BAAI/bge-small-en-v1.5")
    settings_b = Settings(data_dir=tmp_path / "u_b", embed_model="BAAI/bge-small-en-v1.5")
    store_a = SqliteStore(settings_a, embedder=BagEmbedder())
    store_b = SqliteStore(settings_b, embedder=BagEmbedder())

    for store in (store_a, store_b):
        store.put(f"# Deploy rollback runbook alpha\n\n{DUP_BODY}", kind="reference")
        store.put(f"# Deploy rollback runbook beta\n\n{DUP_BODY}", kind="reference")
        compute_status(store.db, store.settings)  # baseline: one canonical, one duplicate

    # UPDATE alpha's content (still near-dup of beta, but touches alpha this time).
    alpha_a = store_a.db.execute(
        "SELECT ext_id FROM docs WHERE title LIKE 'Deploy rollback runbook alpha%'"
    ).fetchone()["ext_id"]
    alpha_b = store_b.db.execute(
        "SELECT ext_id FROM docs WHERE title LIKE 'Deploy rollback runbook alpha%'"
    ).fetchone()["ext_id"]
    store_a.put(f"# Deploy rollback runbook alpha\n\n{DUP_BODY} revised", ext_id=alpha_a, kind="reference")
    store_b.put(f"# Deploy rollback runbook alpha\n\n{DUP_BODY} revised", ext_id=alpha_b, kind="reference")
    alpha_id_a = store_a.db.execute("SELECT id FROM docs WHERE ext_id = ?", (alpha_a,)).fetchone()["id"]

    compute_status(store_a.db, store_a.settings, touched_doc_ids=[alpha_id_a])
    compute_status(store_b.db, store_b.settings)
    assert _statuses_by_title(store_a.db) == _statuses_by_title(store_b.db)

    # REMOVE: delete whichever doc the update left canonical — the "no doc
    # left canonical" edge. The survivor's dup_of_id pointed at a row that no
    # longer exists; incremental (touched_doc_ids=[survivor]) must promote it
    # back to canonical, matching a full recompute, when the caller correctly
    # scopes touched_doc_ids to the group's surviving member.
    rows_a = store_a.db.execute("SELECT id, ext_id, title, status FROM docs").fetchall()
    canonical_a = next(r for r in rows_a if r["status"] == "canonical")
    survivor_a = next(r for r in rows_a if r["status"] != "canonical")
    rows_b = store_b.db.execute("SELECT id, ext_id, title, status FROM docs").fetchall()
    canonical_b = next(r for r in rows_b if r["status"] == "canonical")
    assert canonical_a["title"] == canonical_b["title"]  # mirrored updates kept both stores in lockstep

    store_a.delete(canonical_a["ext_id"])
    store_b.delete(canonical_b["ext_id"])

    compute_status(store_a.db, store_a.settings, touched_doc_ids=[survivor_a["id"]])  # incremental
    compute_status(store_b.db, store_b.settings)  # full

    result_a = _statuses_by_title(store_a.db)
    result_b = _statuses_by_title(store_b.db)
    assert result_a == result_b
    assert result_a[survivor_a["title"]] == (
        "canonical",
        None,
    ), "surviving doc must be promoted to canonical once its group's canonical is removed"


def test_removed_doc_forces_full_recompute_via_reindex(tmp_path, settings, monkeypatch):
    """A run with a removal must NOT call compute_status incrementally — the
    spy records touched_doc_ids=None (full) whenever anything was removed."""
    import trovex.status as status_mod

    src_root = tmp_path / "repo"
    src_root.mkdir()
    (src_root / "a.md").write_text("# Alpha\n\nalpha body", encoding="utf-8")
    (src_root / "b.md").write_text("# Bravo\n\nbravo body", encoding="utf-8")
    idx = Indexer(settings, embedder=BagEmbedder())
    idx.reindex(sources=[Source(id="code", label="repo", root=src_root)])

    spy = CountingComputeStatusSpy(status_mod.compute_status)
    monkeypatch.setattr(status_mod, "compute_status", spy)

    (src_root / "a.md").unlink()  # removal
    idx.reindex(sources=[Source(id="code", label="repo", root=src_root)])

    assert spy.calls == [None], f"expected exactly one full-recompute call, got {spy.calls}"


def test_unchanged_2000_doc_corpus_reindex_under_5s_including_status(settings, tmp_path):
    """AC: unchanged-corpus reindex on the 2000-doc fixture completes under 5s
    wall INCLUDING status — the AC cbb8e8fb carried and that prod (with its
    real compute_status cost) missed."""
    src_root = tmp_path / "repo"
    src_root.mkdir()
    for i in range(2000):
        (src_root / f"doc{i}.md").write_text(f"# Doc {i}\n\nbody text for doc {i}", encoding="utf-8")

    idx = Indexer(settings, embedder=BagEmbedder())
    idx.reindex(sources=[Source(id="code", label="repo", root=src_root)])  # warm the store

    idx2 = Indexer(settings, embedder=BagEmbedder())
    stats = idx2.reindex(sources=[Source(id="code", label="repo", root=src_root)])

    assert stats["unchanged"] == 2000
    assert stats["phase_ms"]["status"] == 0
    assert stats["wall_ms"] < 5000, f"unchanged 2000-doc reindex took {stats['wall_ms']:.0f}ms"


def test_unchanged_run_does_not_call_compute_status(tmp_path, settings, monkeypatch):
    """AC: docs_changed == 0, nothing removed -> compute_status is never
    called at all (not even with an empty list), and phase_ms['status'] is 0."""
    import trovex.status as status_mod

    src_root = tmp_path / "repo"
    src_root.mkdir()
    (src_root / "a.md").write_text("# Alpha\n\nalpha body", encoding="utf-8")
    idx = Indexer(settings, embedder=BagEmbedder())
    idx.reindex(sources=[Source(id="code", label="repo", root=src_root)])

    spy = CountingComputeStatusSpy(status_mod.compute_status)
    monkeypatch.setattr(status_mod, "compute_status", spy)

    stats = idx.reindex(sources=[Source(id="code", label="repo", root=src_root)])

    assert spy.calls == [], f"expected zero calls on an unchanged run, got {spy.calls}"
    assert stats["phase_ms"]["status"] == 0


def test_cli_status_command_runs_full_recompute(tmp_path, monkeypatch):
    """AC: full recompute remains available behind a CLI command (`trovex
    status`) — it must call compute_status with touched_doc_ids=None (full),
    not skip or scope it, regardless of what's in the store."""
    import trovex.status as status_mod

    monkeypatch.setenv("TROVEX_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TROVEX_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
    store = SqliteStore(Settings(data_dir=tmp_path, embed_model="BAAI/bge-small-en-v1.5"), embedder=BagEmbedder())
    store.put("# Alpha\n\nalpha body", kind="reference")

    spy = CountingComputeStatusSpy(status_mod.compute_status)
    monkeypatch.setattr(status_mod, "compute_status", spy)

    runner = CliRunner()
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    assert spy.calls == [None], f"expected exactly one FULL (touched_doc_ids=None) call, got {spy.calls}"
