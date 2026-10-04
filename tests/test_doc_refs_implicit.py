"""Implicit edges: unlinked mentions + semantic 'similar' (task 07b7cdc4,
trovex/links L3). Deterministic via a controlled unit-vector embedder.

The store's similarity is `1 - distance/2` where vec0's distance is cosine
distance (1 - cos), i.e. the stored similarity is (1 + cos)/2 — NOT true cosine
(the documented L3 caveat). With dup threshold 0.90 and band 0.15 the 'similar'
window is a stored score in [0.75, 0.90), i.e. cos in [0.50, 0.80).
Hermetic: no model download.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from trovex.config import Settings
from trovex.status import compute_status
from trovex.store import SqliteStore

DIM = 384


def _vec(*components: tuple[int, float]) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    for i, x in components:
        v[i] = x
    n = float(np.linalg.norm(v)) or 1.0
    return v / n


def _plane(cos: float, axis: int) -> np.ndarray:
    """Unit vector with dot `cos` against e0, its remainder on axis `axis`."""
    return _vec((0, cos), (axis, math.sqrt(max(0.0, 1.0 - cos * cos))))


# marker → embedding. DUP/BAND/FAR sit on SEPARATE axes so they are not mutual
# duplicates of each other (only their cosine against BASE is controlled).
_MARKERS = {
    "DOC_BASE": _vec((0, 1.0)),
    "DOC_DUP": _plane(0.85, 1),   # (1+0.85)/2 = 0.925 ≥ 0.90 → duplicate
    "DOC_BAND": _plane(0.65, 2),  # (1+0.65)/2 = 0.825 ∈ [0.75,0.90) → similar
    "DOC_FAR": _plane(0.30, 3),   # (1+0.30)/2 = 0.650 < 0.75 → nothing
    "DOC_M1": _vec((5, 1.0)),
    "DOC_M2": _vec((6, 1.0)),
    "DOC_M3": _vec((7, 1.0)),
}


class VecEmbedder:
    name = "vec"
    dim = DIM

    def embed(self, texts):
        for t in texts:
            hit = next((v for m, v in _MARKERS.items() if m in t), None)
            yield hit.copy() if hit is not None else _vec((4, 1.0))


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


@pytest.fixture
def store(settings):
    return SqliteStore(settings, embedder=VecEmbedder())


def _id(store, ext):
    return store.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext,)).fetchone()["id"]


def _refs(store, src_id, kind):
    return store.db.execute(
        "SELECT dst_id, dst_raw, context FROM doc_refs WHERE src_id = ? AND kind = ?",
        (src_id, kind),
    ).fetchall()


# --- AC1: unlinked mention → mentions edge; explicit link → none ------------


def test_mention_edge_unless_explicitly_linked(store, settings):
    target = store.put("# Payments\n\nDOC_M1 the payments design", kind="reference", title="Payments")
    plain = store.put("# Plain\n\nWe follow the Payments approach. DOC_M2", kind="reference", title="Plain")
    linked = store.put("# Linked\n\nSee [[Payments]] for detail. DOC_M3", kind="reference", title="Linked")

    t_id = _id(store, target)
    compute_status(store.db, settings, touched_doc_ids=[_id(store, plain), _id(store, linked)])

    assert [r["dst_id"] for r in _refs(store, _id(store, plain), "mentions")] == [t_id]
    assert all(r["dst_id"] != t_id for r in _refs(store, _id(store, linked), "mentions"))


# --- AC2: similar within band (scored); below band none; dups excluded ------


def test_similar_band_scored_and_excludes_dups(store, settings):
    dup = store.put("# Dup\n\nDOC_DUP near-identical", kind="reference", title="Dup")  # older
    band = store.put("# Band\n\nDOC_BAND related but distinct", kind="reference", title="Band")
    far = store.put("# Far\n\nDOC_FAR unrelated", kind="reference", title="Far")
    base = store.put("# Base\n\nDOC_BASE the anchor", kind="reference", title="Base")  # newest

    base_id = _id(store, base)
    compute_status(store.db, settings, touched_doc_ids=[base_id])

    sims = {r["dst_id"]: r["context"] for r in _refs(store, base_id, "similar")}
    assert _id(store, band) in sims
    assert float(sims[_id(store, band)]) == pytest.approx(0.825, abs=0.02)
    assert _id(store, far) not in sims   # below band
    assert _id(store, dup) not in sims   # ≥ dup threshold → duplicate, excluded


# --- AC3: incremental recompute touches only the driver's implicit edges ----


def test_incremental_only_recomputes_driver(store, settings):
    store.put("# Band\n\nDOC_BAND related", kind="reference", title="Band")
    base = store.put("# Base\n\nDOC_BASE anchor", kind="reference", title="Base")
    base_id = _id(store, base)
    compute_status(store.db, settings, touched_doc_ids=[base_id])
    before = {r["dst_id"] for r in _refs(store, base_id, "similar")}
    assert before  # base has a similar edge

    other = store.put("# Other\n\nnothing related", kind="reference", title="Other")
    compute_status(store.db, settings, touched_doc_ids=[_id(store, other)])

    after = {r["dst_id"] for r in _refs(store, base_id, "similar")}
    assert after == before  # untouched driver's edges unchanged
