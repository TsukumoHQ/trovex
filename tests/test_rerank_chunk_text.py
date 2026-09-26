"""Pinned regression for task 4478fe53: the reranker's per-candidate text must
come from the MATCHED chunk (heading breadcrumb + body), not the doc's first
chunk — which for a record with an unheaded preamble block (frontmatter-shaped
metadata: owner/kind/status lines with no heading) is metadata that never
overlaps the query. Hermetic: BagEmbedder, no model download, real SqliteStore
+ Searcher against a tmp_path db."""

from __future__ import annotations

import hashlib
import re

import numpy as np

from trovex.config import Settings
from trovex.mcp_app import _build_chunk_text_fn
from trovex.search import Searcher
from trovex.store import TROVEX_SOURCE_ID, SqliteStore


class BagEmbedder:
    name = "bag"
    dim = 384

    def embed(self, texts):
        for t in texts:
            v = np.zeros(self.dim, dtype=np.float32)
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                idx = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                v[idx % self.dim] += 1.0
            norm = float(np.linalg.norm(v)) or 1.0
            yield v / norm


def _settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


def test_chunk_text_fn_uses_matched_section_not_file_head(tmp_path):
    """The doc's first 400 chars (an unheaded preamble block, i.e. a
    frontmatter-shaped metadata header) must never leak into the cross-encoder
    text when a LATER heading section is the actual chunk-level match."""
    settings = _settings(tmp_path)
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)
    doc_body = (
        "owner: alice\nkind: decision\nstatus: final\n\n"
        "# Deploy Playbook\n\n"
        "kubernetes rollback runbook for ERR_ROLL_9001 during canary rollout\n"
    )
    ext_id = store.put(doc_body, tags=["topic/deploy"])

    searcher = Searcher(settings, embedder=embedder)
    candidates = searcher.search("ERR_ROLL_9001", limit=5, source_ids=[TROVEX_SOURCE_ID])
    assert candidates and candidates[0].path == ext_id

    text_fn = _build_chunk_text_fn(store, "ERR_ROLL_9001", candidates, source=TROVEX_SOURCE_ID)
    text = text_fn(candidates[0])

    assert "ERR_ROLL_9001" in text  # the matched section, fed to the cross-encoder
    assert "owner: alice" not in text  # never the unrelated preamble/first chunk
    assert "Deploy Playbook" in text  # heading breadcrumb present


def test_chunk_text_fn_falls_back_to_first_chunk_when_no_chunk_hit(tmp_path):
    """A candidate with no chunk-level hit for THIS query (simulated here via a
    source filter that excludes every one of its chunks from search_chunks)
    still gets text — the doc's first chunk, DB-backed, same as pre-4478fe53
    fallback behaviour — instead of raising or returning empty."""
    settings = _settings(tmp_path)
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)
    ext_id = store.put(
        "# Billing\n\nstripe webhook retries need an idempotency_key header",
        tags=["topic/billing"],
    )

    class _Cand:
        path = ext_id
        title = "Billing"

    cand = _Cand()
    # A source that owns none of this doc's chunks: search_chunks post-filters
    # every hit out by source_id, so the candidate falls to the fallback SQL
    # (which is NOT source-filtered) instead of a chunk-level match.
    text_fn = _build_chunk_text_fn(store, "idempotency_key", [cand], source="no-such-source")
    text = text_fn(cand)
    assert "Billing" in text
    assert "idempotency_key" in text or "stripe webhook" in text
