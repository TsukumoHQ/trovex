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


def test_unpinned_search_scans_all_partitions_not_just_trovex(settings, store):
    """Round-2 review regression: source='*' and an unpinned connection resolve to
    source_ids=None = the documented 'search the whole store' contract. P2a's KNN
    fell back to ['trovex'] for None, silently dropping ALL dense hits from
    file-backed partitions (a dense-only query returned nothing). None must scan
    EVERY partition and merge by distance.

    Seed a doc that matches the query only in a file-backed 'code' partition (the
    'trovex' partition holds an unrelated doc), then a dense-only unpinned search
    must still recall the 'code' doc."""
    import sqlite_vec

    q = "kubernetes ingress controller tls termination"
    match_blob = sqlite_vec.serialize_float32(next(iter(store.embedder.embed([q]))).tolist())
    other_blob = sqlite_vec.serialize_float32(
        next(iter(store.embedder.embed(["quarterly budget spreadsheet finance"]))).tolist()
    )
    now = 1_600_000_000.0

    def _seed(source_id, path, blob):
        store.db.execute(
            """INSERT INTO docs
                 (source_id, path, absolute_path, content_hash, size_bytes, tokens_est,
                  mtime, first_indexed, last_indexed, title, lifecycle)
               VALUES (?, ?, ?, ?, 10, 3, ?, ?, ?, ?, 'active')""",
            (source_id, path, f"/{path}", f"h-{path}", now, now, now, path),
        )
        rid = store.db.execute("SELECT id FROM docs WHERE path = ?", (path,)).fetchone()["id"]
        store.db.execute(
            "INSERT INTO vec_docs(rowid, source_id, embedding, kind, lifecycle, status) "
            "VALUES (?, ?, ?, 'doc', 'active', 'canonical')",
            (rid, source_id, blob),
        )

    _seed("code", "code/ingress.md", match_blob)  # file-backed source, matches q
    _seed("trovex", "trovex/unrelated.md", other_blob)  # SSOT, does NOT match q
    store.db.commit()

    searcher = Searcher(settings, embedder=store.embedder)
    # Unpinned (source_ids=None), dense-only so BM25 can't mask a dropped dense hit.
    hits = searcher.search(q, limit=5, source_ids=None, hybrid=False)
    assert any(h.source_id == "code" for h in hits), (
        "unpinned dense search saw only the trovex partition — file-source recall lost"
    )


def test_boot_never_returns_cold_tier_but_explicit_source_reaches_it(settings, store):
    """P2b AC: boot scans ONLY the ssot ('trovex') tier — a cold file-indexed
    artifact never leaks into an agent's boot pack even when it matches the boot
    query — while an explicit source query still reaches the cold corpus.

    (The unpinned-flagship-default→ssot routing lives in _resolve_source and is
    covered in test_mcp_contract; this pins the boot + explicit-source ends.)"""
    import sqlite_vec

    # A cold 'code' artifact whose text matches the boot query verbatim — the
    # strongest possible pull. Only tier scoping (not tags/score) can exclude it.
    blob = sqlite_vec.serialize_float32(next(iter(store.embedder.embed([BOOT_QUERY]))).tolist())
    now = 1_600_000_000.0
    store.db.execute(
        """INSERT INTO docs
             (source_id, path, absolute_path, content_hash, size_bytes, tokens_est,
              mtime, first_indexed, last_indexed, title, lifecycle)
           VALUES ('code', 'code/hot.md', '/code/hot.md', 'h-hot', 10, 3, ?, ?, ?, 'hot', 'active')""",
        (now, now, now),
    )
    rid = store.db.execute("SELECT id FROM docs WHERE path = 'code/hot.md'").fetchone()["id"]
    store.db.execute(
        "INSERT INTO vec_docs(rowid, source_id, embedding, kind, lifecycle, status) "
        "VALUES (?, 'code', ?, 'doc', 'active', 'canonical')",
        (rid, blob),
    )
    # One owner record in the ssot tier so boot has something legitimate to recall.
    owner = store.put(f"# resume\n\n{BOOT_QUERY}", kind="record", tags=["owner/agentx"])
    store.db.commit()

    searcher = Searcher(settings, embedder=store.embedder)

    # Boot is ssot-scoped → the cold artifact never appears; the owner record does.
    pack = boot_pointers(searcher, "agentx")
    ids = [p["id"] for p in pack["pointers"]]
    assert rid not in ids, "boot leaked a cold-tier artifact (tier scoping failed)"
    assert owner in ids

    # But the cold corpus is reachable on purpose via an explicit source filter.
    cold = searcher.search(BOOT_QUERY, limit=5, source_ids=["code"])
    assert any(h.path == "code/hot.md" for h in cold), "explicit source query didn't reach cold"


