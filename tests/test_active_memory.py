"""Active-Memory invariants (RFC 330e7d43) — the subsystem-specific guarantees that
a generic store test wouldn't catch. Complements tests/test_store.py (roundtrip,
upsert, case-insensitive owner scope) by pinning the *load-bearing* ones:

  • scope-first, score-second — the knn pool WIDENS under a metadata filter, so a
    tightly-scoped query (owner/<agent> + kind=record) isn't starved out of the pool
    by a store dominated by other agents' docs;
  • the boot floor drops below-threshold recall (zero-cost for an absent agent);
  • ranking within a scope is by score;
  • the write-time near-duplicate guard blocks a near-copy CREATE of a canonical doc
    but SKIPS records (owner current-state is an upsert, not a dup pile).

Hermetic: a deterministic bag-of-words embedder (no OpenAI / no model download).
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex.boot import boot_pointers
from trovex.config import Settings
from trovex.search import Searcher
from trovex.store import SqliteStore

DIM = 384


class BagEmbedder:
    """Stable hashing bag-of-words embedder — shared tokens → high cosine."""

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
        embed_model="BAAI/bge-small-en-v1.5",  # dim 384, matches BagEmbedder
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


@pytest.fixture
def store(settings):
    return SqliteStore(settings, embedder=BagEmbedder())


def test_scope_widens_pool_so_tight_scope_is_not_starved(settings, store):
    """THE load-bearing invariant. The knn `k` is `max(limit*5, 50)` when a filter is
    on. Flood the store with 35 other-owner records that are MORE similar to the query
    than the target (each == the query string), so the target sits at rank ~36 by
    distance. A naive pool of `limit*5` (=25) would exclude it and the tag filter would
    return NOTHING; the widened pool (50) keeps it, so the scoped query still recalls
    its own record. This is exactly the cross-owner starvation the widening prevents."""
    query = "jwt token signature validation auth incident"
    for i in range(35):
        store.put(f"# noise {i}\n\n{query}", kind="record", tags=["owner/noise"])
    target = store.put(
        f"# target state\n\n{query} uniquetargettoken", kind="record", tags=["owner/target"]
    )

    searcher = Searcher(settings, embedder=BagEmbedder())
    scoped = searcher.search(query, limit=5, source_ids=["trovex"], kind="record", tags=["owner/target"])

    assert [r.path for r in scoped] == [target], "widened pool must keep the scoped record in range"


def test_boot_floor_drops_below_threshold(settings, store):
    """Boot gates on a score floor AFTER scope. A scoped record that scores below the
    floor yields an empty (zero-cost) pack; the same record clears a floor of 0."""
    store.put("# target state\n\nzzz unrelated tokens only", kind="record", tags=["owner/target"])
    searcher = Searcher(settings, embedder=BagEmbedder())

    # Query shares nothing with the record → low score → dropped by a normal floor.
    high = boot_pointers(searcher, "target", q="completely different subject matter", floor=0.62)
    assert high["pointers"] == []
    assert high["tokens_est"] == 0

    # floor=0 keeps it → proves the emptiness above was the FLOOR, not a scope miss.
    low = boot_pointers(searcher, "target", q="completely different subject matter", floor=0.0)
    assert any("target" in p["title"] for p in low["pointers"])


def test_scope_ranks_by_score_within_filter(settings, store):
    """Score-second: within a single owner scope, the more query-similar record ranks
    first. Scope narrows the candidate set; score orders what survives."""
    query = "kubernetes pod rollout crash loop deploy rollback"
    near = store.put(f"# near\n\n{query}", kind="record", tags=["owner/dev"])
    far = store.put(
        "# far\n\nstripe invoice webhook billing reconciliation",
        kind="record",
        tags=["owner/dev"],
    )

    searcher = Searcher(settings, embedder=BagEmbedder())
    res = searcher.search(query, limit=5, source_ids=["trovex"], kind="record", tags=["owner/dev"])

    assert res[0].path == near
    assert {r.path for r in res} == {near, far}  # both in scope
    assert res[0].score >= res[-1].score  # sorted by score desc


def test_near_dup_guard_blocks_canonical_create_but_skips_records(settings, store):
    """The write-time dedup guard (store.check_duplicate) backs trovex_write's
    block-and-point on CREATE. It fires for a near-copy of a CANONICAL non-record doc,
    is silent for a genuinely distinct doc, and is SKIPPED for records — because an
    owner's current-state is a deterministic upsert, not a near-duplicate to block."""
    canonical = store.put(
        "# Auth runbook\n\njwt token signature validation rotate keys on incident",
        kind="reference",
    )

    # A near-copy of the canonical reference → guard points at the original.
    hit = store.check_duplicate("jwt token signature validation rotate keys on incident", title="Auth")
    assert hit is not None
    assert hit["ext_id"] == canonical
    assert hit["similarity"] >= store.settings.dup_cosine_threshold

    # A clearly different doc → no block.
    assert store.check_duplicate("stripe invoice webhook billing reconciliation flow") is None

    # A record neighbour must NOT block (records are upsert-by-owner, not dup bloat).
    store.put("# cmo state\n\nmoonshot launch metrics current state", kind="record", tags=["owner/cmo"])
    assert store.check_duplicate("moonshot launch metrics current state") is None
