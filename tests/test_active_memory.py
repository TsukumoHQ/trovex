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

from trovex.boot import BOOT_QUERY, boot_pointers
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
    block-and-point on CREATE. It fires for a near-copy of a CANONICAL non-record doc
    OF THE SAME KIND, is silent for a genuinely distinct doc, and is SKIPPED for
    ephemeral kinds — because an owner's current-state is a deterministic upsert,
    not a near-duplicate to block. The caller passes the incoming doc's kind so the
    guard compares like-with-like."""
    canonical = store.put(
        "# Auth runbook\n\njwt token signature validation rotate keys on incident",
        kind="reference",
    )

    # A near-copy of the canonical reference, SAME kind → guard points at the original.
    hit = store.check_duplicate(
        "jwt token signature validation rotate keys on incident", title="Auth", kind="reference"
    )
    assert hit is not None
    assert hit["ext_id"] == canonical
    assert hit["similarity"] >= store.settings.dup_cosine_threshold

    # A clearly different doc (same kind) → no block.
    assert (
        store.check_duplicate("stripe invoice webhook billing reconciliation flow", kind="reference")
        is None
    )

    # An ephemeral-kind driver must NOT block (records are upsert-by-owner, not bloat).
    store.put("# cmo state\n\nmoonshot launch metrics current state", kind="record", tags=["owner/cmo"])
    assert store.check_duplicate("moonshot launch metrics current state", kind="record") is None


def test_dedup_is_namespaced_by_kind_no_cross_kind_false_positive(settings, store):
    """Regression (aa08ffaa): a governance audit was blocked as ~92% similar to a
    stale checkpoint. Dedup must compare WITHIN a (source_id, kind) class, so a
    near-identical body in a DIFFERENT kind never blocks — while a genuine
    same-kind near-copy still does."""
    topic = "quarterly access review rotate keys audit findings remediation"
    # An ephemeral checkpoint on the same topic — must never be a dedup neighbour.
    store.put(f"# Checkpoint\n\n{topic}", kind="checkpoint")

    # A governance doc with a near-identical body but a DIFFERENT kind → NOT blocked
    # (cross-kind), even though its vector is ~identical to the checkpoint's.
    assert store.check_duplicate(f"# Audit\n\n{topic}", title="Audit", kind="governance") is None

    # A genuine same-kind near-copy of an existing canonical governance doc → BLOCKED.
    gov = store.put(f"# Audit\n\n{topic}", kind="governance")
    hit = store.check_duplicate(f"# Audit copy\n\n{topic}", title="Audit", kind="governance")
    assert hit is not None and hit["ext_id"] == gov

    # And the auto-flagger is namespaced too: the checkpoint was never demoted to a
    # duplicate of the governance doc (a cross-kind false flag would HIDE it).
    cp_status = store.db.execute(
        "SELECT status FROM docs WHERE kind = 'checkpoint'"
    ).fetchone()["status"]
    assert cp_status != "duplicate"


def test_batch_detect_duplicates_is_namespaced_by_kind(settings, store):
    """Regression (aa08ffaa review r1): the BATCH duplicate pass (compute_status →
    _detect_duplicates, run by every reindex / fs-watch) must be namespaced too —
    otherwise a reindex silently demotes an owned canonical governance doc to a
    duplicate of an unrelated ephemeral checkpoint, HIDING it from retrieval."""
    from trovex.status import compute_status

    topic = "quarterly access review rotate keys audit findings remediation"
    gov = store.put(f"# Audit\n\n{topic}", kind="governance")
    store.put(f"# Checkpoint\n\n{topic}", kind="checkpoint")  # near-identical, different kind

    compute_status(store.db, store.settings)  # the reindex/fs-watch path

    # The governance canonical is NOT demoted against the cross-kind checkpoint.
    assert store.db.execute("SELECT status FROM docs WHERE ext_id = ?", (gov,)).fetchone()[
        "status"
    ] == "canonical"
    # The ephemeral checkpoint is never a dedup driver either.
    assert store.db.execute(
        "SELECT status FROM docs WHERE kind = 'checkpoint'"
    ).fetchone()["status"] != "duplicate"

    # But a genuine SAME-kind near-copy still gets collapsed (write-path + batch
    # agree): one of the pair ends up 'duplicate', not both left canonical. DISTINCT
    # titles → distinct canonical_topic (no SSOT collision), but near-identical
    # bodies → high cosine, so the batch still pairs them.
    body = "deploy rollback runbook incident response mitigation steps canonical procedure notes"
    a = store.put(f"# Deploy rollback runbook alpha\n\n{body}", kind="reference")
    b = store.put(f"# Deploy rollback runbook beta\n\n{body}", kind="reference")
    compute_status(store.db, store.settings)
    statuses = sorted(
        row["status"]
        for row in store.db.execute(
            "SELECT status FROM docs WHERE ext_id IN (?, ?)", (a, b)
        )
    )
    assert statuses == ["canonical", "duplicate"]  # one of the pair collapsed


# --- OUTAGE regression: sqlite-vec 4096 KNN ceiling ------------------------


def _bulk_seed_docs(store, n: int) -> None:
    """Insert `n` unscoped docs straight into docs+vec_docs in one transaction.
    Fast path: 4000+ store.put() calls (embed+chunk+fts+commit each) would take
    far too long for a gate test, and here we only need the vec_docs row COUNT to
    cross the ceiling — the bodies are irrelevant."""
    import sqlite_vec

    emb = next(iter(store.embedder.embed(["reverse proxy tls nginx seed"]))).tolist()
    blob = sqlite_vec.serialize_float32(emb)
    now = 1_600_000_000.0
    rows = [
        # source_id='code' (NOT 'trovex') + no kind → never matches the owner boot
        # scope, so the boot query comes back short and hits the widen-retry.
        ("code", f"seed/{i}.md", f"/seed/{i}.md", f"h{i}", 10, 3, now, now, now, f"seed {i}")
        for i in range(n)
    ]
    store.db.executemany(
        """INSERT INTO docs
             (source_id, path, absolute_path, content_hash, size_bytes,
              tokens_est, mtime, first_indexed, last_indexed, title)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    ids = [r["id"] for r in store.db.execute("SELECT id FROM docs")]
    store.db.executemany(
        "INSERT INTO vec_docs(rowid, embedding) VALUES (?, ?)",
        [(i, blob) for i in ids],
    )
    store.db.commit()


