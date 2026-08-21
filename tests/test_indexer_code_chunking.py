"""Code-file chunk-level indexing (9299f37d): a .py/.go/.rs/.ts/.tsx file
scanned by Indexer gets cAST chunks (chunks/chunks_fts/vec_chunks), reusing
the same Merkle incremental sync markdown chunks already rely on. Markdown
files are NOT retroactively chunked by this wiring (scope containment)."""

from __future__ import annotations

import hashlib
import os
import re

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


def _reindex(settings, root, embedder):
    return Indexer(settings, embedder=embedder).reindex(sources=_src(root))


PY_SRC = (
    "import os\n\n\n"
    "def foo():\n    return 1\n\n\n"
    "class Bar:\n    def baz(self):\n        return 2\n"
)


def test_python_file_gets_chunk_level_indexing(settings, source_root):
    _write(source_root, "a.py", PY_SRC, mtime=1000)
    stats = _reindex(settings, source_root, CountingEmbedder())
    assert stats["added"] == 1

    idx = Indexer(settings, embedder=CountingEmbedder())
    doc_id = idx.db.execute("SELECT id FROM docs WHERE path = 'a.py'").fetchone()["id"]
    chunks = idx.db.execute(
        "SELECT heading_path, content FROM chunks WHERE doc_id = ?", (doc_id,)
    ).fetchall()
    assert len(chunks) >= 1
    joined = "\n".join(c["content"] for c in chunks)
    assert "def foo" in joined and "class Bar" in joined

    vec_count = idx.db.execute(
        "SELECT COUNT(*) AS c FROM vec_chunks WHERE rowid IN "
        "(SELECT id FROM chunks WHERE doc_id = ?)",
        (doc_id,),
    ).fetchone()["c"]
    assert vec_count == len(chunks)  # every chunk got an embedding


def test_markdown_file_gets_no_chunks_scope_containment(settings, source_root):
    """The new wiring must NOT retroactively chunk existing markdown docs —
    only code extensions dispatch through sync_doc_chunks in the indexer."""
    _write(source_root, "a.md", "# Alpha\n\nalpha body here\n", mtime=1000)
    _reindex(settings, source_root, CountingEmbedder())

    idx = Indexer(settings, embedder=CountingEmbedder())
    doc_id = idx.db.execute("SELECT id FROM docs WHERE path = 'a.md'").fetchone()["id"]
    n = idx.db.execute("SELECT COUNT(*) AS c FROM chunks WHERE doc_id = ?", (doc_id,)).fetchone()["c"]
    assert n == 0


def test_unchanged_code_file_reembeds_no_chunks(settings, source_root):
    """mtime unchanged -> _upsert_doc is never called -> zero chunk churn."""
    _write(source_root, "a.py", PY_SRC, mtime=1000)
    _reindex(settings, source_root, CountingEmbedder())

    second = CountingEmbedder()
    stats2 = _reindex(settings, source_root, second)
    assert stats2["unchanged"] == 1
    assert second.embedded == []


def test_edit_one_symbol_reembeds_only_that_chunk(settings, source_root):
    """Merkle reuse: editing foo()'s body must not touch baz()'s embedded chunk."""
    # Each function padded well past the 450-token merge budget so foo/baz
    # land in separate chunks instead of being greedily merged into one.
    pad = "    x = 1  # filler line to pad this function past the merge budget\n" * 60
    big_src = f"def foo():\n{pad}    return 1\n\n\nclass Bar:\n    def baz(self):\n{pad}        return 2\n"
    _write(source_root, "a.py", big_src, mtime=1000)
    _reindex(settings, source_root, CountingEmbedder())

    idx = Indexer(settings, embedder=CountingEmbedder())
    doc_id = idx.db.execute("SELECT id FROM docs WHERE path = 'a.py'").fetchone()["id"]
    before = {
        r["content_hash"]: r["id"]
        for r in idx.db.execute("SELECT id, content_hash FROM chunks WHERE doc_id = ?", (doc_id,)).fetchall()
    }
    assert len(before) >= 2, "expected foo and baz in separate chunks"

    revised = big_src.replace("return 1", "return 999  # revised")
    _write(source_root, "a.py", revised, mtime=2000)
    second = CountingEmbedder()
    _reindex(settings, source_root, second)

    # baz's chunk hash is unchanged -> its row id is reused, never re-embedded.
    after = {
        r["content_hash"]: r["id"]
        for r in idx.db.execute("SELECT id, content_hash FROM chunks WHERE doc_id = ?", (doc_id,)).fetchall()
    }
    unchanged_hashes = set(before) & set(after)
    assert unchanged_hashes, "expected at least one chunk (e.g. baz) untouched by the edit"
    for h in unchanged_hashes:
        assert before[h] == after[h]
    assert any("999" in t for t in second.embedded)  # the revised chunk WAS re-embedded


def test_deleted_code_file_prunes_its_chunks(settings, source_root):
    _write(source_root, "a.py", PY_SRC, mtime=1000)
    _reindex(settings, source_root, CountingEmbedder())

    idx = Indexer(settings, embedder=CountingEmbedder())
    doc_id = idx.db.execute("SELECT id FROM docs WHERE path = 'a.py'").fetchone()["id"]
    assert idx.db.execute("SELECT COUNT(*) AS c FROM chunks WHERE doc_id = ?", (doc_id,)).fetchone()["c"] > 0

    (source_root / "a.py").unlink()
    _reindex(settings, source_root, CountingEmbedder())

    idx2 = Indexer(settings, embedder=CountingEmbedder())
    assert idx2.db.execute("SELECT COUNT(*) AS c FROM chunks WHERE doc_id = ?", (doc_id,)).fetchone()["c"] == 0
    assert idx2.db.execute("SELECT COUNT(*) AS c FROM vec_chunks").fetchone()["c"] == 0


def test_other_v1_extensions_are_scanned(settings, source_root):
    _write(source_root, "main.go", "package main\n\nfunc Foo() {}\n", mtime=1000)
    _write(source_root, "lib.rs", "fn foo() {}\n", mtime=1000)
    _write(source_root, "app.ts", "function foo() {}\n", mtime=1000)
    _write(source_root, "App.tsx", "function App() { return null; }\n", mtime=1000)
    stats = _reindex(settings, source_root, CountingEmbedder())
    assert stats["added"] == 4

    idx = Indexer(settings, embedder=CountingEmbedder())
    n = idx.db.execute("SELECT COUNT(*) AS c FROM chunks").fetchone()["c"]
    assert n >= 4  # at least one chunk per file
