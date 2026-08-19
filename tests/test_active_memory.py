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
    # Partitioned vec_docs: source_id='code' shard, metadata from the docs defaults.
    store.db.executemany(
        "INSERT INTO vec_docs(rowid, source_id, embedding, kind, lifecycle, status) "
        "VALUES (?, 'code', ?, 'doc', 'active', 'canonical')",
        [(i, blob) for i in ids],
    )
    store.db.commit()


def test_partitioned_knn_over_4096_docs_scopes_correctly(settings, store):
    """P2a: the 4096 KNN ceiling is gone STRUCTURALLY. source_id is the vec0
    partition key, so a >4096-doc corpus spread across partitions is fine — each
    KNN scans only its source's bounded shard with a small k, no clamp/widen.

    Seed a >4096-doc 'code' partition plus one owner record in the 'trovex' (SSOT)
    partition, then assert: boot recalls the owner record from the small trovex
    shard (unaffected by the 4100 code docs), and a search SCOPED to 'code' returns
    results from the big shard — neither raises, both with a tiny k."""
    _bulk_seed_docs(store, 4100)  # 4100 docs in the 'code' partition
    total = store.db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
    assert total > 4096  # corpus genuinely exceeds the old ceiling

    # One owner record in the SSOT ('trovex') partition, fresh so it clears the floor.
    owner = store.put(
        f"# resume\n\n{BOOT_QUERY}", kind="record", tags=["owner/agentx"]
    )

    searcher = Searcher(settings, embedder=BagEmbedder())

    # Boot scans ONLY the small 'trovex' partition — recalls the owner record, and
    # the 4100-doc 'code' partition never enters the scan (no ceiling, no crash).
    pack = boot_pointers(searcher, "agentx")
    assert [p["id"] for p in pack["pointers"]] == [owner]

    # A search scoped to the >4096-doc 'code' partition returns results with a tiny
    # k (50) — the partition bounds the scan; the old widen-to-4096 clamp is retired.
    scoped = searcher.search("reverse proxy tls nginx seed", limit=5, source_ids=["code"])
    assert scoped and all(r.source_id == "code" for r in scoped)


def test_archived_heavy_partition_does_not_squeeze_live_recall(settings, store):
    """Round-1 review regression: vec0 pushes '=', '!=', 'IN' metadata constraints
    INTO the KNN but NOT 'NOT IN' — a `lifecycle NOT IN (...)` clause would
    post-filter the k-window instead. On a partition where the k nearest are all
    archived, that silently squeezes live recall to zero (and P2a retired the
    widen-retry that used to compensate). The exclude must be chained '!=', so a
    live doc buried behind an archived cluster is still recalled.

    Seed 60 archived docs at the exact query embedding (distance 0, they fill the
    k=50 window) plus one active doc a hair farther. A NOT IN clause returns
    nothing; the chained '!=' returns the active doc."""
    import sqlite_vec

    q = "reverse proxy tls nginx seed"
    emb = next(iter(store.embedder.embed([q]))).tolist()
    blob = sqlite_vec.serialize_float32(emb)
    active_emb = next(iter(store.embedder.embed([q + " extra farther token"]))).tolist()
    active_blob = sqlite_vec.serialize_float32(active_emb)
    now = 1_600_000_000.0

    def _seed(i, lifecycle, b):
        store.db.execute(
            """INSERT INTO docs
                 (source_id, path, absolute_path, content_hash, size_bytes, tokens_est,
                  mtime, first_indexed, last_indexed, title, lifecycle)
               VALUES ('arch', ?, ?, ?, 10, 3, ?, ?, ?, ?, ?)""",
            (f"arch/{i}.md", f"/arch/{i}.md", f"h{i}", now, now, now, f"seed {i}", lifecycle),
        )
        rid = store.db.execute("SELECT id FROM docs WHERE path = ?", (f"arch/{i}.md",)).fetchone()["id"]
        store.db.execute(
            "INSERT INTO vec_docs(rowid, source_id, embedding, kind, lifecycle, status) "
            "VALUES (?, 'arch', ?, 'doc', ?, 'canonical')",
            (rid, b, lifecycle),
        )

    for i in range(60):  # 60 archived at distance 0 → fill the k=50 window
        _seed(i, "archived", blob)
    _seed(999, "active", active_blob)  # one live doc, a hair farther
    store.db.commit()

    searcher = Searcher(settings, embedder=store.embedder)
    hits = searcher.search(q, limit=5, source_ids=["arch"])
    # The active doc survives the archived-heavy k-window — no NOT IN squeeze.
    assert hits, "archived-heavy partition squeezed live recall to zero (NOT IN regression)"
    assert all(h.source_id == "arch" for h in hits)
    assert any(h.path == "arch/999.md" for h in hits)


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


