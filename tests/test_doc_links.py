"""Typed doc_links (task edaf8627) — supersedes/verdict-of/decided-in/resume-of
edges written at capture time, as-of resolution, current_only search filtering,
and cascade-delete. Hermetic: bag-of-words embedder, no model download."""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex.config import Settings
from trovex.store import SqliteStore

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
def store(settings):
    return SqliteStore(settings, embedder=BagEmbedder())


def _doc_id(store: SqliteStore, ext_id: str) -> int:
    return store.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext_id,)).fetchone()["id"]


# --- AC1: doc_links table + trovex_write (store.put) accepts links, rejects unknown rels ---


def test_put_with_links_creates_doc_links_row(store):
    old = store.put("# Old decision\n\nwe use postgres", kind="record")
    new = store.put(
        "# New decision\n\nwe use sqlite",
        kind="record",
        links=[{"rel": "supersedes", "target": old}],
    )
    row = store.db.execute(
        "SELECT rel, src_doc_id, dst_doc_id FROM doc_links"
    ).fetchone()
    assert row["rel"] == "supersedes"
    assert row["src_doc_id"] == _doc_id(store, new)
    assert row["dst_doc_id"] == _doc_id(store, old)


def test_put_accepts_a_short_prefix_target(store):
    old = store.put("# Old\n\ncontent one", kind="record")
    new = store.put("# New\n\ncontent two", kind="record", links=[{"rel": "supersedes", "target": old[:8]}])
    row = store.db.execute("SELECT dst_doc_id FROM doc_links").fetchone()
    assert row["dst_doc_id"] == _doc_id(store, old)
    assert new  # sanity


def test_put_rejects_unknown_rel_and_writes_nothing(store):
    old = store.put("# Old\n\ncontent", kind="record")
    with pytest.raises(ValueError, match="unknown link rel"):
        store.put(
            "# Bad\n\nnever stored",
            ext_id="bad-doc",
            links=[{"rel": "obsoletes", "target": old}],
        )
    assert store.get("bad-doc") is None  # whole write rolled back, not half-applied
    assert store.db.execute("SELECT COUNT(*) AS c FROM doc_links").fetchone()["c"] == 0


def test_put_rejects_unresolvable_target_and_writes_nothing(store):
    with pytest.raises(ValueError, match="not found"):
        store.put(
            "# Bad\n\nnever stored",
            ext_id="bad-doc-2",
            links=[{"rel": "supersedes", "target": "no-such-doc"}],
        )
    assert store.get("bad-doc-2") is None
    assert store.db.execute("SELECT COUNT(*) AS c FROM doc_links").fetchone()["c"] == 0


def test_put_links_idempotent_on_identical_redeclare(store):
    old = store.put("# Old\n\ncontent", kind="record")
    new = store.put("# New\n\nv1", kind="record", ext_id="new-doc", links=[{"rel": "supersedes", "target": old}])
    # Same content + same link, re-declared — must not raise a UNIQUE violation.
    store.put("# New\n\nv1", kind="record", ext_id="new-doc", links=[{"rel": "supersedes", "target": old}])
    assert store.db.execute("SELECT COUNT(*) AS c FROM doc_links").fetchone()["c"] == 1
    assert new == "new-doc"


def test_put_writes_multiple_rel_kinds(store):
    ticket = store.put("# Ticket\n\nfix the thing", kind="record")
    verdict = store.put(
        "# QA verdict\n\napproved",
        kind="record",
        links=[{"rel": "verdict-of", "target": ticket}],
    )
    rels = {r["rel"] for r in store.db.execute("SELECT rel FROM doc_links")}
    assert rels == {"verdict-of"}
    assert verdict


# --- AC2: trovex_read(as_of=...) resolves a supersedes chain to the version valid at that time ---


