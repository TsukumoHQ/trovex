"""FsConnector (task 960a4b64): the filesystem walk behind the Connector protocol
(trovex/connectors/base.py). Runs the shared conformance suite every connector
must pass. Hermetic: BagEmbedder, no model download.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat

import numpy as np
import pytest
from connector_conformance import (
    check_failures_are_inline,
    check_fetch_returns_one_record,
    check_list_slim,
    check_poll_resumes_from_cursor,
    drain,
)

from trovex.config import Settings, Source
from trovex.connectors import build_connector
from trovex.connectors.base import Connector, Cursor, RecordFailure, SlimRef, SourceRecord
from trovex.connectors.fs import FsConnector
from trovex.indexer import Indexer

DIM = 384
BASE_NS = 1_700_000_000 * 10**9


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
def fs(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _write(root, "a.md", "# Alpha\n\nalpha body", BASE_NS + 1)
    _write(root, "sub/b.md", "# Bravo\n\nbravo body", BASE_NS + 2)
    _write(root, "c.md", "# Charlie\n\ncharlie body", BASE_NS + 3)
    settings = Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    idx = Indexer(settings, embedder=BagEmbedder())
    source = Source(id="code", label="repo", root=root.resolve())
    return FsConnector(source, idx), root


def test_fs_connector_satisfies_protocol_and_registry(fs):
    connector, _root = fs
    assert isinstance(connector, Connector)
    assert connector.kind == "fs"
    built = build_connector("fs", connector.source, connector.indexer)
    assert isinstance(built, FsConnector)
    with pytest.raises(KeyError):
        build_connector("no-such-kind", connector.source, connector.indexer)


def test_fs_conformance_list_slim(fs):
    connector, _root = fs
    refs = check_list_slim(connector)
    assert {r.external_id for r in refs} == {"a.md", "sub/b.md", "c.md"}
    by_id = {r.external_id: r for r in refs}
    assert by_id["sub/b.md"].parents == ["sub"]
    assert by_id["sub/b.md"].remote_version == str(BASE_NS + 2)


def test_fs_conformance_fetch_returns_one_record(fs):
    connector, _root = fs
    check_fetch_returns_one_record(connector)
    rec = connector.fetch(SlimRef("sub/b.md", str(BASE_NS + 2), [], ["sub"]))
    assert "bravo body" in rec.markdown and rec.title == "Bravo"
    assert rec.record_locator == {"path": "sub/b.md"}


def test_fs_conformance_poll_resumes_from_cursor(fs):
    connector, root = fs

    def add_record():
        _write(root, "d.md", "# Delta\n\ndelta body", BASE_NS + 10)
        return "d.md"

    check_poll_resumes_from_cursor(connector, add_record)


def test_fs_conformance_failures_are_inline(fs):
    connector, root = fs

    def break_record():
        p = root / "sub" / "b.md"
        p.chmod(0)
        return "sub/b.md"

    try:
        check_failures_are_inline(connector, break_record)
    finally:
        (root / "sub" / "b.md").chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_fs_poll_cursor_is_max_mtime_ns_and_skips_ignored_files(fs):
    connector, root = fs
    _write(root, "node_modules/x.md", "# ignored", BASE_NS + 99)
    items, cursor = drain(connector.poll(None))
    assert isinstance(cursor, Cursor)
    assert cursor.opaque == {"mtime_ns": BASE_NS + 3}
    assert all(isinstance(i, SourceRecord) for i in items)
    assert "node_modules/x.md" not in {i.external_id for i in items}
    assert not any(isinstance(i, RecordFailure) for i in items)
