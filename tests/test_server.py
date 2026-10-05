"""HTTP route tests for the Active-Memory surface (RFC 330e7d43).

Store-level scope/recall is covered in test_store.py; this exercises the FastAPI
routes that wrap it — /api/search (kind/tags query params) and /api/boot
(owner+kind scope, mixed-case agent recall). Hermetic: the deterministic
BagEmbedder, an in-memory-ish tmp store, and a TestClient WITHOUT a lifespan
context (so the /mcp session manager is never started — these routes don't need
it, and get_state() returns the injected test state per request).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from trovex import state as state_mod
from trovex.config import Settings
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.server import build_app
from trovex.state import AppState
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
def client(tmp_path):
    """A TestClient backed by a known corpus, with the app's global state injected.

    Corpus is written BEFORE the searcher is built so every connection sees it.
    The trailing reset_state() keeps the process-wide singleton from leaking into
    other tests.
    """
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",  # dim 384, matches BagEmbedder
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    embedder = BagEmbedder()
    store = SqliteStore(settings, embedder=embedder)

    # owner/alpha record + owner/beta living doc → kind/tag scope can separate them.
    store.put(
        "# Auth incident\n\ncurrent state resume open work in flight next steps gotchas",
        kind="record",
        tags=["owner/alpha"],
    )
    store.put(
        "# Auth note\n\ncurrent state resume open work in flight next steps gotchas",
        tags=["owner/beta"],
    )
    # A record owned by a MIXED-CASE agent. Tags are stored lower-cased
    # (owner/coo); /api/boot must lower-case the queried agent to match it.
    store.put(
        "# COO handoff\n\ncurrent state resume open work in flight next steps gotchas",
        kind="record",
        tags=["owner/coo"],
    )

    searcher = Searcher(settings, embedder=embedder)
    indexer = Indexer(settings, embedder=embedder)
    state_mod._state = AppState(
        settings=settings,
        embedder=embedder,
        searcher=searcher,
        indexer=indexer,
        store=store,
    )
    try:
        yield TestClient(build_app())
    finally:
        state_mod.reset_state()


@pytest.fixture(autouse=True)
def _generous_boot_deadline(monkeypatch):
    """The 2.5s offload deadline is a PROD load-shed knob; a slow/contended CI
    host must not turn it into a false 'empty recall'. Correctness tests assert
    recall, not host speed — so give boot a generous deadline here. The prod
    default (server._BOOT_OFFLOAD_TIMEOUT_SEC) is unchanged (ticket 7df08701)."""
    from trovex import server as _server_mod

    monkeypatch.setattr(_server_mod, "_BOOT_OFFLOAD_TIMEOUT_SEC", 30.0)


def test_api_search_scopes_by_kind_and_tags(client):
    """/api/search threads kind + (comma-separated) tags into the store scope."""
    q = "current state resume work"

    # No scope → both auth docs come back.
    base = client.get("/api/search", params={"q": q, "limit": 5}).json()
    titles = {r["title"] for r in base}
    assert "Auth incident" in titles and "Auth note" in titles

    # kind=record → drops the living (kind-less) note.
    by_kind = client.get("/api/search", params={"q": q, "limit": 5, "kind": "record"}).json()
    kind_titles = {r["title"] for r in by_kind}
    assert "Auth note" not in kind_titles
    assert "Auth incident" in kind_titles

    # tags scope (any-match) → only the alpha-owned doc.
    by_tag = client.get("/api/search", params={"q": q, "limit": 5, "tags": "owner/alpha"}).json()
    assert [r["title"] for r in by_tag] == ["Auth incident"]


def test_api_boot_recalls_mixed_case_owner(client):
    """Regression for the silent mixed-case bug: GET /api/boot?agent=COO must
    recall the owner/coo record (tags are stored lower-cased)."""
    upper = client.get("/api/boot", params={"agent": "COO", "floor": 0.0}).json()
    assert upper["agent"] == "COO"
    assert [p["title"] for p in upper["pointers"]] == ["COO handoff"]
    assert upper["tokens_est"] > 0


def test_api_boot_budget_receipt_header_and_query_log(client):
    response = client.get(
        "/api/boot", params={"agent": "coo", "floor": 0.0, "budget": 200}
    )
    out = response.json()

    assert response.headers["X-Trovex-Budget-Used"] == str(out["budget_used"])
    assert out["budget_requested"] == 200
    assert sum(pointer["tokens_est"] for pointer in out["pointers"]) == out["budget_used"]
    assert all(set(item) == {"doc_id", "tier"} for item in out["trimmed"])
    row = state_mod._state.store.db.execute(
        "SELECT budget_requested, budget_used FROM mcp_queries ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert dict(row) == {"budget_requested": 200, "budget_used": out["budget_used"]}


def test_api_boot_and_search_200_over_4096_docs(client):
    """OUTAGE regression at the HTTP surface: once the corpus crossed sqlite-vec's
    4096 KNN ceiling, the widen-retry issued a k>4096 MATCH that raised and
    /api/boot 500'd for the whole fleet. P2a retires the ceiling structurally —
    source_id partitions the vec0 shards, so 4100 docs live in a bounded 'code'
    shard the owner-scoped boot never scans. Both routes must return 200."""
    import sqlite_vec

    store = state_mod._state.store
    emb = next(iter(store.embedder.embed(["reverse proxy tls nginx seed"]))).tolist()
    blob = sqlite_vec.serialize_float32(emb)
    now = 1_600_000_000.0
    # 4100 docs in the 'code' partition (source_id='code', no kind) → never matches
    # the owner boot scope, so the boot query stays scoped to the small trovex shard.
    store.db.executemany(
        """INSERT INTO docs
             (source_id, path, absolute_path, content_hash, size_bytes,
              tokens_est, mtime, first_indexed, last_indexed, title)
           VALUES ('code', ?, ?, ?, 10, 3, ?, ?, ?, ?)""",
        [(f"seed/{i}.md", f"/seed/{i}.md", f"h{i}", now, now, now, f"seed {i}") for i in range(4100)],
    )
    ids = [r["id"] for r in store.db.execute("SELECT id FROM docs WHERE path LIKE 'seed/%'")]
    # Partitioned vec_docs: 'code' shard, metadata from the docs defaults.
    store.db.executemany(
        "INSERT INTO vec_docs(rowid, source_id, embedding, kind, lifecycle, status, embed_model) "
        "VALUES (?, 'code', ?, 'doc', 'active', 'canonical', 'test')",
        [(i, blob) for i in ids],
    )
    store.db.commit()
    assert store.db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"] > 4096

    boot = client.get("/api/boot", params={"agent": "nobody"})
    assert boot.status_code == 200
    search = client.get("/api/search", params={"q": "reverse proxy tls nginx", "limit": 5})
    assert search.status_code == 200

    # The already-lower-case spelling resolves to the same record.
    lower = client.get("/api/boot", params={"agent": "coo", "floor": 0.0}).json()
    assert [p["title"] for p in lower["pointers"]] == ["COO handoff"]


def test_api_boot_unknown_agent_is_empty(client):
    """An agent with no records injects nothing — even at floor 0 it's scope, not
    score, that excludes it (zero-cost boot for an unknown session)."""
    out = client.get("/api/boot", params={"agent": "nobody", "floor": 0.0}).json()
    assert out["pointers"] == []
    assert out["tokens_est"] == 0


def test_api_boot_truncates_long_query_instead_of_rejecting(client):
    """Regression: the prompt hook passes the WHOLE user prompt as q=, and long
    agent preambles used to 422 — a silently-dropped recall, since the hook
    swallows the error. Over-long queries must truncate and still recall."""
    from trovex.boot import BOOT_Q_MAX

    long_q = "COO handoff current state " + ("filler padding text " * 3000)
    assert len(long_q) > BOOT_Q_MAX * 10

    resp = client.get("/api/boot", params={"agent": "coo", "floor": 0.0, "q": long_q})
    assert resp.status_code == 200
    assert [p["title"] for p in resp.json()["pointers"]] == ["COO handoff"]


def test_api_boot_owner_scope_excludes_other_owners(client):
    """Boot is owner-scoped: alpha never sees beta's or coo's records."""
    out = client.get("/api/boot", params={"agent": "alpha", "floor": 0.0}).json()
    titles = {p["title"] for p in out["pointers"]}
    assert titles == {"Auth incident"}


def test_api_boot_logs_one_query_row_with_served_ids(client):
    """task 2b7974cf: a SessionStart-style boot call (no q=) logs exactly one
    mcp_queries row with source='boot' and its served pointer ids into
    mcp_query_results — the replay eval's blind spot before this landed."""
    db = state_mod._state.store.db

    before = db.execute("SELECT COUNT(*) AS c FROM mcp_queries WHERE source='boot'").fetchone()["c"]
    out = client.get("/api/boot", params={"agent": "coo", "floor": 0.0}).json()
    after = db.execute("SELECT COUNT(*) AS c FROM mcp_queries WHERE source='boot'").fetchone()["c"]
    assert after == before + 1

    row = db.execute(
        "SELECT id, session_id, user FROM mcp_queries WHERE source='boot' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["session_id"] == "coo"  # the agent name, not an MCP transport session
    assert row["user"] == "coo"
    served = [
        r["path"] for r in db.execute(
            "SELECT path FROM mcp_query_results WHERE query_id = ? ORDER BY rank", (row["id"],)
        )
    ]
    assert served == [p["id"] for p in out["pointers"]]
    assert served  # this fixture's coo record clears scope+floor


def test_api_boot_logs_source_prompt_when_q_given(client):
    """The UserPromptSubmit hook (trovex-prompt.sh) passes q=<prompt> — that same
    /api/boot call must log source='prompt', not 'boot', so --replay can tell
    hook-driven prompt recall apart from a plain session start."""
    db = state_mod._state.store.db
    client.get("/api/boot", params={"agent": "coo", "floor": 0.0, "q": "current state resume"})
    row = db.execute(
        "SELECT source FROM mcp_queries ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["source"] == "prompt"


def test_api_boot_empty_pointers_still_logs_a_row(client):
    """An unknown agent's boot call is a real (zero-result) traffic event — it
    must still show up in the replay eval's n, not vanish silently."""
    db = state_mod._state.store.db
    before = db.execute("SELECT COUNT(*) AS c FROM mcp_queries").fetchone()["c"]
    client.get("/api/boot", params={"agent": "nobody", "floor": 0.0})
    after = db.execute("SELECT COUNT(*) AS c FROM mcp_queries").fetchone()["c"]
    assert after == before + 1
    row = db.execute("SELECT n_results FROM mcp_queries ORDER BY id DESC LIMIT 1").fetchone()
    assert row["n_results"] == 0


def test_search_page_renders_states(client):
    """The /search surface ships all four UX states. Empty (no query) prompts; a real
    query renders the result list; and the page wires the error-state template + the
    htmx error handlers so a failed /search/partial isn't a silent freeze."""
    empty = client.get("/search")
    assert empty.status_code == 200
    assert "type a query to search" in empty.text  # empty/no-query state

    hit = client.get("/search", params={"q": "current state work in flight"})
    assert hit.status_code == 200
    assert "result-list" in hit.text and "Auth incident" in hit.text  # results state

    # Error state: the template + the three htmx error hooks must be present so a
    # non-2xx / dropped /search/partial swaps in a retry instead of freezing.
    assert 'id="search-error-tpl"' in empty.text
    assert "htmx:responseError" in empty.text
    assert "htmx:sendError" in empty.text


def test_search_partial_renders_no_results_state(client):
    """A scope that excludes every doc renders the no-results empty state (not a 500).
    (knn has no score floor, so a gibberish query still returns top-k — emptiness comes
    from a filter that matches nothing, here kind=note with no note docs indexed.)"""
    res = client.get("/search/partial", params={"q": "current state", "kind": "note"})
    assert res.status_code == 200
    assert "no results" in res.text


def test_api_search_scopes_by_source(client):
    """A project must be able to restrict retrieval to its own source. Without
    this, an agent on a 14-doc project searches all 2800 docs in the store and
    gets buried by whichever project is biggest."""
    q = "current state resume work"

    unscoped = client.get("/api/search", params={"q": q, "limit": 5}).json()
    assert len(unscoped) > 0

    # The fixture's docs are all trovex-owned; 'code' is the configured file
    # source and holds nothing.
    owned = client.get("/api/search", params={"q": q, "limit": 5, "source": "trovex"}).json()
    assert {r["source_id"] for r in owned} == {"trovex"}
    assert len(owned) == len(unscoped)

    empty = client.get("/api/search", params={"q": q, "limit": 5, "source": "code"}).json()
    assert empty == []


def test_api_search_rejects_unknown_source(client):
    """A typo'd source must fail loudly. Silently filtering everything away
    would read as 'trovex found nothing' and send the caller debugging the
    wrong thing."""
    r = client.get("/api/search", params={"q": "anything", "source": "nope"})
    assert r.status_code == 422
    assert "unknown source" in r.json()["error"]


# ── /api/graph — the knowledge-graph projection for the /graph SPA ──────────


def _seed_link_graph(store):
    """A tiny lineage: a canonical decision that SUPERSEDES an older one and is
    DECIDED-IN a note, plus a code file (classified by its .py path) and one
    real agent read. Returns the path we recorded a read against."""
    # Create every node first (a link target must already exist), then wire the
    # typed edges from dec-new.
    store.put("# Old decision\n\npick postgres", kind="decision", ext_id="dec-old")
    store.put("# New decision\n\npick sqlite after all", kind="decision", ext_id="dec-new")
    store.put("# Design note\n\nwhy sqlite", kind=None, ext_id="note-c")
    for rel, tgt in (("supersedes", "dec-old"), ("decided-in", "note-c")):
        store.db.execute(
            """INSERT INTO doc_links (src_doc_id, rel, dst_doc_id, created_at, created_by)
               SELECT s.id, ?, d.id, ?, 'test'
               FROM docs s, docs d WHERE s.ext_id='dec-new' AND d.ext_id=?""",
            (rel, time.time(), tgt),
        )
    # A code file node — classification is by the .py path extension.
    store.put("# module\n\ncode", kind=None, ext_id="code-x")
    store.db.execute("UPDATE docs SET path='src/trovex/graphview.py' WHERE ext_id='code-x'")
    # Canonical/superseded statuses so the status lens has something to show.
    store.db.execute("UPDATE docs SET status='canonical' WHERE ext_id='dec-new'")
    store.db.execute("UPDATE docs SET status='superseded' WHERE ext_id='dec-old'")
    # One real agent read against dec-new's path within the 7d window.
    read_path = store.db.execute("SELECT path FROM docs WHERE ext_id='dec-new'").fetchone()["path"]
    cur = store.db.execute(
        "INSERT INTO mcp_queries (ts, query) VALUES (?, ?)", (time.time(), "why sqlite")
    )
    store.db.execute(
        "INSERT INTO mcp_query_results (query_id, rank, path, used) VALUES (?, 0, ?, 1)",
        (cur.lastrowid, read_path),
    )
    store.db.commit()
    return read_path


def test_api_graph_returns_nodes_edges_with_fields(client):
    """Core contract: nodes carry kind/status/reads_7d/drift; typed doc_links
    come back as edges; the .py doc is classified as a code node."""
    store = state_mod._state.store
    _seed_link_graph(store)

    out = client.get("/api/graph").json()
    nodes = {n["title"]: n for n in out["nodes"]}

    assert "New decision" in nodes
    nd = nodes["New decision"]
    # every contracted field is present on every node
    for key in ("id", "title", "path", "kind", "status", "reads_7d", "drift"):
        assert key in nd
    assert nd["kind"] == "decision"
    assert nd["status"] == "canonical"
    assert nd["reads_7d"] >= 1  # the real read we recorded
    assert nd["drift"] == 0  # L5 drift column not on dev → defaults to 0

    # the .py doc is a code node; the old decision kept its decision kind
    assert nodes["module"]["kind"] == "code"
    assert nodes["Old decision"]["kind"] == "decision"

    # the supersedes lineage edge is present and typed
    by_id = {n["id"]: n["title"] for n in out["nodes"]}
    sup = [
        e for e in out["edges"]
        if e["kind"] == "supersedes"
        and by_id.get(e["src"]) == "New decision"
        and by_id.get(e["dst"]) == "Old decision"
    ]
    assert len(sup) == 1


def test_api_graph_focus_depth_limits_neighbourhood(client):
    """focus+depth restrict the result to the k-hop neighbourhood of a node."""
    store = state_mod._state.store
    _seed_link_graph(store)

    d0 = client.get("/api/graph", params={"focus": "dec-new", "depth": 0}).json()
    assert [n["title"] for n in d0["nodes"]] == ["New decision"]
    assert d0["edges"] == []

    d1 = client.get("/api/graph", params={"focus": "dec-new", "depth": 1}).json()
    titles = {n["title"] for n in d1["nodes"]}
    # one hop out reaches both direct neighbours, and nothing unrelated
    assert titles == {"New decision", "Old decision", "Design note"}

    missing = client.get("/api/graph", params={"focus": "no-such-node"}).json()
    assert missing["nodes"] == [] and missing["edges"] == []


def test_api_graph_bad_params_422(client):
    assert client.get("/api/graph", params={"depth": -1}).status_code == 422
    assert client.get("/api/graph", params={"depth": 99}).status_code == 422
    assert client.get("/api/graph", params={"source": "bad source!"}).status_code == 422


def test_api_graph_node_detail_renders_and_lists_links(client):
    """The side-panel endpoint renders the doc and lists in/out links w/ context."""
    store = state_mod._state.store
    _seed_link_graph(store)

    detail = client.get("/api/graph/node/dec-new").json()
    assert detail["title"] == "New decision"
    assert "<" in detail["html"]  # markdown rendered to HTML
    out_rels = {(x["rel"], x["title"]) for x in detail["out_links"]}
    assert ("supersedes", "Old decision") in out_rels
    assert ("decided-in", "Design note") in out_rels

    # dec-old is on the receiving end of the supersedes edge
    back = client.get("/api/graph/node/dec-old").json()
    assert ("supersedes", "New decision") in {(x["rel"], x["title"]) for x in back["in_links"]}

    assert client.get("/api/graph/node/does-not-exist").status_code == 404


def test_graph_mount_is_404_safe_when_dist_missing(client, tmp_path, monkeypatch):
    """Like /receipt: with no web/dist-graph build, the app still boots and the
    route is simply absent (404) — never a 500, and the API still serves.
    Hermetic: point GRAPH_DIST at a path that does not exist, regardless of
    whether a real build happens to be sitting in the tree. (`client` injects
    the app state the routes read.)"""
    from trovex.server import build_app

    monkeypatch.setattr("trovex.server.GRAPH_DIST", tmp_path / "no-such-dist-graph")
    app = TestClient(build_app())
    assert app.get("/graph/").status_code == 404
    assert app.get("/api/graph").status_code == 200


def test_graph_mount_serves_spa_when_built(tmp_path, monkeypatch, client):
    """When the build exists, /graph serves the SPA index (html=True fallback)."""
    from trovex.server import build_app

    dist = tmp_path / "dist-graph"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>graph spa</title>", encoding="utf-8")
    monkeypatch.setattr("trovex.server.GRAPH_DIST", dist)

    built = TestClient(build_app())
    r = built.get("/graph/")
    assert r.status_code == 200
    assert "graph spa" in r.text


def test_api_graph_coread_backbone(client):
    """Docs pulled into the SAME agent query twice earn a faint 'co-read' edge —
    the agent-usage backbone that turns a sparse link cloud into communities."""
    store = state_mod._state.store
    store.put("# Alpha\n\none", ext_id="co-a")
    store.put("# Beta\n\ntwo", ext_id="co-b")
    pa = store.db.execute("SELECT path FROM docs WHERE ext_id='co-a'").fetchone()["path"]
    pb = store.db.execute("SELECT path FROM docs WHERE ext_id='co-b'").fetchone()["path"]
    # the pair is co-retrieved in two separate queries → weight 2 (>= threshold)
    for _ in range(2):
        cur = store.db.execute("INSERT INTO mcp_queries (ts, query) VALUES (?, 'q')", (time.time(),))
        qid = cur.lastrowid
        store.db.execute("INSERT INTO mcp_query_results (query_id, rank, path) VALUES (?, 0, ?)", (qid, pa))
        store.db.execute("INSERT INTO mcp_query_results (query_id, rank, path) VALUES (?, 1, ?)", (qid, pb))
    store.db.commit()

    out = client.get("/api/graph").json()
    by_id = {n["id"]: n["title"] for n in out["nodes"]}
    coread = [
        e for e in out["edges"]
        if e["kind"] == "co-read"
        and {by_id.get(e["src"]), by_id.get(e["dst"])} == {"Alpha", "Beta"}
    ]
    assert len(coread) == 1
    assert coread[0]["weight"] == 2


def test_doc_view_shows_backlinks_panel(client):
    """The Jinja doc page renders its typed doc_links: out-links on the newer
    doc, backlinks on the one it superseded."""
    store = state_mod._state.store
    old = store.put("# Old choice\n\nx", kind="decision", ext_id="bl-old")
    new = store.put(
        "# New choice\n\ny", kind="decision", ext_id="bl-new",
        links=[{"rel": "supersedes", "target": "bl-old"}],
    )

    newer = client.get(f"/doc/{new}").text
    assert "doc-backlinks" in newer
    assert "supersedes" in newer and "Old choice" in newer

    older = client.get(f"/doc/{old}").text
    assert "Backlinks" in older and "New choice" in older


# ── incident 35c0631e: served-empty-store (frozen snapshot) ──────────────────


def test_log_pointer_query_rolls_back_stuck_txn_on_error(client):
    """Root-cause regression (incident 35c0631e): a malformed pointer makes
    log_pointer_query raise AFTER its mcp_queries INSERT has already opened a
    write transaction. The except MUST roll back — otherwise the long-lived
    served connection is stuck in an open write txn, which freezes every later
    read to a stale snapshot (/api/stats served 0 on a 4.7k-doc store) and holds
    the WAL write lock so the separate reindex writer is locked out and the WAL
    can never checkpoint."""
    from trovex.usage import log_pointer_query

    db = state_mod._state.searcher.db
    before = db.execute("SELECT COUNT(*) FROM mcp_queries").fetchone()[0]

    # pointer dict missing "id" -> the executemany list-comp raises KeyError
    # AFTER the mcp_queries INSERT opened the write txn.
    log_pointer_query(
        db,
        source="boot",
        agent="probe",
        query="q",
        pointers=[{"score": 1.0}],
        tokens_est=0,
        elapsed_ms=1,
    )

    # fix: the half-open write txn was released, not left dangling
    assert db.in_transaction is False
    # the failed INSERT was rolled back, not silently committed
    assert db.execute("SELECT COUNT(*) FROM mcp_queries").fetchone()[0] == before

    # and the WAL write lock is free: a separate writer is not locked out
    other = sqlite3.connect(str(state_mod._state.settings.data_dir / "trovex.db"))
    other.execute("PRAGMA busy_timeout=1500")
    try:
        other.execute("CREATE TABLE IF NOT EXISTS _healthz_probe(x)")
        other.execute("INSERT INTO _healthz_probe(x) VALUES (1)")
        other.commit()  # pre-fix this raises sqlite3.OperationalError: database is locked
    finally:
        other.close()


def test_healthz_ok_when_store_populated(client):
    # a fresh refresh on the populated fixture store clears the flag
    from trovex.server import _refresh_health

    _refresh_health(state_mod._state)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_healthz_is_loop_only_reads_flag_not_db(client, monkeypatch):
    """Audit Q9: /healthz must NOT touch the DB or the offload pool on the probe
    path — it reads the background-refreshed flag only. Prove it: a served
    connection that raises on every execute does not affect /healthz."""
    class _BoomDB:
        def execute(self, *a, **k):
            raise AssertionError("/healthz must not query the DB on the probe path")

    monkeypatch.setattr(state_mod._state.searcher, "db", _BoomDB())
    resp = client.get("/healthz")  # reads state.health (default healthy), no db
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_healthz_503_when_served_empty_but_db_populated(client):
    """A frozen/stale served connection that reads 0 docs while the DB file on
    disk holds rows must make /healthz fail LOUD (503), so the monitor restarts
    us instead of silently handing every agent an empty context (incident
    35c0631e). The flag is set by the BACKGROUND refresher (_refresh_health),
    which cross-checks the file through a FRESH connection so a stale server
    can't vouch for itself; /healthz then just reads the flag."""
    from trovex.server import _refresh_health

    # the real tmp DB file has the fixture's docs; swap the SERVED connection for
    # an empty one to mimic the frozen 0-row snapshot, then refresh the flag.
    empty = sqlite3.connect(":memory:")
    empty.row_factory = sqlite3.Row
    empty.execute("CREATE TABLE docs(id INTEGER PRIMARY KEY)")  # 0 rows
    state_mod._state.searcher.db = empty
    _refresh_health(state_mod._state)

    resp = client.get("/healthz")
    assert resp.status_code == 503
    assert "stale store" in resp.text


# ── b02389c2 AC1: /api/boot load-shed (audit Q5) ─────────────────────────────


def test_api_boot_sheds_when_pool_saturated(client, monkeypatch):
    """When the offload pool is saturated, /api/boot returns the empty pack (200)
    immediately and never submits a recall — a burst must not pile onto a full
    pool and orphan workers (audit Q5)."""
    import trovex.offload as off

    monkeypatch.setattr(off, "pool_saturated", lambda: True)

    async def _boom(*a, **k):
        raise AssertionError("shed path must not submit to the offload pool")

    monkeypatch.setattr(off, "off_loop", _boom)
    resp = client.get("/api/boot", params={"agent": "coo", "floor": 0.0})
    assert resp.status_code == 200
    assert resp.json()["pointers"] == []


def test_api_boot_sheds_when_client_disconnected(client, monkeypatch):
    """A client that already gave up (the prompt hook abandons at ~2s) must not
    cost a recall: /api/boot sheds to the empty pack (200) without hitting the
    pool (audit Q5)."""
    import trovex.offload as off
    from starlette.requests import Request

    async def _disconnected(self):
        return True

    monkeypatch.setattr(off, "pool_saturated", lambda: False)
    monkeypatch.setattr(Request, "is_disconnected", _disconnected)

    async def _boom(*a, **k):
        raise AssertionError("disconnected client must not trigger a recall")

    monkeypatch.setattr(off, "off_loop", _boom)
    resp = client.get("/api/boot", params={"agent": "coo", "floor": 0.0})
    assert resp.status_code == 200
    assert resp.json()["pointers"] == []


# ── b02389c2 AC2: background query-log writer (audit Q6) ──────────────────────


def test_query_log_writer_writes_enqueued_rows(client):
    """The background writer drains enqueued rows on its OWN connection and
    commits them (task b02389c2 AC2)."""
    import trovex.usage as usage

    db = state_mod._state.store.db
    before = db.execute("SELECT COUNT(*) FROM mcp_queries").fetchone()[0]
    usage.start_query_log_writer(state_mod._state.settings.data_dir)
    try:
        usage.enqueue_pointer_query(
            db, source="boot", agent="coo", query="q",
            pointers=[{"id": "x", "score": 1.0}], tokens_est=5, elapsed_ms=1,
        )
        for _ in range(100):  # wait for the writer thread to drain + commit
            if db.execute("SELECT COUNT(*) FROM mcp_queries").fetchone()[0] > before:
                break
            time.sleep(0.05)
    finally:
        usage.stop_query_log_writer()
    assert db.execute("SELECT COUNT(*) FROM mcp_queries").fetchone()[0] == before + 1


def test_api_boot_enqueues_log_no_synchronous_write(client, monkeypatch):
    """AC2: /api/boot does ZERO synchronous log writes on the request path — it
    enqueues to the running background writer, so log_pointer_query (the sync
    fallback) is never called from the handler."""
    import trovex.usage as usage

    sync = {"n": 0}
    monkeypatch.setattr(usage, "log_pointer_query", lambda *a, **k: sync.__setitem__("n", sync["n"] + 1))
    usage.start_query_log_writer(state_mod._state.settings.data_dir)
    try:
        resp = client.get("/api/boot", params={"agent": "coo", "floor": 0.0})
        assert resp.status_code == 200
    finally:
        usage.stop_query_log_writer()
    assert sync["n"] == 0  # enqueued, not written synchronously


# ---------------------------------------------------------------------------
# ticket 7df08701: /api/boot must NEVER return a silently empty pack under
# contention. Corrected root cause (investigated, repro'd): the real trigger is
# the offload wall-deadline (server._BOOT_OFFLOAD_TIMEOUT_SEC, blown under CPU
# starvation -> TimeoutError -> empty pack in api_boot). The OperationalError
# swallow in boot.boot_pointers is a second, latent silent-empty path. The
# shared-connection race was investigated and did NOT reproduce (sqlite3's
# per-connection mutex serialises reads+writes). Both empty paths must carry a
# `degraded` flag naming which path, so the prompt hook can tell "no records"
# from "recall shed".
# ---------------------------------------------------------------------------


class _RaisingSearcher:
    """Searcher stand-in whose .search raises a chosen exception — the
    deterministic seam for boot_pointers' degraded-path contract."""

    def __init__(self, exc):
        self._exc = exc
        self.db = None  # never reached: search raises before the budget path

    def search(self, *a, **k):
        raise self._exc


def test_boot_pointers_flags_transient_sqlite_error_not_silent():
    """A transient (lock/busy) sqlite OperationalError during boot search must
    surface as a degraded='sqlite' pack, never an unflagged empty one."""
    from trovex.boot import boot_pointers

    pack = boot_pointers(
        _RaisingSearcher(sqlite3.OperationalError("database is locked")),
        "coo",
        floor=0.0,
    )
    assert pack["pointers"] == []
    assert pack["degraded"] == "sqlite"


def test_boot_pointers_flags_vec_ceiling_distinctly():
    """The genuine sqlite-vec KNN ceiling is a bounded empty flagged 'ceiling',
    distinct from a transient — so the narrow except is not widened to pass a
    transient off as a ceiling."""
    from trovex.boot import boot_pointers

    ceiling = sqlite3.OperationalError(
        "k value in knn query too large, provided 5000 and the limit is 4096"
    )
    pack = boot_pointers(_RaisingSearcher(ceiling), "coo", floor=0.0)
    assert pack["pointers"] == []
    assert pack["degraded"] == "ceiling"


def test_boot_healthy_recall_is_not_degraded(client):
    """A normal recall carries degraded=None — the flag is always in the schema."""
    out = client.get("/api/boot", params={"agent": "coo", "floor": 0.0}).json()
    assert [p["title"] for p in out["pointers"]] == ["COO handoff"]
    assert out["degraded"] is None


def test_api_boot_timeout_is_flagged_not_silent(client, monkeypatch):
    """REAL trigger: the offload deadline blown under load -> TimeoutError.
    api_boot must return 200 with degraded='timeout', never a silent empty pack
    the prompt hook can't distinguish from 'no records'."""
    from trovex import server as server_mod

    async def _boom(*a, **k):
        raise TimeoutError

    monkeypatch.setattr(server_mod.offload, "off_loop", _boom)
    resp = client.get("/api/boot", params={"agent": "coo", "floor": 0.0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["pointers"] == []
    assert body["degraded"] == "timeout"


def test_api_boot_concurrent_recall_never_silent_empty(client):
    """AC3 guard: hammer /api/boot concurrently; every response either recalls
    the COO record or is explicitly flagged degraded — never a silent empty."""
    import threading

    results = []
    lock = threading.Lock()

    def hit():
        body = client.get("/api/boot", params={"agent": "coo", "floor": 0.0}).json()
        with lock:
            results.append(body)

    threads = [threading.Thread(target=hit) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 16
    for body in results:
        recalled = [p["title"] for p in body["pointers"]] == ["COO handoff"]
        assert recalled or body["degraded"] is not None, body
