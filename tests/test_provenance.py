"""Provenance envelope (steal #6): docs + chunks carry where a record came from
and how to re-fetch it; every search hit and trovex_read slice serves it.

Hermetic: deterministic BagEmbedder, no model download / network.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3

import numpy as np
import pytest

from trovex import mcp_app
from trovex import state as state_mod
from trovex.config import Settings, Source
from trovex.db import open_db
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.state import AppState
from trovex.store import SqliteStore

DIM = 384

_DOC_COLS = (
    "external_id",
    "source_url",
    "record_locator",
    "remote_version",
    "remote_updated_at",
    "owners",
    "parents",
    "fetched_at",
)


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


def _settings(tmp_path):
    return Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


def _cols(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}  # noqa: S608


def _fs_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "notes.md").write_text("# Notes\n\nplain markdown one\nsecond line\n")
    (root / "guide.md").write_text("# Guide\n\nplain markdown two\n")
    (root / "svc.py").write_text(
        "def quokka_router(x):\n    \"\"\"route the quokka request\"\"\"\n    return x * 2\n"
    )
    return root


@pytest.fixture
def wired(tmp_path, monkeypatch):
    monkeypatch.setenv("TROVEX_ALLOW_UNAUTH_WRITES", "1")
    settings = _settings(tmp_path)
    store = SqliteStore(settings, embedder=BagEmbedder())
    indexer = Indexer(settings, embedder=BagEmbedder())
    root = _fs_root(tmp_path)
    indexer.reindex(sources=[Source(id="code", label="repo", root=root)])
    state_mod._state = AppState(
        settings=settings,
        embedder=BagEmbedder(),
        searcher=Searcher(settings, embedder=BagEmbedder()),
        indexer=indexer,
        store=store,
    )
    try:
        yield state_mod._state, root
    finally:
        state_mod.reset_state()


def test_migration_adds_provenance_and_is_idempotent_on_pre_migration_store(tmp_path):
    settings = _settings(tmp_path)
    store = SqliteStore(settings, embedder=BagEmbedder())
    ext_id = store.put("# Runbook\n\n## Deploy step\n\nrestart the quokka pool\n", kind="record")
    Indexer(settings, embedder=BagEmbedder()).reindex(
        sources=[Source(id="code", label="repo", root=_fs_root(tmp_path))]
    )
    db = store.db
    # Rewind to the pre-migration shape: drop every provenance column.
    for col in _DOC_COLS:
        db.execute(f"ALTER TABLE docs DROP COLUMN {col}")  # noqa: S608
    for col in ("anchor", "link"):
        db.execute(f"ALTER TABLE chunks DROP COLUMN {col}")  # noqa: S608
    db.commit()
    db.close()
    assert not (set(_DOC_COLS) & _cols(_raw(settings), "docs"))

    for _ in range(2):  # opening twice must be a no-op the second time
        conn = open_db(settings.data_dir / "trovex.db", settings.resolved_embed_dim(), "")
        assert set(_DOC_COLS) <= _cols(conn, "docs")
        assert {"anchor", "link"} <= _cols(conn, "chunks")
        owned = conn.execute(
            "SELECT c.anchor, c.link FROM chunks c JOIN docs d ON d.id = c.doc_id "
            "WHERE d.ext_id = ? AND c.heading_path LIKE '%Deploy step'",
            (ext_id,),
        ).fetchone()
        assert owned["anchor"] == "deploy-step"
        assert owned["link"] == f"trovex:{ext_id}#deploy-step"
        fs = conn.execute(
            "SELECT record_locator FROM docs WHERE path = 'notes.md'"
        ).fetchone()
        assert json.loads(fs["record_locator"]) == {"path": "notes.md"}
        py = conn.execute(
            "SELECT c.link FROM chunks c JOIN docs d ON d.id = c.doc_id WHERE d.path = 'svc.py'"
        ).fetchone()
        assert py["link"].startswith("file://") and "svc.py#" in py["link"]
        assert conn.execute("SELECT COUNT(*) FROM chunks WHERE anchor = ''").fetchone()[0] == 0
        conn.close()


def _raw(settings):
    conn = sqlite3.connect(str(settings.data_dir / "trovex.db"))
    conn.row_factory = sqlite3.Row
    return conn


def test_indexer_fills_record_locator_and_chunk_anchor_on_three_docs(wired):
    state, root = wired
    db = state.store.db
    rows = {r["path"]: r for r in db.execute("SELECT path, record_locator, fetched_at FROM docs")}
    assert set(rows) == {"notes.md", "guide.md", "svc.py"}
    for path, n_lines in (("notes.md", 5), ("guide.md", 4), ("svc.py", 4)):
        loc = json.loads(rows[path]["record_locator"])
        assert loc["path"] == path
        assert loc["line_range"] == [1, n_lines]
        assert rows[path]["fetched_at"] > 0
    chunks = db.execute(
        "SELECT c.anchor, c.link FROM chunks c JOIN docs d ON d.id = c.doc_id "
        "WHERE d.path = 'svc.py'"
    ).fetchall()
    assert chunks
    for c in chunks:
        assert c["anchor"]
        assert c["link"] == f"file://{root / 'svc.py'}#{c['anchor']}"


def test_search_hit_and_read_slice_serve_link_and_record_locator(wired):
    _state, root = wired
    out = mcp_app.trovex_search(q="quokka_router route quokka request", source="*")
    assert f"↳ file://{root / 'svc.py'}#" in out
    assert 'loc={"path":"svc.py","line_range":[1,4]}' in out
    passage = mcp_app.trovex_read(query="quokka_router route quokka request")
    assert f"↳ file://{root / 'svc.py'}#" in passage
    assert '"path":"svc.py"' in passage


def test_read_section_of_owned_doc_serves_anchored_link(wired):
    state, _ = wired
    ext_id = state.store.put("# Runbook\n\n## Deploy step\n\nrestart the pool\n", kind="record")
    out = mcp_app.trovex_read(doc_id=ext_id, section="Deploy step")
    assert f"↳ trovex:{ext_id}#deploy-step" in out
    hit = mcp_app.trovex_search(q="restart the pool deploy step")
    assert f"↳ trovex:{ext_id}#deploy-step" in hit