def test_knn_ceiling_boot_and_search_survive_over_4096_docs(settings, store):
    """Regression for the fleet OUTAGE: once the corpus crossed sqlite-vec's 4096
    KNN ceiling, the widen-retry issued a k>4096 MATCH that raised
    OperationalError, and /api/boot (Active-Memory) 500'd for every agent.

    Non-vacuous by construction: we first PROVE the corpus genuinely exceeds the
    ceiling (a raw k=count MATCH still raises), then assert the clamped paths —
    boot_pointers and Searcher.search — return normally instead of throwing."""
    import sqlite3

    import sqlite_vec

    N = 4100  # > 4096: the exact condition that took the fleet down
    _bulk_seed_docs(store, N)
    count = store.db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
    assert count == N

    # Prove the ceiling is real: an un-clamped k = count MATCH still throws, so a
    # regression that drops the clamp fails this test rather than silently passing.
    qblob = sqlite_vec.serialize_float32(
        next(iter(store.embedder.embed(["reverse proxy tls nginx"]))).tolist()
    )
    with pytest.raises(sqlite3.OperationalError):
        store.db.execute(
            "SELECT rowid FROM vec_docs WHERE embedding MATCH ? AND k = ?",
            (qblob, N),
        ).fetchall()

    searcher = Searcher(settings, embedder=BagEmbedder())

    # Boot for any agent forces the owner-scoped short first pass → widen-retry.
    # Before the clamp this raised (→ boot 500); now it fail-opens to an empty pack.
    pack = boot_pointers(searcher, "anyagent")
    assert pack["pointers"] == []

    # A plain unfiltered search over the same >4096-doc store must not throw.
    results = searcher.search("reverse proxy tls nginx", limit=5)
    assert isinstance(results, list)


