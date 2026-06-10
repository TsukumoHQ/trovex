"""v0.9 — ctx-owned store: write/read roundtrip, semantic routing, lifecycle.

Hermetic: a deterministic bag-of-words embedder (no OpenAI / no model download).
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import re
import time

import numpy as np
import pytest

from ctx.config import Settings, Source
from ctx.indexer import Indexer
from ctx.search import Searcher
from ctx.status import compute_status
from ctx.store import SqliteStore, extract_section

DIM = 384


class BagEmbedder:
    """Stable hashing bag-of-words embedder — shared tokens → high cosine."""

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
        embed_model="BAAI/bge-small-en-v1.5",  # dim 384, matches BagEmbedder
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


@pytest.fixture
def store(settings):
    return SqliteStore(settings, embedder=BagEmbedder())


def test_put_get_roundtrip(store):
    body = "# Outage 2026-06-09\n\nThe auth database ran out of connections."
    ext_id = store.put(body, kind="record")
    assert ext_id
    doc = store.get(ext_id)
    assert doc is not None
    assert doc.content == body
    assert doc.kind == "record"
    assert doc.title == "Outage 2026-06-09"


def test_put_with_id_overwrites(store):
    ext_id = store.put("first version")
    store.put("second version", ext_id=ext_id)
    doc = store.get(ext_id)
    assert doc.content == "second version"
    # No duplicate row created.
    assert len(store.list_docs()) == 1


def test_get_unknown_returns_none(store):
    assert store.get("does-not-exist") is None


def test_read_by_query_routes_to_right_doc(settings, store):
    """ctx_read's query path: search restricted to source_id='ctx' returns the
    matching doc's ext_id, which the Store resolves to content."""
    auth = store.put("# Auth incident\n\njwt token signature validation failed")
    deploy = store.put("# Deploy rollback\n\nthe kubernetes pod crash looped")

    searcher = Searcher(settings, embedder=BagEmbedder())
    results = searcher.search("jwt token signature", limit=1, source_ids=["ctx"])
    assert results, "expected a ctx-owned match"
    assert results[0].path == auth  # SearchResult.path holds the ext_id
    assert results[0].path != deploy


def test_record_not_stale_by_age(settings, store):
    """A record stays canonical no matter how old; a non-record goes stale."""
    rec = store.put("# Old incident", kind="record")
    living = store.put("# Old note")  # kind is None → a normal living doc

    old = time.time() - settings.stale_age_days * 86400 - 86400  # past the cutoff
    store.db.execute("UPDATE docs SET mtime = ?", (old,))
    store.db.commit()

    compute_status(store.db, settings)

    assert store.get(rec).status == "canonical"
    assert store.get(living).status == "stale"


def test_indexer_does_not_purge_ctx_docs(settings, store, tmp_path):
    """The filesystem indexer must never delete ctx-owned docs (they have no
    file on disk). It only touches the source it scans."""
    ext_id = store.put("# Survives reindex", kind="record")

    empty_source = tmp_path / "repo"
    empty_source.mkdir()
    indexer = Indexer(settings, embedder=BagEmbedder())
    indexer.reindex(sources=[Source(id="code", label="repo", root=empty_source)])

    assert store.get(ext_id) is not None


def test_extract_section():
    doc = "# Title\n\nintro\n\n## Alpha\n\naaa\n\n## Beta\n\nbbb\n\n### Beta sub\n\nccc\n"
    assert extract_section(doc, "Alpha") == "## Alpha\n\naaa"
    beta = extract_section(doc, "Beta")
    assert "bbb" in beta and "ccc" in beta  # keeps its deeper ### subheading
    assert "aaa" not in beta
    assert extract_section(doc, "Nonexistent") is None


def test_concurrent_puts_are_serialized(store):
    def write(i):
        return store.put(f"# Doc {i}\n\nbody {i}", ext_id=f"id-{i}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        ids = list(ex.map(write, range(20)))

    assert len(set(ids)) == 20
    assert len(store.list_docs()) == 20
    assert store.get("id-7").content == "# Doc 7\n\nbody 7"
