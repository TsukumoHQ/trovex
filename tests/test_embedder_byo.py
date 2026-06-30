"""Bring-your-own-embedder routing: build_embedder / embedder_from_settings.

These lock the plumbing WITHOUT downloading any ONNX model or hitting a network:
the two concrete embedders are stubbed, and we assert build_embedder picks the
right backend and threads provider / base_url / dim through. A live multi-model
index is exercised separately (see scripts/proof), not in unit tests.
"""

import trovex.embedder as emb
from trovex.config import Settings
from trovex.embedder import build_embedder, embedder_from_settings


class _Rec:
    """Records the construction args of whichever embedder build_embedder chose."""

    def __init__(self, model_name, api_key=None, base_url=None, dim=None):
        self.name = model_name
        self.base_url = base_url
        self.dim = dim or 999


def _stub(monkeypatch):
    calls = {}

    class FastStub(_Rec):
        def __init__(self, model_name, dim=None):
            super().__init__(model_name, dim=dim)
            calls["kind"] = "fastembed"
            calls["dim"] = dim

    class OpenAIStub(_Rec):
        def __init__(self, model_name, api_key=None, base_url=None, dim=None):
            super().__init__(model_name, api_key, base_url, dim)
            calls["kind"] = "openai"
            calls["base_url"] = base_url
            calls["dim"] = dim

    monkeypatch.setattr(emb, "FastEmbedEmbedder", FastStub)
    monkeypatch.setattr(emb, "OpenAIEmbedder", OpenAIStub)
    return calls


def test_known_local_model_routes_to_fastembed(monkeypatch):
    calls = _stub(monkeypatch)
    build_embedder("BAAI/bge-small-en-v1.5")
    assert calls["kind"] == "fastembed"


def test_known_openai_model_routes_to_openai(monkeypatch):
    calls = _stub(monkeypatch)
    build_embedder("text-embedding-3-large")
    assert calls["kind"] == "openai"


def test_unknown_model_defaults_to_local(monkeypatch):
    calls = _stub(monkeypatch)
    build_embedder("some/never-heard-of-model")
    assert calls["kind"] == "fastembed"


def test_provider_override_and_base_url_and_dim(monkeypatch):
    calls = _stub(monkeypatch)
    build_embedder(
        "my-local-llm",
        provider="openai",
        base_url="http://localhost:11434/v1",
        dim=768,
    )
    assert calls["kind"] == "openai"
    assert calls["base_url"] == "http://localhost:11434/v1"
    assert calls["dim"] == 768


def test_embedder_from_settings_threads_byo_fields(monkeypatch):
    calls = _stub(monkeypatch)
    s = Settings(
        embed_model="custom-768-model",
        embed_dim=768,
        embed_provider="fastembed",
    )
    embedder_from_settings(s)
    assert calls["kind"] == "fastembed"
    # unknown model → registry dim 0 → resolved_embed_dim falls back to embed_dim
    assert calls["dim"] == 768


def test_openai_embedder_local_base_url_needs_no_key(monkeypatch):
    """A local OpenAI-compatible endpoint must construct without OPENAI_API_KEY."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TROVEX_OPENAI_KEY", raising=False)
    e = emb.OpenAIEmbedder(
        "nomic-embed-text", base_url="http://localhost:11434/v1", dim=768
    )
    assert e.dim == 768
