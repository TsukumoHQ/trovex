"""distil_summary + the capture transcript path (RFC 330e7d43, step 4).

The LLM fallback for sessions with no compaction. BYOK + best-effort: no key,
thin input, NO-SIGNAL, or any API error → None and the caller falls back; it must
never raise into the agent. Hermetic — the OpenAI client is faked, no network,
no key needed beyond a sentinel in the context var.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex import capture as capture_mod
from trovex.capture import capture_state, distil_summary
from trovex.config import Settings
from trovex.store import SqliteStore
from trovex.usage import current_openai_key, current_rerank_model

DIM = 384
LONG_TRANSCRIPT = "user: fix the boot scope bug\nassistant: lowercased the owner tag\n" * 4
DISTILLED = (
    "### Done this session\n- Fixed boot owner-scope case.\n### Next\n- Lint sweep, pending cmo."
)


# ── a minimal fake OpenAI client ─────────────────────────────────────


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]


def _fake_openai(content, *, raise_exc=None, calls=None):
    class _Completions:
        def create(self, **params):
            if calls is not None:
                calls.append(params)
            if raise_exc is not None:
                raise raise_exc
            return _Resp(content)

    class _Chat:
        completions = _Completions()

    class _Client:
        def __init__(self, **kw):
            self.chat = _Chat()

    return _Client


@pytest.fixture
def with_key():
    """A sentinel BYOK key in the context var, cleaned up after."""
    tok = current_openai_key.set("sk-test-sentinel")
    try:
        yield
    finally:
        current_openai_key.reset(tok)


@pytest.fixture
def store(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )

    class _Bag:
        name = "bag"
        dim = DIM

        def embed(self, texts):
            for t in texts:
                v = np.zeros(DIM, dtype=np.float32)
                for tok in re.findall(r"[a-z0-9]+", t.lower()):
                    idx = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                    v[idx % DIM] += 1.0
                yield v / (float(np.linalg.norm(v)) or 1.0)

    return SqliteStore(settings, embedder=_Bag())


def test_distil_no_key_returns_none():
    """No key in context → None, and the client is never constructed."""
    assert distil_summary(LONG_TRANSCRIPT) is None


def test_distil_thin_transcript_skips_api(with_key, monkeypatch):
    calls = []
    monkeypatch.setattr(capture_mod, "OpenAI", _fake_openai(DISTILLED, calls=calls))
    assert distil_summary("too short") is None
    assert calls == []  # bailed before any API call


def test_distil_happy_path_uses_gpt5_param_shape(with_key, monkeypatch):
    calls = []
    monkeypatch.setattr(capture_mod, "OpenAI", _fake_openai(DISTILLED, calls=calls))

    out = distil_summary(LONG_TRANSCRIPT, prior="### Next\n- old item")
    assert out == DISTILLED

    (params,) = calls
    assert params["model"] == "gpt-5.4-mini"
    # gpt-5* takes max_completion_tokens, not max_tokens/temperature.
    assert "max_completion_tokens" in params
    assert "max_tokens" not in params and "temperature" not in params
    # prior state + transcript are both threaded into the user message.
    user = params["messages"][-1]["content"]
    assert "old item" in user and "boot scope bug" in user


def test_distil_non_gpt5_model_uses_temperature(with_key, monkeypatch):
    calls = []
    monkeypatch.setattr(capture_mod, "OpenAI", _fake_openai(DISTILLED, calls=calls))
    tok = current_rerank_model.set("gpt-4o-mini")
    try:
        assert distil_summary(LONG_TRANSCRIPT) == DISTILLED
    finally:
        current_rerank_model.reset(tok)
    (params,) = calls
    assert params["model"] == "gpt-4o-mini"
    assert params["max_tokens"] == 1024 and params["temperature"] == 0


def test_distil_no_signal_returns_none(with_key, monkeypatch):
    monkeypatch.setattr(capture_mod, "OpenAI", _fake_openai("NO-SIGNAL"))
    assert distil_summary(LONG_TRANSCRIPT) is None


def test_distil_swallows_api_error(with_key, monkeypatch):
    monkeypatch.setattr(capture_mod, "OpenAI", _fake_openai("", raise_exc=RuntimeError("boom")))
    assert distil_summary(LONG_TRANSCRIPT) is None  # best-effort, never raises


def test_capture_distils_when_no_summary(with_key, monkeypatch, store):
    """capture_state with no summary but a transcript → distils, then upserts the
    canonical record (the step-4 wiring through to the store)."""
    monkeypatch.setattr(capture_mod, "OpenAI", _fake_openai(DISTILLED))
    out = capture_state(store, "alpha", summary="", transcript=LONG_TRANSCRIPT)
    assert out["captured"] is True
    doc = store.get("owner-alpha-current-state")
    assert "Lint sweep" in doc.content


def test_capture_no_summary_failed_distil_captures_nothing(with_key, monkeypatch, store):
    """Distil returns None (NO-SIGNAL) and no free summary → nothing written."""
    monkeypatch.setattr(capture_mod, "OpenAI", _fake_openai("NO-SIGNAL"))
    out = capture_state(store, "alpha", summary="", transcript=LONG_TRANSCRIPT)
    assert out["captured"] is False
    assert store.get("owner-alpha-current-state") is None
