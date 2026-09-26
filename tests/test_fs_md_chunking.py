"""Opt-in chunk-level indexing for fs markdown docs (task 52385ebc): a source's
`chunk_markdown` flag, default off, so passage/card/section + the provenance link
work on fs .md docs like owned docs; enabling is guarded by the vec0 ceiling.
Hermetic: counting BagEmbedder, no model download.
"""

from __future__ import annotations

import hashlib
import json
import re

import numpy as np
import pytest
from typer.testing import CliRunner

from trovex import fs_chunking
from trovex import sources as sources_mod
from trovex.cli import app
from trovex.config import Settings
from trovex.indexer import Indexer

DIM = 384
runner = CliRunner()

DOC = """# Guide

intro paragraph about the guide

## Install

install steps go here, run the installer

## Usage

usage notes go here, call the tool

## Limits

limits are documented here, know them
"""


class CountingEmbedder:
    name = "bag"
    dim = DIM

    def __init__(self) -> None:
        self.embedded: list[str] = []

    def embed(self, texts):
        texts = list(texts)
        self.embedded.extend(texts)
        for t in texts:
            v = np.zeros(DIM, dtype=np.float32)
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                idx = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                v[idx % DIM] += 1.0
            norm = float(np.linalg.norm(v)) or 1.0
            yield v / norm


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "guide.md").write_text(DOC, encoding="utf-8")
    (root / "other.md").write_text("# Other\n\n## A\n\nalpha text\n\n## B\n\nbeta text\n", encoding="utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    emb = CountingEmbedder()
    idx = Indexer(settings, embedder=emb)
    sources_mod.add_source(idx.db, id="code", root=root)
    return idx, emb, root


def _chunks(idx, path="guide.md"):
    return idx.db.execute(
        """SELECT c.* FROM chunks c JOIN docs d ON d.id = c.doc_id
           WHERE d.source_id = 'code' AND d.path = ? ORDER BY c.chunk_index""",
        (path,),
    ).fetchall()


def _reindex(idx):
    return idx.reindex(sources=idx.settings.load_sources())


def _flag(idx) -> bool:
    return bool(json.loads(sources_mod.get_source(idx.db, "code")["config"]).get("chunk_markdown"))


def test_flag_defaults_off_and_md_docs_get_zero_chunks(env):
    idx, _emb, _root = env
    assert idx.settings.load_sources()[0].chunk_markdown is False
    _reindex(idx)
    assert idx.db.execute("SELECT COUNT(*) c FROM docs WHERE source_id='code'").fetchone()["c"] == 2
    assert idx.db.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"] == 0


def test_enable_backfills_existing_docs_with_anchor_and_link(env):
    idx, _emb, root = env
    _reindex(idx)

    res = fs_chunking.enable_chunk_markdown(idx, "code")

    assert res["enabled"] is True and res["chunks"] >= 4
    assert _flag(idx) is True and idx.settings.load_sources()[0].chunk_markdown is True
    rows = _chunks(idx)
    assert len(rows) >= 4
    for r in rows:
        assert r["anchor"], "every chunk carries its anchor"
        assert r["link"].startswith("file://") and r["link"].endswith("#" + r["anchor"])
        assert str(root) in r["link"]
    n_vec = idx.db.execute("SELECT COUNT(*) c FROM vec_chunks WHERE source_id='code'").fetchone()["c"]
    assert n_vec == idx.db.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]


def test_flag_on_chunks_a_newly_indexed_md_doc(env):
    idx, _emb, root = env
    fs_chunking.enable_chunk_markdown(idx, "code")
    (root / "new.md").write_text("# New\n\n## One\n\nfirst\n\n## Two\n\nsecond\n", encoding="utf-8")
    _reindex(idx)
    assert len(_chunks(idx, "new.md")) >= 2


def test_editing_one_section_re_embeds_only_that_chunk(env):
    idx, emb, root = env
    _reindex(idx)
    fs_chunking.enable_chunk_markdown(idx, "code")
    before = {r["content_hash"]: r["id"] for r in _chunks(idx)}
    assert len(before) >= 4

    emb.embedded.clear()
    (root / "guide.md").write_text(DOC.replace("call the tool", "call the tool twice"), encoding="utf-8")
    _reindex(idx)

    after = {r["content_hash"]: r["id"] for r in _chunks(idx)}
    kept = set(before) & set(after)
    assert len(after) - len(kept) == 1, "exactly one chunk is new"
    assert all(before[h] == after[h] for h in kept), "unchanged sections keep their rows"
    # one doc-level embed + one chunk embed; an all-sections re-embed would be 1 + len(after)
    assert len(emb.embedded) == 2
    assert any("twice" in t for t in emb.embedded)


def test_enable_refuses_past_the_vec0_ceiling_and_journals_why(env, monkeypatch):
    idx, _emb, _root = env
    _reindex(idx)
    monkeypatch.setattr(fs_chunking, "VEC0_K_CEILING", 3)

    res = fs_chunking.enable_chunk_markdown(idx, "code")

    assert res["enabled"] is False and "ceiling" in res["reason"]
    assert _flag(idx) is False
    assert idx.db.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"] == 0
    run = idx.db.execute("SELECT * FROM source_runs WHERE source_id='code' ORDER BY id DESC").fetchone()
    assert run["kind"] == "guard" and "ceiling" in run["error"]


def test_projection_reports_chunk_and_token_cost_without_writing(env):
    idx, _emb, _root = env
    _reindex(idx)
    proj = fs_chunking.project_markdown_chunks(idx, "code")
    assert proj["docs"] == 2 and proj["new_chunks"] >= 4 and proj["embed_tokens"] > 0
    assert proj["current_chunks"] == 0 and proj["ceiling"] == fs_chunking.VEC0_K_CEILING
    assert idx.db.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"] == 0
    assert _flag(idx) is False


def test_disable_purges_the_sources_md_chunks_and_stops_chunking(env):
    idx, _emb, root = env
    _reindex(idx)
    fs_chunking.enable_chunk_markdown(idx, "code")
    assert idx.db.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"] > 0

    fs_chunking.disable_chunk_markdown(idx, "code")

    assert _flag(idx) is False
    assert idx.db.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"] == 0
    assert idx.db.execute("SELECT COUNT(*) c FROM vec_chunks WHERE source_id='code'").fetchone()["c"] == 0
    (root / "guide.md").write_text(DOC + "\n## Extra\n\nmore\n", encoding="utf-8")
    _reindex(idx)
    assert idx.db.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"] == 0


def test_cli_chunk_markdown_dry_run_then_on_off(env, tmp_path, monkeypatch):
    idx, _emb, _root = env
    _reindex(idx)
    idx.db.close()
    monkeypatch.setenv("TROVEX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TROVEX_SOURCES_CONFIG_PATH", str(tmp_path / "none.yaml"))
    monkeypatch.setattr("trovex.indexer.embedder_from_settings", lambda s: CountingEmbedder())

    res = runner.invoke(app, ["sources", "chunk-markdown", "code", "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "projected" in res.output and "chunks" in res.output

    res = runner.invoke(app, ["sources", "chunk-markdown", "code"])
    assert res.exit_code == 0, res.output
    assert "enabled" in res.output.lower()

    res = runner.invoke(app, ["sources", "chunk-markdown", "code", "--off"])
    assert res.exit_code == 0, res.output
    assert "disabled" in res.output.lower()

    res = runner.invoke(app, ["sources", "chunk-markdown", "no-such"])
    assert res.exit_code != 0