def test_resolve_as_of_walks_a_three_version_chain(store, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr("trovex.store.time.time", lambda: clock["t"])

    clock["t"] = 1000.0
    v1 = store.put("# Decision\n\nuse postgres", kind="record", ext_id="decision")
    t1 = clock["t"]

    clock["t"] = 2000.0
    v2 = store.put("# Decision v2\n\nuse sqlite for local dev, postgres in prod", kind="record", ext_id="decision-v2",
                    links=[{"rel": "supersedes", "target": v1}])
    t2 = clock["t"]

    clock["t"] = 3000.0
    v3 = store.put("# Decision v3\n\nsqlite everywhere, postgres retired", kind="record", ext_id="decision-v3",
                    links=[{"rel": "supersedes", "target": v2}])
    t3 = clock["t"]

    # Before v1 even existed: no older version reachable — falls back to the oldest.
    assert store.resolve_as_of(v3, t1 - 500) == v1
    # Between v1 and v2 → v1 was current.
    assert store.resolve_as_of(v3, t1 + 500) == v1
    # Between v2 and v3 → v2 was current.
    assert store.resolve_as_of(v3, t2 + 500) == v2
    # At/after v3's own creation → v3 itself.
    assert store.resolve_as_of(v3, t3) == v3
    assert store.resolve_as_of(v3, t3 + 500) == v3
    # Starting the walk from a MIDDLE node (v2) for an earlier as_of still reaches v1.
    assert store.resolve_as_of(v2, t1 + 500) == v1


def test_resolve_as_of_returns_input_unchanged_when_unlinked(store):
    solo = store.put("# Solo\n\nnever superseded", kind="record")
    assert store.resolve_as_of(solo, 0.0) == solo
    assert store.resolve_as_of(solo, 99999999999.0) == solo


def test_resolve_as_of_unknown_doc_returns_input(store):
    assert store.resolve_as_of("no-such-doc", 123.0) == "no-such-doc"


# --- AC3: current_only hides a supersedes target by default ---


def test_search_chunks_hides_superseded_target_by_default(store):
    old = store.put("# Decision\n\nauth flow uses redis sessions", kind="record", ext_id="decision-old")
    store.put(
        "# Decision v2\n\nauth flow uses redis sessions but jwt now",
        kind="record",
        ext_id="decision-new",
        links=[{"rel": "supersedes", "target": old}],
    )

    default_hits = store.search_chunks("auth flow redis sessions", limit=5)
    assert "decision-old" not in {h["ext_id"] for h in default_hits}
    assert "decision-new" in {h["ext_id"] for h in default_hits}

    all_hits = store.search_chunks("auth flow redis sessions", limit=5, current_only=False)
    assert "decision-old" in {h["ext_id"] for h in all_hits}


def test_search_chunks_current_only_does_not_hide_unlinked_docs(store):
    store.put("# Unrelated\n\nauth flow redis sessions", kind="record", ext_id="solo")
    hits = store.search_chunks("auth flow redis sessions", limit=5)
    assert "solo" in {h["ext_id"] for h in hits}


# --- AC4: delete_doc_cascade prunes doc_links in both directions ---


def test_delete_prunes_doc_links_as_source(store):
    old = store.put("# Old\n\ncontent", kind="record", ext_id="old-doc")
    new = store.put("# New\n\ncontent v2", kind="record", ext_id="new-doc", links=[{"rel": "supersedes", "target": old}])
    assert store.db.execute("SELECT COUNT(*) AS c FROM doc_links").fetchone()["c"] == 1

    assert store.delete(new)

    assert store.db.execute("SELECT COUNT(*) AS c FROM doc_links").fetchone()["c"] == 0


def test_delete_prunes_doc_links_as_target(store):
    old = store.put("# Old\n\ncontent", kind="record", ext_id="old-doc-2")
    store.put("# New\n\ncontent v2", kind="record", ext_id="new-doc-2", links=[{"rel": "supersedes", "target": old}])
    assert store.db.execute("SELECT COUNT(*) AS c FROM doc_links").fetchone()["c"] == 1

    assert store.delete(old)

    assert store.db.execute("SELECT COUNT(*) AS c FROM doc_links").fetchone()["c"] == 0
