"""v0.9 — trovex-owned store: write/read roundtrip, semantic routing, lifecycle.

Hermetic: a deterministic bag-of-words embedder (no OpenAI / no model download).
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import re
import time

import numpy as np
import pytest

from trovex.config import Settings, Source
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.status import compute_status
from trovex.store import SqliteStore, extract_section, replace_section

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


def test_put_get_roundtrip(store):
    body = "# Outage 2026-06-09\n\nThe auth database ran out of connections."
    ext_id = store.put(body, kind="record")
    assert ext_id
    doc = store.get(ext_id)
    assert doc is not None
    assert doc.content == body
    assert doc.kind == "record"
    assert doc.title == "Outage 2026-06-09"


def test_put_with_id_overwrites(store):
    ext_id = store.put("first version")
    store.put("second version", ext_id=ext_id)
    doc = store.get(ext_id)
    assert doc.content == "second version"
    # No duplicate row created.
    assert len(store.list_docs()) == 1


def test_get_unknown_returns_none(store):
    assert store.get("does-not-exist") is None


def test_resolve_ext_id_accepts_unique_prefix(store):
    full = store.put("# Doc\n\nbody")
    assert store.resolve_ext_id(full) == full  # exact
    assert store.resolve_ext_id(full[:8]) == full  # unique short prefix
    assert store.resolve_ext_id(full[:8].upper()) == full  # LIKE is case-insensitive — forgiving
    assert store.resolve_ext_id("zzzzzzzz") is None  # absent
    assert store.resolve_ext_id("") is None


def test_resolve_ext_id_ambiguous_prefix_is_none(store):
    # Two ids sharing a prefix → ambiguous → None (never silently pick one).
    store.put("# A\n\na", ext_id="dupprefix-aaaa")
    store.put("# B\n\nb", ext_id="dupprefix-bbbb")
    assert store.resolve_ext_id("dupprefix-") is None
    assert store.resolve_ext_id("dupprefix-aaaa") == "dupprefix-aaaa"  # full still resolves


def test_replace_section_patches_in_place():
    doc = "# Title\n\nintro\n\n## Standing\n\nold body\n\n## Other\n\nkeep me"
    patched = replace_section(doc, "Standing", "## Standing\n\nNEW body")
    assert patched is not None
    assert "NEW body" in patched
    assert "old body" not in patched
    assert "keep me" in patched  # sibling section untouched
    assert "intro" in patched  # preamble untouched
    # The patched doc still has both headings.
    assert patched.count("## ") == 2


def test_replace_section_missing_heading_returns_none():
    doc = "# Title\n\n## Standing\n\nbody"
    assert replace_section(doc, "Nonexistent", "whatever") is None  # caller MUST hard-error


def test_section_write_roundtrip_preserves_siblings(store):
    body = "# Notes\n\n## Alpha\n\nalpha-one\n\n## Beta\n\nbeta-one"
    ext_id = store.put(body, kind="record")
    # Read a section, edit it, write it back — the data-loss-safe path.
    sec = extract_section(store.get(ext_id).content, "Alpha")
    assert sec == "## Alpha\n\nalpha-one"
    patched = replace_section(store.get(ext_id).content, "Alpha", "## Alpha\n\nalpha-TWO")
    store.put(patched, ext_id=ext_id, kind="record")
    doc = store.get(ext_id)
    assert "alpha-TWO" in doc.content
    assert "beta-one" in doc.content  # the other section survived (no whole-doc clobber)
    assert len(store.list_docs()) == 1  # still one doc


def test_read_by_query_routes_to_right_doc(settings, store):
    """trovex_read's query path: search restricted to source_id='trovex' returns the
    matching doc's ext_id, which the Store resolves to content."""
    auth = store.put("# Auth incident\n\njwt token signature validation failed")
    deploy = store.put("# Deploy rollback\n\nthe kubernetes pod crash looped")

    searcher = Searcher(settings, embedder=BagEmbedder())
    results = searcher.search("jwt token signature", limit=1, source_ids=["trovex"])
    assert results, "expected a trovex-owned match"
    assert results[0].path == auth  # SearchResult.path holds the ext_id
    assert results[0].path != deploy


