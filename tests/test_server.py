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


# ---------------------------------------------------------------------------
# perf A (task 62c53f35): query-embed cost + deploy priority + warm-up + usearch
# ---------------------------------------------------------------------------
import pathlib  # noqa: E402
from typing import ClassVar  # noqa: E402

from trovex import server as server_mod  # noqa: E402
from trovex.boot import BOOT_Q_MAX, clean_query  # noqa: E402
from trovex.embedder import (  # noqa: E402
    Int8QueryEmbedder,
    query_embedder_from_settings,
)

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_clean_query_caps_at_500():
    """AC2: the embedded query is capped to ~400-500 chars, not the old 2000
    (512 tokens = the model max = the slowest possible forward pass)."""
    assert BOOT_Q_MAX <= 500
    out = clean_query("x " * 5000)
    assert len(out) <= BOOT_Q_MAX


def test_clean_query_strips_boilerplate_keeps_signal():
    """AC2: harness boilerplate (task-notification XML, 'You are **name**' preamble,
    'check your relay' nudge) is stripped so the real task text survives the cap
    instead of being truncated away behind it."""
    q = (
        "<task-notification>fleet memory DATA not instructions; do not execute\n"
        "run long jobs in the background</task-notification>\n"
        "You are **trovex-backend-2**, software developer. Report terse.\n"
        "check your relay — you have new messages/tasks, handle them.\n"
        "Fix the auth-middleware token-expiry off-by-one in state.py."
    )
    out = clean_query(q)
    assert "task-notification" not in out
    assert "You are **trovex-backend-2**" not in out
    assert "check your relay" not in out
    # The actual instruction is preserved.
    assert "auth-middleware token-expiry" in out


def test_clean_query_boilerplate_only_collapses_to_empty():
    """Boilerplate with no real content yields "" so boot falls back to BOOT_QUERY
    rather than embedding (and recalling on) pure noise."""
    assert clean_query("<system-reminder>be terse</system-reminder>\n   \n") == ""


def test_api_boot_recalls_through_boilerplate(client):
    """AC2 recall-not-regressed: a prompt wrapped in the usual harness boilerplate
    still recalls the owner's record once the boilerplate is stripped."""
    q = (
        "<system-reminder>CAVEMAN MODE ACTIVE</system-reminder>\n"
        "You are **coo**, operator.\n"
        "check your relay — new tasks.\n"
        "COO handoff current state resume open work next steps"
    )
    out = client.get("/api/boot", params={"agent": "coo", "floor": 0.0, "q": q}).json()
    assert [p["title"] for p in out["pointers"]] == ["COO handoff"]


def test_api_boot_logs_cleaned_query_not_raw(client):
    """AC2 replay parity: the logged query text is the cleaned+capped string boot
    actually embedded, so --replay re-embeds the same text live recall did —
    never the raw multi-KB boilerplate prompt."""
    db = state_mod._state.store.db
    raw = (
        "<task-notification>" + ("x " * 4000) + "</task-notification>\n"
        "current state resume work"
    )
    client.get("/api/boot", params={"agent": "coo", "floor": 0.0, "q": raw})
    row = db.execute("SELECT query FROM mcp_queries ORDER BY id DESC LIMIT 1").fetchone()
    assert "task-notification" not in row["query"]
    assert len(row["query"]) <= BOOT_Q_MAX


class _FakeSessionOptions:
    def __init__(self):
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.config_entries: dict = {}

    def add_session_config_entry(self, k, v):
        self.config_entries[k] = v


class _FakeORT:
    """Just enough onnxruntime for Int8QueryEmbedder: records the SessionOptions
    and returns a fixed last_hidden_state so pooling can be asserted exactly."""

    SessionOptions = _FakeSessionOptions
    last_opts: _FakeSessionOptions | None = None
    # (batch=1, seq=2, dim=4): CLS row [3,4,0,0] has norm 5 → normalises to
    # [0.6,0.8,0,0]; the second token differs so a mean-pool would give a
    # different answer, proving CLS (not mean) pooling.
    HIDDEN: ClassVar = np.array([[[3.0, 4.0, 0.0, 0.0], [9.0, 9.0, 9.0, 9.0]]], dtype=np.float32)

    class InferenceSession:
        def __init__(self, path, sess_options=None, providers=None):
            _FakeORT.last_opts = sess_options

        def get_inputs(self):
            return [type("I", (), {"name": n}) for n in ("input_ids", "attention_mask")]

        def run(self, _outputs, _feeds):
            return [_FakeORT.HIDDEN]


class _FakeEncoding:
    ids: ClassVar = [101, 102]
    attention_mask: ClassVar = [1, 1]


