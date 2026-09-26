"""`sources` table replaces sources.yaml (task 960a4b64, design 61a37a82 6.1):
schema, one-shot yaml import on first start, RESERVED_SOURCE_ID guard, and the
`trovex sources list|add|disable` CLI. Hermetic: BagEmbedder.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest
import yaml
from typer.testing import CliRunner

from trovex import sources as sources_mod
from trovex.cli import app
from trovex.config import RESERVED_SOURCE_ID, Settings
from trovex.indexer import Indexer

DIM = 384

SOURCE_COLS = {
    "id",
    "kind",
    "label",
    "config",
    "credential_ref",
    "policy",
    "poll_sec",
    "gc_sec",
    "deletion_safety_ratio",
    "meta",
    "enabled",
}
SOURCE_RUN_COLS = {
    "id",
    "source_id",
    "kind",
    "started",
    "ended",
    "cursor_json",
    "added",
    "updated",
    "removed",
    "ok",
    "failed",
    "failures_json",
    "removed_ids",
    "error",
    "scan_ms",
    "embed_ms",
    "write_ms",
}

runner = CliRunner()


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


def _settings(tmp_path, entries=None) -> Settings:
    cfg = tmp_path / "sources.yaml"
    if entries is not None:
        cfg.write_text(yaml.safe_dump({"sources": entries}))
    return Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=cfg,
    )


def _cols(db, table):
    return {r[1] for r in db.execute(f"PRAGMA table_info({table})")}


def test_sources_and_source_runs_tables_have_the_designed_columns(tmp_path):
    idx = Indexer(_settings(tmp_path), embedder=BagEmbedder())
    assert _cols(idx.db, "sources") == SOURCE_COLS
    assert _cols(idx.db, "source_runs") == SOURCE_RUN_COLS


def test_first_start_imports_sources_yaml_once(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    entries = [
        {"id": "notes", "label": "My notes", "root": str(a)},
        {"id": "code", "root": str(b)},
        {"id": RESERVED_SOURCE_ID, "root": str(a)},  # reserved: must be skipped
    ]
    settings = _settings(tmp_path, entries)
    idx = Indexer(settings, embedder=BagEmbedder())

    rows = {r["id"]: r for r in sources_mod.list_sources(idx.db)}
    assert set(rows) == {"notes", "code"}
    assert rows["notes"]["kind"] == "fs" and rows["notes"]["label"] == "My notes"
    assert rows["notes"]["enabled"] == 1 and rows["notes"]["policy"] == "upsert_delete"
    assert rows["notes"]["deletion_safety_ratio"] == pytest.approx(0.5)
    assert str(a.resolve()) in rows["notes"]["config"]

    # Second start is a no-op (not a duplicate insert, not a re-import), and once the
    # table is populated it wins over the yaml file.
    settings.sources_config_path.write_text(
        yaml.safe_dump({"sources": entries + [{"id": "extra", "root": str(a)}]})
    )
    idx2 = Indexer(settings, embedder=BagEmbedder())
    assert {r["id"] for r in sources_mod.list_sources(idx2.db)} == {"notes", "code"}
    assert {s.id for s in settings.load_sources()} == {"notes", "code"}


def test_load_sources_falls_back_to_yaml_while_table_is_empty(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    settings = _settings(tmp_path, [{"id": "notes", "root": str(a)}])
    # No Indexer built yet, so nothing was imported: the yaml path still serves.
    assert [s.id for s in settings.load_sources()] == ["notes"]


def test_add_source_rejects_reserved_and_duplicate_ids(tmp_path):
    idx = Indexer(_settings(tmp_path), embedder=BagEmbedder())
    root = tmp_path / "r"
    root.mkdir()
    with pytest.raises(ValueError, match="reserved"):
        sources_mod.add_source(idx.db, id=RESERVED_SOURCE_ID, root=root)
    sources_mod.add_source(idx.db, id="notes", root=root)
    with pytest.raises(ValueError, match="exists"):
        sources_mod.add_source(idx.db, id="notes", root=root)


def test_disabled_source_is_not_loaded(tmp_path):
    settings = _settings(tmp_path)
    idx = Indexer(settings, embedder=BagEmbedder())
    root = tmp_path / "r"
    root.mkdir()
    sources_mod.add_source(idx.db, id="notes", root=root)
    assert [s.id for s in settings.load_sources()] == ["notes"]
    assert sources_mod.disable_source(idx.db, "notes") is True
    assert sources_mod.disable_source(idx.db, "no-such") is False
    assert settings.load_sources() == []  # disabled rows exist, so no single-source fallback


def test_cli_sources_add_list_disable(tmp_path, monkeypatch):
    monkeypatch.setenv("TROVEX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TROVEX_SOURCES_CONFIG_PATH", str(tmp_path / "none.yaml"))
    root = tmp_path / "docs"
    root.mkdir()

    res = runner.invoke(app, ["sources", "add", "--id", "notes", "--root", str(root)])
    assert res.exit_code == 0, res.output

    res = runner.invoke(app, ["sources", "list"])
    assert res.exit_code == 0, res.output
    assert "notes" in res.output and "fs" in res.output and "enabled" in res.output

    res = runner.invoke(app, ["sources", "add", "--id", RESERVED_SOURCE_ID, "--root", str(root)])
    assert res.exit_code != 0 and "reserved" in res.output

    res = runner.invoke(app, ["sources", "disable", "notes"])
    assert res.exit_code == 0, res.output
    res = runner.invoke(app, ["sources", "list"])
    assert "disabled" in res.output

    res = runner.invoke(app, ["sources", "disable", "no-such"])
    assert res.exit_code != 0