def test_search_filters_by_kind_and_tags(settings, store):
    """The /api/boot scope path: doc-level search narrows to a kind and/or an owner
    tag, so an agent recalls only its OWN records — not the whole store. Scope first."""
    rec = store.put(
        "# Auth incident\n\njwt token signature failed", kind="record", tags=["owner/alpha"]
    )
    note = store.put(
        "# Auth note\n\njwt token signature failed", tags=["owner/beta"]
    )  # kind None → a normal living doc

    searcher = Searcher(settings, embedder=BagEmbedder())

    # Unscoped: both docs match the query.
    base = searcher.search("jwt token signature", limit=5, source_ids=["trovex"])
    assert {r.path for r in base} == {rec, note}

    # kind filter → only the record.
    by_kind = searcher.search("jwt token signature", limit=5, source_ids=["trovex"], kind="record")
    assert [r.path for r in by_kind] == [rec]

    # tag filter (any-match) → only the alpha-owned doc.
    by_tag = searcher.search(
        "jwt token signature", limit=5, source_ids=["trovex"], tags=["owner/alpha"]
    )
    assert [r.path for r in by_tag] == [rec]

    # kind AND tags are ANDed: record ∧ owner/beta matches neither doc.
    scoped = searcher.search(
        "jwt token signature", limit=5, source_ids=["trovex"], kind="record", tags=["owner/beta"]
    )
    assert scoped == []


def test_boot_pointers_scopes_to_owner_records(settings, store):
    """/api/boot recall: an agent gets ONLY its own records (owner/<agent> +
    kind=record) — not other agents', not non-record docs. Scope first."""
    from trovex.boot import boot_pointers

    store.put(
        "# fullstack state\n\njwt token signature work in flight",
        kind="record",
        tags=["owner/fullstack"],
    )
    store.put("# cmo state\n\njwt token signature current state", kind="record", tags=["owner/cmo"])
    store.put(
        "# fullstack note\n\njwt token signature", tags=["owner/fullstack"]
    )  # owned but NOT a record

    searcher = Searcher(settings, embedder=BagEmbedder())
    boot = boot_pointers(searcher, "fullstack", floor=0.0)

    assert {p["title"] for p in boot["pointers"]} == {"fullstack state"}
    assert boot["render"].startswith("## Resume — fullstack")
    assert boot["tokens_est"] > 0


def test_extract_title_fallbacks():
    """Title derivation is robust to docs that don't lead with an H1 — the bug
    that left ## -led docs as 'Untitled'."""
    from trovex.store import _extract_title

    assert _extract_title("# Real H1\n\nbody") == "Real H1"
    assert _extract_title("## Sub only\n\nbody") == "Sub only"  # H2 → first heading
    assert _extract_title("text first\n\n# Later H1") == "Later H1"  # H1 preferred over a line
    assert _extract_title("---\ntitle: From FM\n---\n\nplain body") == "From FM"  # frontmatter
    assert _extract_title("just a sentence, no heading") == "just a sentence, no heading"
    assert _extract_title("") == "Untitled"
    assert _extract_title("   \n\n  ") == "Untitled"


def test_boot_empty_when_no_owner_records(settings, store):
    """No scoped record → empty pack, zero cost (unknown agent injects nothing)."""
    from trovex.boot import boot_pointers

    store.put("# someone else\n\njwt token signature", kind="record", tags=["owner/other"])
    searcher = Searcher(settings, embedder=BagEmbedder())
    boot = boot_pointers(searcher, "nobody", floor=0.0)

    assert boot["pointers"] == []
    assert boot["render"] == ""
    assert boot["tokens_est"] == 0


