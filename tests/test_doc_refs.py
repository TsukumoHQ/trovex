"""Obsidian-style extracted doc links (task a1b5a169, trovex/links L1).

Covers the parser (wikilinks + relative .md links, code-fence/inline-code skip,
anchor/alias/context), resolution + dangling persistence, dangling re-bind on
rename / future-doc appearance, owned-doc -> file-backed resolution, and the
delete_doc_cascade two-sided behaviour. Hermetic: bag-of-words embedder, no
model download.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex import sources as sources_mod
from trovex.config import Settings
from trovex.indexer import Indexer
from trovex.links_parse import parse_links
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
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


@pytest.fixture
def idx(settings, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    indexer = Indexer(settings, embedder=BagEmbedder())
    sources_mod.add_source(indexer.db, id="code", root=root)
    return indexer, root


def _reindex(indexer):
    return indexer.reindex(sources=indexer.settings.load_sources())


def _refs_from(indexer, src_path):
    """doc_refs rows whose SRC doc is the fs doc at `src_path` (source 'code')."""
    return indexer.db.execute(
        """SELECT r.* FROM doc_refs r JOIN docs d ON d.id = r.src_id
           WHERE d.source_id = 'code' AND d.path = ?""",
        (src_path,),
    ).fetchall()


def _doc_id(db, source_id, path):
    row = db.execute(
        "SELECT id FROM docs WHERE source_id = ? AND path = ?", (source_id, path)
    ).fetchone()
    return row["id"] if row else None


# --- AC1: parser extracts every form; ignores code -------------------------

PARSE_DOC = """# Title