def test_agent_artifact_globs_ignored_anywhere_in_basename(settings):
    """P2c AC: the fleet's per-agent scratch .md (resume/checkpoint/lessons) must
    never enter the index. The globs match the token ANYWHERE in the basename, so
    `trovex-backend-resume.md` and `2026-checkpoint.md` are caught — not only names
    that START with the token (the earlier prefix globs let those through)."""
    from trovex.indexer import _is_ignored

    globs = settings.default_ignore_globs
    for name in (
        "resume.md",
        "trovex-backend-resume.md",
        "2026-checkpoint.md",
        "sprint-lessons.md",
        ".niwa-decision.md",
        "docs/agent-resume.md",
    ):
        assert _is_ignored(name, globs), f"{name} should be ignored"
    # A legit doc that merely mentions a topic is NOT swept.
    for name in ("architecture.md", "deploy-guide.md", "api.md"):
        assert not _is_ignored(name, globs), f"{name} should NOT be ignored"


def test_store_only_kind_is_bm25_findable_but_not_in_knn(settings, store):
    """P2c AC: a store-only kind lands in FTS (BM25-findable) but creates NO
    vec_docs/vec_chunks row — zero KNN pressure. A normal kind still embeds."""
    store.settings.store_only_kinds = ["reference"]

    body = "kubernetes ingress controller tls termination reference material"
    archived = store.put(f"# Ingress reference\n\n{body}", kind="reference")
    normal = store.put(f"# Ingress howto\n\n{body} howto steps", kind="doc")

    aid = store.db.execute("SELECT id FROM docs WHERE ext_id = ?", (archived,)).fetchone()["id"]
    nid = store.db.execute("SELECT id FROM docs WHERE ext_id = ?", (normal,)).fetchone()["id"]

    # Store-only doc: no vectors at all.
    assert store.db.execute("SELECT COUNT(*) c FROM vec_docs WHERE rowid = ?", (aid,)).fetchone()["c"] == 0
    assert (
        store.db.execute(
            "SELECT COUNT(*) c FROM vec_chunks WHERE rowid IN (SELECT id FROM chunks WHERE doc_id = ?)",
            (aid,),
        ).fetchone()["c"]
        == 0
    )
    # Normal doc DID embed.
    assert store.db.execute("SELECT COUNT(*) c FROM vec_docs WHERE rowid = ?", (nid,)).fetchone()["c"] == 1

    # But the store-only doc is still chunk-indexed for BM25 (keyword-findable).
    assert store.db.execute(
        "SELECT COUNT(*) c FROM chunks WHERE doc_id = ?", (aid,)
    ).fetchone()["c"] >= 1
    searcher = Searcher(settings, embedder=store.embedder)
    hits = searcher.search("kubernetes ingress tls reference", limit=10, source_ids=["trovex"])
    assert archived in [
        store.db.execute("SELECT ext_id FROM docs WHERE path = ?", (h.path,)).fetchone()["ext_id"]
        for h in hits
    ], "store-only doc not found via BM25"


def test_query_embed_is_lru_cached(settings, store):
    """T1: a repeated query embeds ONCE — the LRU query cache turns the ONNX
    forward pass into a dict hit. /api/boot re-embeds the same BOOT_QUERY every
    session, so this collapses the boot/repeat-query latency curve."""
    from trovex.query_cache import clear_query_cache

    clear_query_cache()
    base = store.embedder
    calls = {"n": 0}

    class Counting:
        name = base.name
        dim = base.dim

        def embed(self, texts):
            texts = list(texts)
            calls["n"] += len(texts)
            return base.embed(texts)

    store.put("# doc\n\nzookeeper quorum election timeout tuning", kind="doc")
    searcher = Searcher(settings, embedder=Counting())
    q = "zookeeper quorum election timeout"
    r1 = searcher.search(q, limit=5, source_ids=["trovex"])
    r2 = searcher.search(q, limit=5, source_ids=["trovex"])  # cache hit
    searcher.search(q, limit=5, source_ids=["trovex"])  # cache hit
    assert calls["n"] == 1, f"query embedded {calls['n']}x, expected 1 (one cold miss)"
    # No correctness change — cached blob yields identical results.
    assert [h.path for h in r1] == [h.path for h in r2]