# --- bc4d183d: bloat sweep + enforced agent-artifact ignores ---------------


def test_sweep_bloat_tombstones_superseded_and_ages_owned_idempotent(settings, store):
    """The sweep tombstone-DELETES superseded forks (so their vec_docs rows leave
    the KNN corpus) and re-marks age-stale owned non-record docs — idempotently."""
    import time as _time

    # A superseded fork via the SSOT supersede path.
    old = store.put("# Topic X\n\noriginal", kind="reference")
    store.put("# Topic X\n\nreplacement body", kind="reference", force=True)
    assert store.db.execute("SELECT status FROM docs WHERE ext_id = ?", (old,)).fetchone()[
        "status"
    ] == "superseded"

    # An owned canonical older than stale_age_days, plus a fresh one and a record.
    fresh = store.put("# Fresh doc\n\nrecent notes", kind="reference")
    aged = store.put("# Aged doc\n\nancient notes", kind="reference")
    rec = store.put("# Incident\n\nevent anchored", kind="record", tags=["owner/x"])
    ancient = _time.time() - (settings.stale_age_days + 1) * 86400
    store.db.execute(
        "UPDATE docs SET mtime = ? WHERE ext_id IN (?, ?)", (ancient, aged, rec)
    )
    store.db.commit()

    result = store.sweep_bloat()
    assert result["superseded_deleted"] == 1
    assert result["stale_marked"] == 1

    # Superseded fork is gone from the corpus (and its vec row with it)...
    assert store.db.execute("SELECT 1 FROM docs WHERE ext_id = ?", (old,)).fetchone() is None
    assert store.db.execute("SELECT 1 FROM vec_docs WHERE rowid NOT IN (SELECT id FROM docs)").fetchone() is None
    # ...but recoverable via the tombstone snapshot.
    assert any(t["title"] == "Topic X" for t in store.list_tombstones())
    # Aged owned canonical → stale; fresh stays canonical; the old RECORD is never aged.
    assert store.db.execute("SELECT status FROM docs WHERE ext_id = ?", (aged,)).fetchone()[
        "status"
    ] == "stale"
    assert store.db.execute("SELECT status FROM docs WHERE ext_id = ?", (fresh,)).fetchone()[
        "status"
    ] == "canonical"
    assert store.db.execute("SELECT status FROM docs WHERE ext_id = ?", (rec,)).fetchone()[
        "status"
    ] == "canonical"

    # Idempotent: a second run finds nothing to do.
    assert store.sweep_bloat() == {
        "superseded_deleted": 0,
        "stale_marked": 0,
        "ephemeral_owners_collapsed": 0,
    }