See [[b]] then [[a#H]] then [[a|alias label]] then ![[emb]] here.

A markdown link [the text](../sub/b.md#frag) in a sentence.

An external [site](https://example.com) and a bare [anchor](#top) are not edges.

Inline `[[incode]]` must be ignored.

```
[[fenced]] also ignored
[skip](../x.md)
```
"""


def test_parser_extracts_all_forms_and_ignores_code():
    refs = {(r.target, r.anchor): r for r in parse_links(PARSE_DOC)}

    assert ("b", None) in refs and refs[("b", None)].kind == "links-to"

    assert ("a", "H") in refs  # anchor captured

    alias_ref = refs[("a", None)]
    assert alias_ref.alias == "alias label"  # alias captured

    assert refs[("emb", None)].kind == "embeds"  # ![[...]] is an embed

    md = refs[("../sub/b.md", "frag")]
    assert md.kind == "links-to"
    assert md.alias == "the text"
    assert md.context and len(md.context) <= 160
    assert "markdown link" in md.context  # surrounding sentence

    # Code (inline + fenced) and non-.md / external / in-page links are NOT edges.
    assert ("incode", None) not in refs
    assert ("fenced", None) not in refs
    assert ("../x.md", None) not in refs
    assert not any(t.startswith("http") or t == "" for (t, _a) in refs)


# --- AC2: resolve on index; deleting the target leaves a dangling ref -------


def test_resolved_ref_becomes_dangling_when_target_deleted(idx):
    indexer, root = idx
    (root / "a.md").write_text("# A\n\nlink to [[b]] here\n", encoding="utf-8")
    (root / "b.md").write_text("# B\n\nbody\n", encoding="utf-8")
    _reindex(indexer)

    rows = _refs_from(indexer, "a.md")
    assert len(rows) == 1
    b_id = _doc_id(indexer.db, "code", "b.md")
    assert rows[0]["dst_id"] == b_id  # resolved a -> b

    (root / "b.md").unlink()
    _reindex(indexer)

    rows = _refs_from(indexer, "a.md")
    assert len(rows) == 1, "ref kept, not deleted"
    assert rows[0]["dst_id"] is None, "ref is now dangling"
    assert rows[0]["dst_raw"] == "b"


# --- AC3: dangling re-binds on rename / when a future doc appears -----------


def test_dangling_rebinds_on_rename_and_future_doc(idx):
    indexer, root = idx
    (root / "b.md").write_text("# B\n\nbody\n", encoding="utf-8")
    (root / "a.md").write_text("# A\n\nsee [[c]] and [[future]]\n", encoding="utf-8")
    _reindex(indexer)

    rows = {r["dst_raw"]: r for r in _refs_from(indexer, "a.md")}
    assert rows["c"]["dst_id"] is None and rows["future"]["dst_id"] is None

    # Rename b.md -> c.md: c now exists, the [[c]] edge must bind on reindex.
    (root / "b.md").rename(root / "c.md")
    _reindex(indexer)
    c_id = _doc_id(indexer.db, "code", "c.md")
    rows = {r["dst_raw"]: r for r in _refs_from(indexer, "a.md")}
    assert rows["c"]["dst_id"] == c_id
    assert rows["future"]["dst_id"] is None  # still waiting

    # A future doc appears -> its dangling edge binds too.
    (root / "future.md").write_text("# Future\n\nhere now\n", encoding="utf-8")
    _reindex(indexer)
    future_id = _doc_id(indexer.db, "code", "future.md")
    rows = {r["dst_raw"]: r for r in _refs_from(indexer, "a.md")}
    assert rows["future"]["dst_id"] == future_id


# --- AC4: an owned doc's [[some/file]] resolves to the file-backed doc ------


def test_owned_doc_link_resolves_to_file_backed_doc(settings, tmp_path):
    store = SqliteStore(settings, embedder=BagEmbedder())
    # A file-backed doc living under an fs source, inserted directly (hermetic:
    # no indexer run needed to exercise owned -> file resolution).
    store.db.execute(
        """INSERT INTO docs (source_id, path, absolute_path, content_hash,
               size_bytes, tokens_est, mtime, first_indexed, last_indexed, title)
           VALUES ('code', 'some/file.md', '/x/some/file.md', 'h', 1, 1, 0, 0, 0, 'File')""",
    )
    store.db.commit()
    file_id = _doc_id(store.db, "code", "some/file.md")

    ext = store.put("# Owner note\n\nrefers to [[some/file]] for detail", kind="record")
    owner_id = store.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext,)).fetchone()["id"]

    rows = store.db.execute(
        "SELECT * FROM doc_refs WHERE src_id = ?", (owner_id,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["dst_raw"] == "some/file"
    assert rows[0]["dst_id"] == file_id


# --- AC5: delete_doc_cascade removes the deleted src's outgoing refs --------


def test_delete_cascade_removes_outgoing_refs(idx):
    indexer, root = idx
    (root / "a.md").write_text("# A\n\n[[b]]\n", encoding="utf-8")
    (root / "b.md").write_text("# B\n\nbody\n", encoding="utf-8")
    _reindex(indexer)
    assert len(_refs_from(indexer, "a.md")) == 1

    (root / "a.md").unlink()
    _reindex(indexer)

    # a's outgoing ref is gone; no orphan rows survive its deletion.
    assert len(_refs_from(indexer, "a.md")) == 0
    orphans = indexer.db.execute(
        "SELECT COUNT(*) n FROM doc_refs WHERE src_id NOT IN (SELECT id FROM docs)"
    ).fetchone()["n"]
    assert orphans == 0


# --- basename resolution: same-source (2a) before global-unique (2b) --------


def test_basename_prefers_same_source_then_global(settings, tmp_path):
    a = tmp_path / "repoA"
    b = tmp_path / "repoB"
    a.mkdir()
    b.mkdir()
    # Both sources have a design.md (basename 'design' is NOT globally unique).
    (a / "design.md").write_text("# A design\n", encoding="utf-8")
    (b / "design.md").write_text("# B design\n", encoding="utf-8")
    # 'onlyb' exists only in B.
    (b / "onlyb.md").write_text("# only in B\n", encoding="utf-8")
    (a / "notes.md").write_text("# Notes\n\nsee [[design]] and [[onlyb]]\n", encoding="utf-8")

    indexer = Indexer(settings, embedder=BagEmbedder())
    sources_mod.add_source(indexer.db, id="A", root=a)
    sources_mod.add_source(indexer.db, id="B", root=b)
    indexer.reindex(sources=indexer.settings.load_sources())

    a_design = _doc_id(indexer.db, "A", "design.md")
    b_onlyb = _doc_id(indexer.db, "B", "onlyb.md")
    rows = {
        r["dst_raw"]: r
        for r in indexer.db.execute(
            """SELECT r.* FROM doc_refs r JOIN docs d ON d.id = r.src_id
               WHERE d.source_id = 'A' AND d.path = 'notes.md'"""
        ).fetchall()
    }
    # 2a: same-source match wins over the ambiguous cross-source design.md.
    assert rows["design"]["dst_id"] == a_design
    # 2b: no 'onlyb' in A, globally unique in B -> binds across sources.
    assert rows["onlyb"]["dst_id"] == b_onlyb