def test_store_only_flip_purges_vectors_on_unchanged_rewrite(settings, store):
    """review-af03da67 leak: re-putting an IDENTICAL doc (same content+title) but
    flipped to a store-only kind hits the content_unchanged fast-path — which must
    still purge the doc's vectors, else it stays in the KNN pool."""
    body = "# note\n\nkafka consumer group rebalance sticky assignor"
    ext = store.put(body, kind="doc")
    did = store.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext,)).fetchone()["id"]
    assert store.db.execute("SELECT COUNT(*) c FROM vec_docs WHERE rowid = ?", (did,)).fetchone()["c"] == 1

    store.settings.store_only_kinds = ["reference"]
    store.put(body, kind="reference", ext_id=ext)  # identical content+title, kind flips

    assert store.db.execute("SELECT COUNT(*) c FROM vec_docs WHERE rowid = ?", (did,)).fetchone()["c"] == 0
    assert (
        store.db.execute(
            "SELECT COUNT(*) c FROM vec_chunks WHERE rowid IN (SELECT id FROM chunks WHERE doc_id = ?)",
            (did,),
        ).fetchone()["c"]
        == 0
    )


def test_store_only_flip_back_re_embeds(settings, store):
    """review-6c02c654 leak: the store-only purge must clear content_hash, so a
    later flip BACK to a searchable kind with IDENTICAL content re-embeds instead
    of being swallowed by the content_unchanged fast-path (permanent BM25-only)."""
    store.settings.store_only_kinds = ["reference"]
    body = "# spec\n\nraft leader election heartbeat randomized timeout"

    ext = store.put(body, kind="doc")  # embedded
    did = store.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext,)).fetchone()["id"]

    def vcount():
        return store.db.execute("SELECT COUNT(*) c FROM vec_docs WHERE rowid = ?", (did,)).fetchone()["c"]

    assert vcount() == 1
    store.put(body, kind="reference", ext_id=ext)  # flip to store-only (identical content)
    assert vcount() == 0  # purged
    store.put(body, kind="doc", ext_id=ext)  # flip BACK (identical content)
    assert vcount() == 1, "flip-back to a searchable kind must re-embed (content_hash cleared)"


def test_rerank_skips_when_candidates_le_limit():
    """T4: with <= limit candidates every one is returned anyway, so the
    cross-encoder pass is skipped — original order, no rerank info, no model load."""
    from trovex.rerank import maybe_rerank
    from trovex.search import SearchResult

    cands = [
        SearchResult(
            path=f"p{i}", title=f"t{i}", distance=0.1, score=1.0, age_days=0.0,
            status="canonical", size_bytes=1, tokens_est=1, absolute_path="", source_id="trovex",
        )
        for i in range(3)
    ]
    out, info = maybe_rerank("q", cands, limit=5)
    assert out == cands  # untouched order
    assert info is None  # rerank did not run


def test_query_cache_is_per_scope_and_ttl(settings, store, monkeypatch):
    """T5: a write to ANOTHER source no longer voids this scope's cached entry
    (per-scope version), while a write to THIS source does; and a past-TTL entry
    misses."""
    from trovex import cache as qc

    db = store.db
    store.put("# a\n\ntrovex owned doc about caching", kind="doc")  # a 'trovex' doc
    # Seed a cache entry versioned to the 'trovex' scope.
    v = qc.corpus_version(db, "trovex")
    qc.put(db, "cache q", False, v, "OUT", 1, 10, 3, 2)
    assert qc.get(db, "cache q", False, v) is not None

    # A write to a DIFFERENT source ('code') must NOT change the trovex version.
    store.db.execute(
        """INSERT INTO docs (source_id, path, absolute_path, content_hash, size_bytes,
             tokens_est, mtime, first_indexed, last_indexed, title)
           VALUES ('code', 'code/x.md', '/code/x.md', 'h', 1, 1, 9e9, 9e9, 9e9, 'x')"""
    )
    store.db.commit()
    assert qc.corpus_version(db, "trovex") == v  # unaffected
    assert qc.get(db, "cache q", False, v) is not None  # still a hit

    # A write to THIS source bumps its version → the old entry is invalidated.
    store.put("# b\n\nanother trovex owned doc", kind="doc")
    assert qc.corpus_version(db, "trovex") != v

    # TTL: with a zero window, even a fresh entry misses.
    monkeypatch.setattr(qc, "_TTL_SEC", -1.0)
    v2 = qc.corpus_version(db, "trovex")
    qc.put(db, "ttl q", False, v2, "OUT", 1, 10, 3, 2)
    assert qc.get(db, "ttl q", False, v2) is None