def test_capture_then_boot_roundtrip(settings, store):
    """Step 3 → step 2: a free-summary capture upserts owner-<agent>-current-state
    (owner/<agent> + kind=record) and /api/boot then recalls that FRESH record."""
    from trovex.boot import boot_pointers
    from trovex.capture import capture_state

    res = capture_state(
        store,
        "cmo",
        "Shipped /api/capture. Next: distil path. Gotcha: hooks no-op if trovex down.",
        reason="postcompact",
    )
    assert res["captured"] is True
    assert res["doc_id"] == "owner-cmo-current-state"

    # Idempotent: a second capture overwrites in place — one canonical record.
    n_before = len(store.list_docs())
    capture_state(store, "cmo", "Updated current state v2 — distil path landed.")
    assert len(store.list_docs()) == n_before
    assert "v2" in store.get("owner-cmo-current-state").content

    # /api/boot recalls the captured record.
    searcher = Searcher(settings, embedder=BagEmbedder())
    boot = boot_pointers(searcher, "cmo", floor=0.0)
    assert any(p["id"] == "owner-cmo-current-state" for p in boot["pointers"])


def test_capture_rejects_empty(store):
    """No durable signal → no write."""
    from trovex.capture import capture_state

    assert capture_state(store, "cmo", "   ")["captured"] is False
    assert store.get("owner-cmo-current-state") is None


def test_capture_transcript_distil_is_byok_best_effort(store):
    """Step 4 distil is BYOK + best-effort: with no OpenAI key in context the
    distil returns None → a transcript-only capture writes nothing and never
    raises. The free-summary path is unaffected."""
    from trovex.capture import capture_state

    res = capture_state(store, "cmo", "", transcript="x" * 500, reason="sessionend")
    assert res["captured"] is False  # no key → no distil → no write
    assert store.get("owner-cmo-current-state") is None

    res2 = capture_state(store, "cmo", "Durable summary of the session state.", reason="sessionend")
    assert res2["captured"] is True


def test_owner_scope_is_case_insensitive(settings, store):
    """A mixed-case agent name (e.g. 'COO') must recall its own captured record.
    The owner tag is normalised to lower case on both capture and boot, so the
    scope matches the store's lower-cased tags regardless of input case."""
    from trovex.boot import boot_pointers
    from trovex.capture import capture_state

    capture_state(store, "COO", "Durable current-state for the COO agent.", reason="postcompact")
    searcher = Searcher(settings, embedder=BagEmbedder())
    boot = boot_pointers(searcher, "COO", floor=0.0)
    assert any("current-state" in p["id"] for p in boot["pointers"])


def test_record_not_stale_by_age(settings, store):
    """A record stays canonical no matter how old; a non-record goes stale."""
    rec = store.put("# Old incident", kind="record")
    living = store.put("# Old note")  # kind is None → a normal living doc

    old = time.time() - settings.stale_age_days * 86400 - 86400  # past the cutoff
    store.db.execute("UPDATE docs SET mtime = ?", (old,))
    store.db.commit()

    compute_status(store.db, settings)

    assert store.get(rec).status == "canonical"
    assert store.get(living).status == "stale"


def test_indexer_does_not_purge_trovex_docs(settings, store, tmp_path):
    """The filesystem indexer must never delete trovex-owned docs (they have no
    file on disk). It only touches the source it scans."""
    ext_id = store.put("# Survives reindex", kind="record")

    empty_source = tmp_path / "repo"
    empty_source.mkdir()
    indexer = Indexer(settings, embedder=BagEmbedder())
    indexer.reindex(sources=[Source(id="code", label="repo", root=empty_source)])

    assert store.get(ext_id) is not None


def test_extract_section():
    doc = "# Title\n\nintro\n\n## Alpha\n\naaa\n\n## Beta\n\nbbb\n\n### Beta sub\n\nccc\n"
    assert extract_section(doc, "Alpha") == "## Alpha\n\naaa"
    beta = extract_section(doc, "Beta")
    assert "bbb" in beta and "ccc" in beta  # keeps its deeper ### subheading
    assert "aaa" not in beta
    assert extract_section(doc, "Nonexistent") is None