def test_reindex_enforces_builtin_agent_artifact_ignores(tmp_path):
    """The indexer ALWAYS excludes agent-artifact globs (resume/checkpoint/lessons)
    even without a repo .trovexignore, and a re-index never re-adds them."""
    from trovex.indexer import Indexer

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "normal.md").write_text("# Normal\n\nkeep this doc", encoding="utf-8")
    (repo / "resume.md").write_text("# Resume\n\nagent scratch", encoding="utf-8")
    (repo / "checkpoint-2.md").write_text("# Checkpoint\n\nscratch", encoding="utf-8")
    (repo / "lessons.md").write_text("# Lessons\n\nscratch", encoding="utf-8")

    settings = Settings(
        data_dir=tmp_path / "data",
        project_root=repo,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    idx = Indexer(settings, embedder=BagEmbedder())

    def _names():
        return {
            r["path"].rsplit("/", 1)[-1] for r in idx.db.execute("SELECT path FROM docs")
        }

    idx.reindex(root=repo)
    names = _names()
    assert "normal.md" in names
    assert not ({"resume.md", "checkpoint-2.md", "lessons.md"} & names)

    idx.reindex(root=repo)  # re-index must not re-add the ignored globs
    assert not ({"resume.md", "checkpoint-2.md", "lessons.md"} & _names())


def test_compute_status_preserves_superseded_no_ssot_crash(settings, store):
    """Regression (bc4d183d review r1): compute_status bulk-reset every doc to
    'canonical', which reset an SSOT-superseded doc back to canonical while its live
    canonical still existed → IntegrityError on the partial unique index, crashing
    the reindex; it also erased the superseded flag the sweep needs. compute_status
    must LEAVE superseded docs alone."""
    from trovex.status import compute_status

    old = store.put("# Topic Z\n\noriginal", kind="reference")
    store.put("# Topic Z\n\nreplacement body", kind="reference", force=True)  # supersedes old
    assert store.db.execute("SELECT status FROM docs WHERE ext_id = ?", (old,)).fetchone()[
        "status"
    ] == "superseded"

    compute_status(store.db, store.settings)  # must NOT raise on the SSOT unique index
    assert store.db.execute("SELECT status FROM docs WHERE ext_id = ?", (old,)).fetchone()[
        "status"
    ] == "superseded"  # left intact, so the reindex-order sweep can still tombstone it

    assert store.sweep_bloat()["superseded_deleted"] == 1
    assert store.db.execute("SELECT 1 FROM docs WHERE ext_id = ?", (old,)).fetchone() is None


def test_sweep_collapses_numeric_suffix_ephemeral_owner_forks(settings, store):
    """A respawned agent leaves owner/<name>-<N> record forks. The sweep tombstones
    them: keep the unsuffixed owner/<name> if it exists, else keep the highest N.
    Reversible (tombstoned, recoverable) and idempotent."""
    # Group A: an unsuffixed canonical owner + two numbered respawn forks.
    a_canon = store.put("# dev state\n\ncanonical dev owner", kind="record", tags=["owner/dev"])
    a60 = store.put("# dev 60\n\nrespawn sixty", kind="record", tags=["owner/dev-60"])
    a61 = store.put("# dev 61\n\nrespawn sixtyone", kind="record", tags=["owner/dev-61"])
    # Group B: NO unsuffixed — only numbered respawns; keep the highest.
    b1 = store.put("# qa 1\n\nrespawn one", kind="record", tags=["owner/qa-1"])
    b2 = store.put("# qa 2\n\nrespawn two", kind="record", tags=["owner/qa-2"])
    # A normal owner with no forks — untouched.
    cmo = store.put("# cmo state\n\nlaunch metrics", kind="record", tags=["owner/cmo"])

    def _alive(ext):
        return store.db.execute("SELECT 1 FROM docs WHERE ext_id = ?", (ext,)).fetchone() is not None

    result = store.sweep_bloat()
    assert result["ephemeral_owners_collapsed"] == 3  # a60, a61, b1

    assert _alive(a_canon) and not _alive(a60) and not _alive(a61)  # unsuffixed kept
    assert _alive(b2) and not _alive(b1)  # highest-N kept
    assert _alive(cmo)  # unrelated owner untouched

    # Reversible: the forks are tombstoned (recoverable), not hard-erased.
    tomb_titles = {t["title"] for t in store.list_tombstones()}
    assert {"dev 60", "dev 61", "qa 1"} <= tomb_titles

    # Idempotent: nothing left to collapse.
    assert store.sweep_bloat()["ephemeral_owners_collapsed"] == 0