def test_capacity_report_flags_near_limit_and_counts_vectors_only(settings, store, monkeypatch):
    """P3 headroom: capacity_report is silent with headroom and flags a partition
    nearing the vec0 KNN ceiling. partition_counts reads the vec0 tables (the KNN
    working set), so a store-only doc (no vector) adds zero KNN pressure."""
    from trovex import capacity

    for i in range(6):
        store.put(f"# d{i}\n\ncaching and storage headroom body {i}", kind="doc")
    # A store-only doc: FTS-indexed but no vector → must NOT count toward capacity.
    store.settings.store_only_kinds = ["reference"]
    store.put("# ref\n\narchival reference no vector", kind="reference")

    counts = capacity.partition_counts(store.db)
    assert counts["trovex"]["docs"] == 6, "store-only doc must not add a vec_docs row"

    # Real (huge) limits → headroom → silent.
    assert capacity.capacity_report(store.db) == []

    # Lower the ceiling so the seeded chunks trip the warn threshold.
    monkeypatch.setattr(capacity, "VEC0_K_CEILING", 5)
    rep = capacity.capacity_report(store.db)
    assert rep and rep[0]["source_id"] == "trovex"
    assert "ceiling" in rep[0]["reason"]


def test_importance_for_blends_status_pin_access():
    """P3: importance = status base + pin boost + saturating access frequency."""
    from trovex.retention import importance_for

    assert importance_for("canonical", 0, 0) == 1.0
    assert importance_for("duplicate", 0, 0) == 0.0
    assert importance_for("canonical", 1, 0) == 2.0  # + pin boost
    assert importance_for("plan", 0, 100) == 0.6 + 0.5  # access saturates at +0.5
    assert importance_for("canonical", 0, 5) == round(1.0 + 0.5 * 0.5, 4)


def test_recompute_importance_from_status_and_access(settings, store):
    """P3: recompute_importance derives docs.importance from status/pinned + the
    query-log hit counts, deterministically."""
    ext = store.put("# hot\n\ncaching strategy write-through", kind="doc")
    did = store.db.execute("SELECT id, path FROM docs WHERE ext_id = ?", (ext,)).fetchone()
    # Log 3 query-result hits on this doc's path.
    store.db.execute(
        "INSERT INTO mcp_queries (ts, query) VALUES (1.0, 'q')"
    )
    qid = store.db.execute("SELECT id FROM mcp_queries LIMIT 1").fetchone()["id"]
    for rank in range(3):
        store.db.execute(
            "INSERT INTO mcp_query_results (query_id, rank, path) VALUES (?, ?, ?)",
            (qid, rank, did["path"]),
        )
    store.db.commit()

    store.recompute_importance()
    imp = store.db.execute("SELECT importance FROM docs WHERE id = ?", (did["id"],)).fetchone()[
        "importance"
    ]
    assert imp == round(1.0 + 0.5 * (3 / 10), 4)  # canonical base + access(3/10)


def test_importance_boosts_flagship_ranking(settings, store):
    """P3: an old-but-important doc outranks a fresh trivial one in the flagship
    hybrid ranking (importance multiplies the score; boot's dense path is untouched)."""
    q = "distributed consensus quorum protocol"
    important = store.put(f"# critical\n\n{q}", kind="doc")
    trivial = store.put(f"# note\n\n{q}", kind="doc")
    # Make the important doc OLD (worse freshness) but high-importance; trivial is
    # fresh but low-importance. Importance must flip the order.
    old = 1_000_000.0
    store.db.execute(
        "UPDATE docs SET importance = 3.0, mtime = ? WHERE ext_id = ?", (old, important)
    )
    store.db.execute("UPDATE docs SET importance = 0.0 WHERE ext_id = ?", (trivial,))
    store.db.commit()

    searcher = Searcher(settings, embedder=store.embedder)
    hits = searcher.search(q, limit=5, source_ids=["trovex"])  # hybrid
    assert hits[0].path == important, "high-importance old doc must outrank fresh trivia"


