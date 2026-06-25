"""capture_state — the write half of Active Memory (RFC 330e7d43, step 3).

The free-summary path (no LLM): an agent's current-state record is upserted under
a STABLE id (owner-<agent>-current-state), so repeated captures overwrite the one
canonical record instead of piling duplicates. Hermetic — no OpenAI key, no model
download (BagEmbedder), the transcript/distil path is exercised elsewhere.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex.capture import capture_state
from trovex.config import Settings
from trovex.store import SqliteStore

DIM = 384

SUMMARY = "Shipped the boot fix and the route tests; next is the lint sweep, pending cmo."


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
def store(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    return SqliteStore(settings, embedder=BagEmbedder())


def test_capture_free_summary_writes_canonical_record(store):
    out = capture_state(store, "alpha", SUMMARY)
    assert out["captured"] is True
    assert out["doc_id"] == "owner-alpha-current-state"
    assert out["tokens"] > 0

    doc = store.get("owner-alpha-current-state")
    assert doc is not None
    assert doc.kind == "record"
    assert SUMMARY in doc.content
    # Owner tag + the lane tags, owner lower-cased for /api/boot scope.
    assert "owner/alpha" in doc.tags
    assert "type/current-state" in doc.tags
    assert "capture/postcompact" in doc.tags


def test_capture_upsert_is_idempotent(store):
    """Repeat capture overwrites the same record — one canonical doc, no dup pile."""
    capture_state(store, "alpha", "First state: investigating the boot bug.")
    capture_state(store, "alpha", "Second state: boot bug fixed and merged.")

    assert store.count_docs(tag="owner/alpha") == 1
    doc = store.get("owner-alpha-current-state")
    assert "Second state" in doc.content
    assert "First state" not in doc.content


def test_capture_rejects_thin_summary(store):
    """A sub-threshold summary captures nothing — no empty record is written."""
    out = capture_state(store, "alpha", "too short")
    assert out["captured"] is False
    assert out["reason"] == "no durable signal"
    assert store.get("owner-alpha-current-state") is None


def test_capture_no_signal_at_all(store):
    """No summary and no transcript → nothing captured (the free path needs text)."""
    out = capture_state(store, "alpha", "")
    assert out["captured"] is False
    assert store.count_docs(tag="owner/alpha") == 0


def test_capture_lowercases_mixed_case_owner(store):
    """A mixed-case agent (COO) is filed under owner/coo so /api/boot recalls it —
    the same normalisation as the boot-scope fix, applied on the write side."""
    out = capture_state(store, "COO", SUMMARY)
    assert out["doc_id"] == "owner-COO-current-state"  # id keeps case (no orphaning)

    doc = store.get("owner-COO-current-state")
    assert "owner/coo" in doc.tags
    assert "owner/COO" not in doc.tags
    # Scope query uses the lower-cased tag and finds exactly the one record.
    assert store.count_docs(tag="owner/coo", kind="record") == 1
