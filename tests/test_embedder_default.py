"""Honesty invariant: trovex ships a LOCAL default embedder.

The landing copy promises "no cloud, no API keys, your code never leaves your
machine" (SQLite + ONNX). That promise is only true if the OUT-OF-BOX default
embedder is local. These tests lock that: the default must be a fastembed/ONNX
model, must not require an API key, and its declared dim must match the model.
Opting into OpenAI is allowed, but only via an explicit TROVEX_EMBED_MODEL.
"""

from trovex.config import Settings
from trovex.embedder import model_dim, model_provider


def test_default_embedder_is_local() -> None:
    """Default provider must be local (fastembed/ONNX), never a cloud API."""
    s = Settings()
    assert model_provider(s.embed_model) != "openai", (
        f"default embed_model {s.embed_model!r} sends chunks to a cloud API — "
        "breaks the 'never leaves your machine' promise"
    )
    assert model_provider(s.embed_model) == "fastembed"


def test_default_dim_matches_model() -> None:
    """Declared embed_dim must match the default model's real dimension."""
    s = Settings()
    assert s.embed_dim == model_dim(s.embed_model)
    assert s.resolved_embed_dim() == model_dim(s.embed_model)


def test_default_embedder_needs_no_api_key(monkeypatch) -> None:
    """Building the default embedder must not require OPENAI_API_KEY."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TROVEX_OPENAI_KEY", raising=False)
    # provider check is the contract; we don't construct fastembed (downloads ONNX).
    s = Settings()
    assert model_provider(s.embed_model) != "openai"