def test_ttl_sweep_opt_in_ages_owned_docs_and_exempts_records_and_pinned(settings, store):
    """P3: the TTL sweep is opt-in (no-op by default); when enabled it ages a
    low-value old OWNED doc active→archived→pending_delete→hard-delete, while
    owned records and pinned docs are never touched. Deterministic + idempotent."""
    old = 1_000.0  # ancient mtime → past every age threshold

    def _seed(kind, status, pinned=0):
        ext = store.put(f"# {kind}-{status}\n\nbody about eviction {kind} {status}", kind=kind)
        store.db.execute(
            "UPDATE docs SET status = ?, mtime = ?, pinned = ? WHERE ext_id = ?",
            (status, old, pinned, ext),
        )
        store.db.commit()
        return ext

    stale = _seed("doc", "stale")
    record = _seed("record", "canonical")  # exempt by kind
    pinned = _seed("reference", "stale", pinned=1)  # exempt by pin

    def lc(ext):
        return store.db.execute("SELECT lifecycle FROM docs WHERE ext_id = ?", (ext,)).fetchone()[
            "lifecycle"
        ]

    # Default: opt-in OFF → nothing moves.
    assert store.sweep_retention() == {
        "archived": 0, "queued_delete": 0, "hard_deleted": 0, "importance_updated": 0
    }
    assert lc(stale) == "active"

    # Enable → stale owned doc archives; record + pinned stay active.
    store.settings.retention_sweep_enabled = True
    s1 = store.sweep_retention()
    assert s1["archived"] == 1
    assert lc(stale) == "archived"
    assert lc(record) == "active" and lc(pinned) == "active"

    # Backdate the archived-at so it's past the pending window → queued for delete.
    store.db.execute(
        "UPDATE docs SET lifecycle_changed_at = 1.0 WHERE ext_id = ?", (stale,)
    )
    store.db.commit()
    s2 = store.sweep_retention()
    assert s2["queued_delete"] == 1
    assert lc(stale) == "pending_delete"

    # Enable hard-delete + backdate → tombstone + hard delete (recoverable).
    store.settings.retention_hard_delete = True
    store.db.execute("UPDATE docs SET lifecycle_changed_at = 1.0 WHERE ext_id = ?", (stale,))
    store.db.commit()
    s3 = store.sweep_retention()
    assert s3["hard_deleted"] == 1
    assert store.db.execute("SELECT 1 FROM docs WHERE ext_id = ?", (stale,)).fetchone() is None
    assert (
        store.db.execute("SELECT 1 FROM doc_tombstones WHERE ext_id = ?", (stale,)).fetchone()
        is not None
    )
    # Idempotent: a second run with nothing newly past a boundary is a clean no-op.
    s4 = store.sweep_retention()
    assert s4["archived"] == 0 and s4["queued_delete"] == 0 and s4["hard_deleted"] == 0
    # Records + pinned survived the whole sweep.
    assert lc(record) == "active" and lc(pinned) == "active"


def test_manually_archived_canonical_never_evicted(settings, store):
    """task 281fac86: only LOW-VALUE docs walk the full eviction chain. A
    deliberately archived owned CANONICAL (via set_lifecycle) must never queue or
    hard-delete, even past every window — a manual archive is keep-hidden, not a
    delete-queue."""
    store.settings.retention_sweep_enabled = True
    store.settings.retention_hard_delete = True
    ext = store.put("# keep\n\nimportant canonical decision body", kind="doc")
    store.set_lifecycle(ext, "archived")  # deliberate archive; status stays canonical
    # Backdate past every window so ONLY the status filter can save it.
    store.db.execute(
        "UPDATE docs SET lifecycle_changed_at = 1.0, mtime = 1.0 WHERE ext_id = ?", (ext,)
    )
    store.db.commit()

    s = store.sweep_retention()
    assert s["queued_delete"] == 0 and s["hard_deleted"] == 0
    row = store.db.execute(
        "SELECT lifecycle, status FROM docs WHERE ext_id = ?", (ext,)
    ).fetchone()
    assert row is not None, "a manually-archived canonical must not be hard-deleted"
    assert row["lifecycle"] == "archived"  # stays archived, never progresses


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
