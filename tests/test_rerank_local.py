"""Local cross-encoder rerank — the key-free DEFAULT tier + the maybe_rerank tiering.

Hermetic: the real ONNX cross-encoder is never loaded (CI is offline). A fake
encoder with controlled scores exercises the reorder/passthrough logic, and the
tiering is checked by monkeypatching the seams. The real-model hit@1 lift is
measured out-of-band via `trovex bench --retrieval --rerank` (see the PR body).
"""

from __future__ import annotations

import pytest

from trovex import rerank, rerank_local
from trovex.search import SearchResult


def _sr(path: str, title: str = "", absolute_path: str = "") -> SearchResult:
    return SearchResult(
        path=path,
        title=title or path,
        distance=0.5,
        score=1.0,
        age_days=0.0,
        status="canonical",
        size_bytes=100,
        tokens_est=50,
        absolute_path=absolute_path,
        source_id="code",
    )


class _FakeEncoder:
    """Returns a preset score per doc, keyed by substring match — deterministic."""

    def __init__(self, scores: list[float]):
        self._scores = scores

    def rerank(self, query, docs):  # noqa: ARG002 — mirrors fastembed signature
        return list(self._scores)


@pytest.fixture(autouse=True)
def _reset_encoder_cache():
    """Each test starts with a clean lazy-load cache."""
    rerank_local._encoder = None
    rerank_local._tried = False
    yield
    rerank_local._encoder = None
    rerank_local._tried = False


def test_local_rerank_reorders_by_score(monkeypatch):
    cands = [_sr("a.md"), _sr("b.md"), _sr("c.md")]
    # b should win (highest score), then c, then a.
    monkeypatch.setattr(rerank_local, "_get_encoder", lambda: _FakeEncoder([0.1, 0.9, 0.5]))
    results, info = rerank_local.rerank("q", cands, limit=2)
    assert [r.path for r in results] == ["b.md", "c.md"]
    assert info is not None
    assert info["tokens_in"] == 0 and info["tokens_out"] == 0  # local spends no API tokens
    assert info["model"]


def test_local_rerank_passthrough_when_encoder_unavailable(monkeypatch):
    cands = [_sr("a.md"), _sr("b.md")]
    monkeypatch.setattr(rerank_local, "_get_encoder", lambda: None)
    results, info = rerank_local.rerank("q", cands, limit=5)
    assert [r.path for r in results] == ["a.md", "b.md"]  # original order
    assert info is None


def test_local_rerank_passthrough_on_encode_error(monkeypatch):
    class _Boom:
        def rerank(self, *a, **k):
            raise RuntimeError("onnx blew up")

    cands = [_sr("a.md"), _sr("b.md")]
    monkeypatch.setattr(rerank_local, "_get_encoder", lambda: _Boom())
    results, info = rerank_local.rerank("q", cands, limit=5)
    assert [r.path for r in results] == ["a.md", "b.md"]
    assert info is None


def test_local_rerank_score_count_mismatch_is_safe(monkeypatch):
    cands = [_sr("a.md"), _sr("b.md"), _sr("c.md")]
    monkeypatch.setattr(rerank_local, "_get_encoder", lambda: _FakeEncoder([0.9]))  # too few
    results, info = rerank_local.rerank("q", cands, limit=3)
    assert [r.path for r in results] == ["a.md", "b.md", "c.md"]
    assert info is None


def test_disabled_via_env(monkeypatch):
    monkeypatch.setenv("TROVEX_DISABLE_LOCAL_RERANK", "1")
    assert rerank_local.enabled() is False
    assert rerank_local._get_encoder() is None


