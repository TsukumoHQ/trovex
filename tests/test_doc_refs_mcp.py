"""Agents see the doc_refs graph through MCP (task b9687dfb, trovex/links L2):
trovex_read(links=True) link block, trovex(q)/format_minimal count hints, and
the trovex://graph/{doc} resource (file-backed docs included). Hermetic:
bag-of-words embedder, no model download.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex import mcp_app
from trovex import sources as sources_mod
from trovex import state as state_mod
from trovex.config import Settings
from trovex.indexer import Indexer
from trovex.search import Searcher, SearchResult
from trovex.state import AppState
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
def env(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    emb = BagEmbedder()
    store = SqliteStore(settings, embedder=emb)
    indexer = Indexer(settings, embedder=emb)
    searcher = Searcher(settings, embedder=emb)
    state_mod._state = AppState(
        settings=settings, embedder=emb, searcher=searcher, indexer=indexer, store=store
    )
    try:
        yield settings, store, indexer, searcher, tmp_path
    finally:
        state_mod.reset_state()


def _result_for(store, ext_id):
    r = store.db.execute(
        """SELECT source_id, path, title, tokens_est, size_bytes, status, absolute_path
           FROM docs WHERE ext_id = ?""",
        (ext_id,),
    ).fetchone()
    return SearchResult(
        path=r["path"],
        title=r["title"],
        distance=0.0,
        score=1.0,
        age_days=0.0,
        status=r["status"],
        size_bytes=r["size_bytes"],
        tokens_est=r["tokens_est"],
        absolute_path=r["absolute_path"] or "",
        source_id=r["source_id"],
    )


# --- AC1: trovex_read(links=True) prints out + dangling + backlinks ---------


def test_read_links_block_lists_out_in_and_dangling(env):
    _settings, store, _idx, _searcher, _tmp = env
    store.put("# Alpha\n\nalpha body", kind="record", title="Alpha")
    store.put("# Beta\n\nbeta body", kind="record", title="Beta")
    x = store.put(
        "# Exes\n\nIt references [[Alpha]] and also [[Beta]] plus a missing [[Ghost]].",
        kind="record",
        title="Exes",
    )
    store.put("# Why\n\nThis note points to [[Exes]] for the detail.", kind="record", title="Why")

    out = mcp_app.trovex_read(doc_id=x, links=True)
    assert out.count("→ out:") == 2  # Alpha + Beta resolved
    assert "∅ Ghost" in out  # dangling kept
    assert out.count("← in:") == 1  # backlink from Why
    assert "references" in out  # outgoing edge carries its citing sentence
    assert "points to" in out  # backlink carries its citing sentence

    # Without links=True the body is unchanged (no graph block).
    assert "→ out:" not in mcp_app.trovex_read(doc_id=x)


def test_read_links_block_caps_each_side_at_ten(env):
    _settings, store, _idx, _searcher, _tmp = env
    body = "# Zed\n\n" + " ".join(f"[[ghost{i}]]" for i in range(12))
    z = store.put(body, kind="record", title="Zed")
    out = mcp_app.trovex_read(doc_id=z, links=True)
    assert out.count("∅ ghost") == 10
    assert "+2 more out" in out


# --- AC2: trovex(q)/format_minimal shows counts only for linked docs --------


def test_minimal_counts_only_for_linked_docs(env):
    _settings, store, _idx, searcher, _tmp = env
    store.put("# Alpha\n\nalpha body", kind="record", title="Alpha")
    x = store.put("# Exes\n\nlinks to [[Alpha]]", kind="record", title="Exes")
    u = store.put("# Unlinked\n\nnothing points here and it points nowhere", kind="record", title="Unlinked")

    linked_line = searcher.format_minimal([_result_for(store, x)])
    unlinked_line = searcher.format_minimal([_result_for(store, u)])

    assert "⇄" in linked_line  # X has an outgoing edge
    assert "⇄" not in unlinked_line  # U has none → line byte-identical to before


# --- AC3: trovex://graph/{doc} 1-hop neighbours for a file-backed doc -------


def test_graph_resource_for_file_backed_doc(env):
    _settings, _store, indexer, _searcher, tmp = env
    root = tmp / "repo"
    root.mkdir()
    (root / "a.md").write_text("# A\n\nIt links to [[b]] in this sentence.\n", encoding="utf-8")
    (root / "b.md").write_text("# B\n\nbody\n", encoding="utf-8")
    sources_mod.add_source(indexer.db, id="code", root=root)
    indexer.reindex(sources=indexer.settings.load_sources())

    out = mcp_app.doc_graph("code:a.md")
    assert "→ out:" in out and "b.md" in out
    # The reverse doc sees the backlink.
    assert "← in:" in mcp_app.doc_graph("code:b.md")
