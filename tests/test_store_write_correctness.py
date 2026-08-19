"""store.put write-path correctness — the follow-ups to steal #2 + #5.

Three fixes:
- a title-only rewrite must RE-EMBED (embed_text fuses the title; the old
  content-hash-only skip left stale vectors);
- a write RESETS lifecycle to active (re-writing a stable ext_id — e.g. an
  Active-Memory capture — must resurrect an archived doc, not silently vanish);
- retrieval's widen-retry fires whenever a result comes back short, since the
  always-on lifecycle filter can squeeze an otherwise-unfiltered query.

Hermetic: deterministic BagEmbedder, no model download / network.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex.config import Settings
from trovex.search import Searcher
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


_DOC = "# Deploy\n\n## Reverse proxy\n\nterminate tls at nginx and forward to the local port\n"


def _chunk_ids(store, ext):
    did = store.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext,)).fetchone()["id"]
    return [
        r["id"]
        for r in store.db.execute(
            "SELECT id FROM chunks WHERE doc_id = ? ORDER BY chunk_index", (did,)
        )
    ]


def _lifecycle(store, ext):
    return store.db.execute("SELECT lifecycle FROM docs WHERE ext_id = ?", (ext,)).fetchone()[
        "lifecycle"
    ]


# --- title-only rewrite must re-embed --------------------------------------


def test_title_only_change_reembeds_chunks(store):
    ext = store.put(_DOC, kind="record", title="Alpha")
    before = _chunk_ids(store, ext)
    store.put(_DOC, ext_id=ext, kind="record", title="Beta")  # same body, new title
    after = _chunk_ids(store, ext)
    assert after != before  # re-embedded (embed_text fuses the title)
    assert (
        store.db.execute("SELECT title FROM docs WHERE ext_id = ?", (ext,)).fetchone()["title"]
        == "Beta"
    )


def test_identical_content_and_title_is_still_a_noop(store):
    ext = store.put(_DOC, kind="record", title="Alpha")
    before = _chunk_ids(store, ext)
    store.put(_DOC, ext_id=ext, kind="record", title="Alpha")  # truly identical
    assert _chunk_ids(store, ext) == before  # reused
    assert store.list_versions(ext) == []  # no snapshot


# --- a write resurrects an archived doc ------------------------------------


def test_writing_new_content_unarchives(store):
    ext = store.put(_DOC, kind="record")
    store.set_lifecycle(ext, "archived")
    assert store.search_chunks("reverse proxy tls") == []  # hidden
    store.put(_DOC + "\n## More\n\nextra section here\n", ext_id=ext, kind="record")
    assert _lifecycle(store, ext) == "active"
    assert store.search_chunks("reverse proxy tls")  # visible again


def test_identical_reput_also_unarchives(store):
    """Even a byte-identical rewrite is a 'this is live' signal — it must
    un-archive (the early-return path still resets lifecycle)."""
    ext = store.put(_DOC, kind="record")
    store.set_lifecycle(ext, "archived")
    store.put(_DOC, ext_id=ext, kind="record")  # identical body
    assert _lifecycle(store, ext) == "active"


# --- widen-retry not squeezed by an archived-heavy pool --------------------


def test_active_doc_found_despite_archived_neighbours(store, settings):
    # Regression for the widen-retry guard: the always-on lifecycle filter can
    # squeeze an *unfiltered* query out of the first-pass KNN pool, and the retry
    # must still fire (old guard `filtered and total>pool` never fired without a
    # kind/tags/source scope, so an archived-heavy pool starved the query).
    #
    # NON-VACUOUS by construction: every archived dup carries ALL four query
    # terms (reverse/proxy/tls/nginx), the one active doc carries only two
    # (reverse/proxy). Under BagEmbedder cosine, the active doc is therefore
    # STRICTLY farther from the query than every archived dup, so it is NOT in the
    # first-pass top-25 — the pre-filter pool is 100% archived, the lifecycle
    # filter empties it, and ONLY the widen-retry over the whole index recovers
    # the active doc. (Earlier revisions gave the active doc the same query-term
    # profile as the dups; its lighter noise gave it a *higher* cosine, so it sat
    # in the first-pass pool and the test passed even when the retry never ran.)
    #
    # hybrid=False isolates the dense widen-retry: BM25 is not an alternate
    # recovery route, so a regression in the retry guard fails this test outright.
    N = 30  # > pool (limit*5 = 25): first-pass top-25 is all-archived
    for i in range(N):
        e = store.put(
            f"# Proxy notes\n\n## Reverse proxy\n\nreverse proxy tls nginx entry {i}\n",
            kind="record",
        )
        store.set_lifecycle(e, "archived")
    # Two query terms only (reverse, proxy) — no tls/nginx — so it ranks below
    # every archived dup and is squeezed out of the first-pass pool.
    active = store.put(
        "# Live entry\n\n## Reverse proxy overview\n\nreverse proxy summary only\n",
        kind="record",
    )
    searcher = Searcher(settings, embedder=BagEmbedder())
    # Dense-only, unfiltered: the pre-filter pool (25) is entirely archived, so
    # the first pass returns empty and only the widen-retry surfaces the active doc.
    results = searcher.search("reverse proxy tls nginx", limit=5, hybrid=False)
    exts = {r.path for r in results}
    assert active in exts  # recovered by the widen-retry, not squeezed out