def test_collections_save_list_get_delete(store):
    store.put("# A", kind="record", tags=["x"])
    store.create_collection("recs", {"kind": "record", "tag": "x"})
    cols = {c["name"]: c["filter"] for c in store.list_collections()}
    assert cols["recs"] == {"kind": "record", "tag": "x"}
    assert store.get_collection("recs") == {"kind": "record", "tag": "x"}
    store.delete_collection("recs")
    assert store.get_collection("recs") is None


def test_tags_write_auto_filter_and_edit(store):
    a = store.put("# A\n\nalpha content", kind="record", tags=["auth", "team/sec"])
    store.put("# B\n\nbeta content", kind="note", tags=["billing"])
    da = store.get(a)
    assert "auth" in da.tags and "team/sec" in da.tags and "kind/record" in da.tags
    # filter list by tag
    assert [d.ext_id for d in store.list_docs(tag="auth")] == [a]
    # add/remove
    store.set_tags(a, add=["urgent"], remove=["auth"])
    da2 = store.get(a)
    assert "urgent" in da2.tags and "auth" not in da2.tags
    # all_tags reflects counts
    tags = dict(store.all_tags())
    assert tags.get("billing") == 1 and tags.get("urgent") == 1
    # tag-filtered chunk search excludes the now-untagged doc
    hits = store.search_chunks("alpha content", limit=5, tags=["billing"])
    assert all(h["ext_id"] != a for h in hits)


def test_chunk_indexing_and_search(store):
    store.put(
        "# Auth\n\n## JWT\n\njwt token signature validation\n\n"
        "## Deploy\n\nkubernetes pod rollout strategy",
        kind="reference",
    )
    store.put("# Billing\n\n## Invoices\n\nstripe invoice webhook handling", kind="reference")
    hits = store.search_chunks("jwt token signature", limit=1)
    assert hits, "expected a chunk hit"
    assert "jwt token signature" in hits[0]["content"]
    assert hits[0]["heading_path"] == "Auth > JWT"


def test_versioning_snapshots_and_restores(store):
    eid = store.put("# v1\n\nfirst content")
    store.put("# v2\n\nsecond content", ext_id=eid)  # overwrite snapshots v1
    versions = store.list_versions(eid)
    assert len(versions) == 1
    assert store.get(eid).content == "# v2\n\nsecond content"
    # restore v1 (which snapshots the current v2 first)
    assert store.restore_version(eid, versions[0]["id"]) is True
    assert store.get(eid).content == "# v1\n\nfirst content"
    assert len(store.list_versions(eid)) == 2


def test_delete_removes_chunks_too(store):
    eid = store.put("# Temp\n\n## S\n\nuniquechunkword here")
    assert store.search_chunks("uniquechunkword", limit=1)
    store.delete(eid)
    assert store.search_chunks("uniquechunkword", limit=5) == []


def test_delete_removes_doc_and_embedding(store):
    eid = store.put("# temp doc\n\nbody")
    assert store.get(eid) is not None
    assert store.delete(eid) is True
    assert store.get(eid) is None
    # gone from the search index too (no ghost result)
    from trovex.search import Searcher

    searcher = Searcher(store.settings, embedder=BagEmbedder())
    assert searcher.search("temp doc", limit=5, source_ids=["trovex"]) == []
    # idempotent: deleting again reports not-found
    assert store.delete(eid) is False


def test_update_is_write_with_same_id(store):
    eid = store.put("# v1\n\nfirst")
    store.put("# v2\n\nsecond", ext_id=eid)  # "update" = write with same id
    assert store.get(eid).content == "# v2\n\nsecond"
    assert len(store.list_docs()) == 1


def test_concurrent_puts_are_serialized(store):
    def write(i):
        return store.put(f"# Doc {i}\n\nbody {i}", ext_id=f"id-{i}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        ids = list(ex.map(write, range(20)))

    assert len(set(ids)) == 20
    assert len(store.list_docs()) == 20
    assert store.get("id-7").content == "# Doc 7\n\nbody 7"