def test_widen_retry_clamp_recalls_owner_records_past_first_pool(settings, store):
    """ISOLATES the search.py widen-retry clamp (review follow-up on 4d832f33).

    The prior outage test could not catch a dropped SQLITE_VEC_MAX_K clamp: boot's
    try/except swallows the throw and the plain limit=5 search never fires the
    widen-retry, so removing the clamp stayed green. This test constructs the
    exact failing shape and asserts RECALL, not just no-throw:

      • 60 near padding docs at distance 0 (unscoped 'code') fill the k=50 first
        pass, so an owner-scoped query comes back empty on the first pass;
      • ONE owner-scoped record sits just behind them (small distance) — inside the
        clamped 4096 pool but past the first pass, so ONLY the widen-retry recalls
        it;
      • 4050 far padding docs push the corpus past 4096.

    With the clamp: widen-retry k=4096 recalls the owner record → boot non-empty.
    Without it: k=count>4096 raises, boot fail-opens to EMPTY → this fails, so a
    regression that drops the clamp silently-empties Active-Memory recall and is
    caught here rather than shipping."""
    import time

    import numpy as np
    import sqlite_vec

    from trovex.search import SQLITE_VEC_MAX_K

    emb = BagEmbedder()
    qvec = next(iter(emb.embed([BOOT_QUERY])))  # the exact vector boot embeds
    near_blob = sqlite_vec.serialize_float32(qvec.tolist())

    # Owner vector: qvec nudged on a dim it doesn't use → distance just above 0
    # (behind the near padding) but cosine ≈ 1 (clears the boot floor 0.62).
    zero_dims = [i for i in range(len(qvec)) if qvec[i] == 0.0]
    owner_vec = qvec.copy()
    owner_vec[zero_dims[0]] = 0.1
    owner_vec /= np.linalg.norm(owner_vec)
    owner_blob = sqlite_vec.serialize_float32(owner_vec.tolist())

    # Far vector: orthogonal (distance 1) — pads the count without ever entering
    # the owner's neighbourhood.
    far_vec = np.zeros(len(qvec), dtype=np.float32)
    far_vec[zero_dims[1]] = 1.0
    far_blob = sqlite_vec.serialize_float32(far_vec.tolist())

    now = time.time()  # fresh, so the owner record clears the boot freshness floor

    def _insert(path, src, kind, blob, status="canonical"):
        cur = store.db.execute(
            """INSERT INTO docs
                 (source_id, path, absolute_path, content_hash, size_bytes,
                  tokens_est, mtime, first_indexed, last_indexed, title, kind, status)
               VALUES (?, ?, ?, ?, 10, 3, ?, ?, ?, ?, ?, ?)""",
            (src, path, "/" + path, "h" + path, now, now, now, path, kind, status),
        )
        store.db.execute(
            "INSERT INTO vec_docs(rowid, embedding) VALUES (?, ?)", (cur.lastrowid, blob)
        )
        return cur.lastrowid

    for i in range(60):  # near padding — fills the k=50 first pass
        _insert(f"near/{i}.md", "code", None, near_blob)
    owner_id = _insert("owner/rec.md", "trovex", "record", owner_blob)
    store.db.execute("INSERT INTO doc_tags(doc_id, tag) VALUES (?, 'owner/isolagent')", (owner_id,))
    for i in range(4050):  # far padding — pushes total past 4096
        _insert(f"far/{i}.md", "code", None, far_blob)
    store.db.commit()

    total = store.db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
    assert total > SQLITE_VEC_MAX_K  # the widen-retry k would exceed the ceiling

    searcher = Searcher(settings, embedder=BagEmbedder())

    # Direct scoped search: recalls the owner record ONLY via the clamped
    # widen-retry (first pass is all near-padding). A dropped clamp raises here.
    scoped = searcher.search(
        BOOT_QUERY, limit=5, source_ids=["trovex"], kind="record", tags=["owner/isolagent"]
    )
    assert [r.path for r in scoped] == ["owner/rec.md"]

    # And through boot: a dropped clamp fail-opens to empty → this assertion fails.
    pack = boot_pointers(searcher, "isolagent")
    assert [p["id"] for p in pack["pointers"]] == ["owner/rec.md"]


# --- status='duplicate' excluded from the default retrieval pool -----------


def test_duplicate_status_excluded_from_default_pool(settings, store):
    """A status='duplicate' doc is a near-copy of a canonical one — it must be
    dropped from the default candidate pool (not merely down-weighted), so a
    dup-heavy corpus doesn't crowd canonical hits out of top-K / the rerank pool.
    include_duplicates=True opts back in.

    The store's write-path dedup flags the OLDER near-copy status='duplicate' and
    keeps the newer as canonical — we use that real path rather than hand-setting
    the column, so the test tracks how duplicates actually arise."""
    query = "kubernetes pod rollout crash loop deploy rollback"
    older = store.put(f"# runbook\n\n{query}", kind="reference")
    newer = store.put(f"# runbook copy\n\n{query}", kind="reference")
    # Write-path dedup demoted the older near-copy to status='duplicate'.
    assert store.db.execute("SELECT status FROM docs WHERE ext_id = ?", (older,)).fetchone()[
        "status"
    ] == "duplicate"

    searcher = Searcher(settings, embedder=BagEmbedder())

    default = {r.path for r in searcher.search(query, limit=10)}
    assert newer in default  # the canonical survivor
    assert older not in default  # duplicate dropped from the default pool

    # Opt-in surfaces it again → proves the emptiness above was the dup filter,
    # not a scope/recall miss.
    opted_in = {r.path for r in searcher.search(query, limit=10, include_duplicates=True)}
    assert older in opted_in


# --- SSOT: one live canonical per topic (schema-enforced) -------------------