def test_default_text_uses_title_and_disk_snippet(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("# Deploy guide\n\nkubernetes rollout steps", encoding="utf-8")
    txt = rerank_local._default_text(_sr("doc.md", title="Deploy guide", absolute_path=str(p)))
    assert "Deploy guide" in txt
    assert "kubernetes rollout steps" in txt

    # No readable body → title only, never crashes.
    txt2 = rerank_local._default_text(_sr("x.md", title="Only Title", absolute_path="/nope/x.md"))
    assert txt2 == "Only Title"


# --- tiering in maybe_rerank ---


def test_maybe_rerank_empty_candidates():
    results, info = rerank.maybe_rerank("q", [], limit=5)
    assert results == [] and info is None


def test_maybe_rerank_uses_local_when_no_key(monkeypatch):
    tok = rerank.current_openai_key.set(None)
    called = {}

    def fake_local(query, cands, limit, text_fn=None):  # noqa: ARG001
        called["yes"] = True
        return list(reversed(cands))[:limit], {
            "model": "fake-local",
            "tokens_in": 0,
            "tokens_out": 0,
            "elapsed_ms": 1,
        }

    monkeypatch.setattr(rerank_local, "rerank", fake_local)
    try:
        # >limit candidates so the rerank path runs (<=limit now skips, T4).
        cands = [_sr("a.md"), _sr("b.md")]
        results, info = rerank.maybe_rerank("q", cands, limit=1)
    finally:
        rerank.current_openai_key.reset(tok)
    assert called.get("yes") is True
    assert [r.path for r in results] == ["b.md"]  # reversed, top-1
    assert info is not None and info.model == "fake-local"


def test_margin_clear_true_on_wide_score_gap():
    """task 4478fe53: rank 1 beating rank 2 by more than RERANK_MARGIN (default
    0.2) of rank 1's score is a settled fusion result — a rerank pass can't
    change it."""
    cands = [_sr("a.md"), _sr("b.md")]
    cands[0].score = 1.0
    cands[1].score = 0.5  # (1.0 - 0.5) / 1.0 = 0.5 > 0.2
    assert rerank._margin_clear(cands) is True


def test_margin_clear_false_on_tight_score_gap():
    cands = [_sr("a.md"), _sr("b.md")]
    cands[0].score = 1.0
    cands[1].score = 0.9  # (1.0 - 0.9) / 1.0 = 0.1 <= 0.2
    assert rerank._margin_clear(cands) is False


def test_margin_clear_true_with_fewer_than_two_candidates():
    assert rerank._margin_clear([_sr("a.md")]) is True
    assert rerank._margin_clear([]) is True


def test_margin_clear_false_when_top_score_not_positive():
    cands = [_sr("a.md"), _sr("b.md")]
    cands[0].score = 0.0
    cands[1].score = 0.0
    assert rerank._margin_clear(cands) is False  # no positive signal to measure


def test_maybe_rerank_skips_when_margin_clear(monkeypatch):
    """Skip path: RerankInfo carries rerank_skipped=True, candidate order is
    untouched, and neither the local cross-encoder nor the LLM tier is ever
    invoked — a settled winner should cost nothing."""
    tok = rerank.current_openai_key.set(None)
    cands = [_sr("a.md"), _sr("b.md"), _sr("c.md")]
    cands[0].score = 1.0
    cands[1].score = 0.5
    cands[2].score = 0.4

    def _boom(*a, **k):
        raise AssertionError("local rerank must not run on a clear-margin skip")

    monkeypatch.setattr(rerank_local, "rerank", _boom)
    try:
        results, info = rerank.maybe_rerank("q", cands, limit=1)
    finally:
        rerank.current_openai_key.reset(tok)
    assert [r.path for r in results] == ["a.md"]  # original order, untouched
    assert info is not None
    assert info.rerank_skipped is True
    assert info.model == "skip"


def test_maybe_rerank_runs_rerank_when_margin_tight(monkeypatch):
    """No-skip path: a tight margin falls through to the local cross-encoder
    tier and RerankInfo.rerank_skipped stays False."""
    tok = rerank.current_openai_key.set(None)
    cands = [_sr("a.md"), _sr("b.md"), _sr("c.md")]
    cands[0].score = 1.0
    cands[1].score = 0.95  # (1.0 - 0.95) / 1.0 = 0.05 <= 0.2 — margin not clear
    cands[2].score = 0.9

    def fake_local(query, cs, limit, text_fn=None):  # noqa: ARG001
        return list(reversed(cs))[:limit], {
            "model": "fake-local",
            "tokens_in": 0,
            "tokens_out": 0,
            "elapsed_ms": 1,
        }

    monkeypatch.setattr(rerank_local, "rerank", fake_local)
    try:
        results, info = rerank.maybe_rerank("q", cands, limit=1)
    finally:
        rerank.current_openai_key.reset(tok)
    assert [r.path for r in results] == ["c.md"]  # reversed by the fake local tier
    assert info is not None
    assert info.rerank_skipped is False
    assert info.model == "fake-local"


def test_maybe_rerank_llm_failure_falls_back_to_local(monkeypatch):
    tok = rerank.current_openai_key.set("sk-test-key")
    # LLM client construction blows up → the tier must fall through to local.
    monkeypatch.setattr(
        rerank, "OpenAI", lambda **k: (_ for _ in ()).throw(RuntimeError("no net"))
    )
    fell_back = {}

    def fake_local(query, cands, limit, text_fn=None):  # noqa: ARG001
        fell_back["yes"] = True
        return cands[:limit], None

    monkeypatch.setattr(rerank_local, "rerank", fake_local)
    try:
        # >limit candidates so rerank runs (<=limit skips, T4) and the LLM tier
        # is reached — then its failure falls back to local.
        rerank.maybe_rerank("q", [_sr("a.md"), _sr("b.md")], limit=1)
    finally:
        rerank.current_openai_key.reset(tok)
    assert fell_back.get("yes") is True