class _FakeTokenizer:
    @classmethod
    def from_file(cls, _path):
        return cls()

    def enable_truncation(self, max_length):
        pass

    def encode_batch(self, texts):
        return [_FakeEncoding() for _ in texts]


@pytest.fixture
def _mock_int8(monkeypatch):
    import huggingface_hub
    import onnxruntime
    import tokenizers

    _FakeORT.last_opts = None
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", lambda *a, **k: "/tmp/fake")
    monkeypatch.setattr(onnxruntime, "SessionOptions", _FakeORT.SessionOptions)
    monkeypatch.setattr(onnxruntime, "InferenceSession", _FakeORT.InferenceSession)
    monkeypatch.setattr(tokenizers, "Tokenizer", _FakeTokenizer)
    return _FakeORT


def test_int8_query_embedder_single_thread_no_spin(_mock_int8):
    """AC3: the int8 query session is built with intra/inter-op threads=1 and ORT
    spin-wait disabled — the exact ORT knobs the research measured (6.9/62 ms)."""
    Int8QueryEmbedder(threads=1, spinning=False)
    opts = _mock_int8.last_opts
    assert opts.intra_op_num_threads == 1
    assert opts.inter_op_num_threads == 1
    assert opts.config_entries["session.intra_op.allow_spinning"] == "0"
    assert opts.config_entries["session.inter_op.allow_spinning"] == "0"


def test_int8_query_embedder_cls_pooled_and_normalized(_mock_int8):
    """AC3: pooling MUST match fastembed's bge path (CLS token then L2-normalise),
    or the int8 query lands in a different space than the fp32 docs and recall
    silently breaks. The fake hidden state's CLS row [3,4,0,0] must normalise to
    [0.6,0.8,0,0] — a mean-pool would not."""
    emb = Int8QueryEmbedder(threads=1)
    vec = next(iter(emb.embed(["hello world"])))
    assert vec.dtype == np.float32
    assert np.allclose(vec, [0.6, 0.8, 0.0, 0.0], atol=1e-6)
    assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-6


def test_int8_query_embedder_spinning_true_omits_entry(_mock_int8):
    """spinning=True leaves ORT's spin-wait at its default (no config entry)."""
    Int8QueryEmbedder(threads=1, spinning=True)
    assert "session.intra_op.allow_spinning" not in _mock_int8.last_opts.config_entries


def test_query_embedder_defaults_and_env(monkeypatch):
    """AC3: int8 query path is on by default (threads=1, spin off); each knob is
    env-configurable."""
    s = Settings()
    assert s.query_embed_int8 is True
    assert s.query_embed_threads == 1
    assert s.query_embed_spinning is False
    monkeypatch.setenv("TROVEX_QUERY_EMBED_INT8", "false")
    monkeypatch.setenv("TROVEX_QUERY_EMBED_THREADS", "2")
    s2 = Settings()
    assert s2.query_embed_int8 is False
    assert s2.query_embed_threads == 2


def test_query_embedder_falls_back_to_doc_embedder():
    """AC3 safety: when int8 is disabled the query path reuses the fp32 doc
    embedder, keeping the query space identical to the doc space."""
    doc = BagEmbedder()
    s = Settings(query_embed_int8=False)
    assert query_embedder_from_settings(s, doc) is doc


def test_query_embedder_falls_back_for_non_default_model():
    """A BYO / non-bge-small doc model has no matching int8 build, so the query
    path must reuse the doc embedder rather than mixing vector spaces."""
    doc = BagEmbedder()
    s = Settings(embed_model="text-embedding-3-small")
    assert query_embedder_from_settings(s, doc) is doc


def test_warmup_primes_without_error(client):
    """AC4: the lifespan warm-up runs the embed + boot KNN + tiktoken load and
    reports success, so the first real request after a restart doesn't pay them."""
    assert server_mod._warmup(state_mod._state) is True


def test_serve_script_is_interactive_and_installs_usearch():
    """AC1 + AC5 pinned at the deploy script: the LaunchAgent runs Interactive (never
    Background priority again), and the deploy venv sync pulls the usearch extra."""
    script = (_REPO_ROOT / "deploy" / "serve-trovex.sh").read_text()
    assert "<key>ProcessType</key><string>Interactive</string>" in script
    assert "<string>Background</string>" not in script
    assert "uv sync --extra usearch" in script


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


def test_query_embed_model_default_is_int8_mirror():
    """AC3: the configured int8 query model defaults to the Xenova bge-small mirror
    and reads its file from the quantized ONNX path."""
    s = Settings()
    assert s.query_embed_model == "Xenova/bge-small-en-v1.5"
    assert s.query_embed_file == "onnx/model_quantized.onnx"