def test_second_canonical_for_a_topic_is_refused_or_supersedes(settings, store):
    """SSOT (e0fd2625): a CREATE that would fork a second live canonical for a topic
    is REFUSED (TopicCollisionError) unless force=True, which atomically SUPERSEDES the
    prior canon so exactly one live canonical per topic survives."""
    from trovex.store import TopicCollisionError

    first = store.put("# Auth guide\n\noriginal body about jwt rotation", kind="reference")

    # Same title/topic, DIFFERENT body (embedding dedup wouldn't catch it) → refused.
    with pytest.raises(TopicCollisionError) as ei:
        store.put("# Auth guide\n\ncompletely different content here", kind="reference")
    assert ei.value.ext_id == first

    # force=True supersedes the prior canon and installs the new one.
    second = store.put(
        "# Auth guide\n\ncompletely different content here", kind="reference", force=True
    )
    rows = {
        r["ext_id"]: (r["status"], r["lifecycle"])
        for r in store.db.execute(
            "SELECT ext_id, status, lifecycle FROM docs WHERE ext_id IN (?, ?)", (first, second)
        )
    }
    assert rows[first] == ("superseded", "archived")  # prior canon stepped down
    assert rows[second][0] == "canonical"
    # Exactly one live canonical carries the topic slug now.
    live = store.db.execute(
        "SELECT COUNT(*) AS c FROM docs WHERE canonical_topic = 'auth-guide' AND status = 'canonical'"
    ).fetchone()["c"]
    assert live == 1

    # Ephemeral kinds carry no topic and never collide — two same-title records OK.
    store.put("# Standup\n\nmonday state", kind="record")
    store.put("# Standup\n\ntuesday state", kind="record")  # no TopicCollisionError raised


def test_update_rename_into_existing_topic_raises_topiccollision(settings, store):
    """SSOT UPDATE-path guard (e0fd2625 review r1): renaming a live canonical's
    title so its slug lands on ANOTHER live canonical's topic must raise
    TopicCollisionError — a clean, actionable block — not the raw sqlite
    IntegrityError from the unique index that an agent write can't recover from."""
    from trovex.store import TopicCollisionError

    a = store.put("# Alpha guide\n\nbody about alpha", kind="reference")  # topic alpha-guide
    b = store.put("# Beta guide\n\nbody about beta", kind="reference")  # topic beta-guide

    # Rename b's title onto alpha-guide → collides with a's live canonical.
    with pytest.raises(TopicCollisionError) as ei:
        store.put("# Alpha guide\n\nbody about beta, renamed", ext_id=b, kind="reference")
    assert ei.value.ext_id == a

    # force=True supersedes a and lets b take the topic.
    store.put("# Alpha guide\n\nbody about beta, renamed", ext_id=b, kind="reference", force=True)
    assert store.db.execute("SELECT status FROM docs WHERE ext_id = ?", (a,)).fetchone()[
        "status"
    ] == "superseded"
    assert store.db.execute("SELECT status FROM docs WHERE ext_id = ?", (b,)).fetchone()[
        "status"
    ] == "canonical"


def test_migration_backfills_and_dedupes_canonical_pair(settings, store):
    """The migration backfills canonical_topic and DE-DUPES the same-title canonical
    pairs that already exist (keep newest, supersede the rest) BEFORE building the
    partial unique index — so an already-forked store converges to SSOT on open."""
    import sqlite3

    from trovex.db import _migrate_add_canonical_topic

    # Simulate a PRE-migration store: no canonical_topic column, no unique index.
    store.db.execute("DROP INDEX IF EXISTS idx_docs_canonical_topic")
    store.db.execute("ALTER TABLE docs DROP COLUMN canonical_topic")
    store.db.commit()
    # Two same-title canonical trovex docs coexist (the pre-SSOT bug), older first.
    for i, mt in enumerate((100.0, 200.0)):
        store.db.execute(
            """INSERT INTO docs
                 (source_id, path, absolute_path, content_hash, size_bytes, tokens_est,
                  mtime, first_indexed, last_indexed, title, status, ext_id, kind)
               VALUES ('trovex', ?, ?, ?, 10, 3, ?, ?, ?, 'Auth Guide', 'canonical', ?, 'reference')""",
            (f"p{i}", f"/p{i}", f"h{i}", mt, mt, mt, f"ext{i}"),
        )
    store.db.commit()

    _migrate_add_canonical_topic(store.db)

    rows = {
        r["ext_id"]: (r["status"], r["canonical_topic"])
        for r in store.db.execute("SELECT ext_id, status, canonical_topic FROM docs")
    }
    assert rows["ext1"][0] == "canonical"  # newest (mtime 200) kept
    assert rows["ext0"][0] == "superseded"  # older stepped down
    assert rows["ext1"][1] == "auth-guide"  # slug backfilled
    # The rebuilt unique index now refuses a second live canonical for the topic.
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("UPDATE docs SET status = 'canonical' WHERE ext_id = 'ext0'")
