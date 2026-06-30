"""Pluggable embedder — local fastembed or OpenAI API.

Both implementations expose .embed(iterable) → list[np.ndarray] for sqlite-vec.
Dimension is fixed per-model; sqlite-vec virtual table must match.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterable
from typing import Protocol

import numpy as np

# Model registry: name → (dim, provider)
MODEL_REGISTRY = {
    # OpenAI
    "text-embedding-3-large": (3072, "openai"),
    "text-embedding-3-small": (1536, "openai"),
    "text-embedding-ada-002": (1536, "openai"),
    # fastembed (local ONNX)
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": (384, "fastembed"),
    "BAAI/bge-small-en-v1.5": (384, "fastembed"),
}


def model_dim(model_name: str) -> int:
    """Registry dim, or 0 for an unknown model (caller supplies an explicit dim).

    0 is a sentinel — resolved_embed_dim() falls back to the configured embed_dim,
    so a bring-your-own model is honoured via TROVEX_EMBED_DIM rather than being
    silently coerced to some other model's dimension.
    """
    return MODEL_REGISTRY.get(model_name, (0, "fastembed"))[0]


def model_provider(model_name: str) -> str:
    """Registry provider, defaulting to local fastembed for unknown models."""
    return MODEL_REGISTRY.get(model_name, (0, "fastembed"))[1]


class Embedder(Protocol):
    dim: int
    name: str

    def embed(self, texts: Iterable[str]) -> Iterable[np.ndarray]: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str, dim: int | None = None):
        import fastembed

        self.name = model_name
        # Bring-your-own fastembed model: honour an explicit dim, else the
        # registry dim, else bge-small's 384 as a last resort.
        self.dim = dim or model_dim(model_name) or 384
        self._client = fastembed.TextEmbedding(model_name=model_name)

    def embed(self, texts: Iterable[str]) -> Iterable[np.ndarray]:
        return self._client.embed(texts)


class OpenAIEmbedder:
    """Batches calls to an OpenAI-compatible embeddings endpoint.

    The endpoint defaults to OpenAI's hosted API, but `base_url` can point at any
    OpenAI-compatible server — including a LOCAL one (Ollama, LM Studio, vLLM,
    LocalAI). A localhost base_url keeps embeddings fully on your machine while
    reusing the OpenAI client + batching.

    The OpenAI API limit per request is 2048 input items or ~300k tokens. We
    keep batches modest (64 items) to stay well under both limits while
    minimising round-trips.
    """

    BATCH_SIZE = 64
    MAX_RETRIES = 3

    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        dim: int | None = None,
    ):
        from openai import OpenAI

        self.name = model_name
        # Custom/unknown models on a compatible endpoint declare their dim explicitly.
        self.dim = dim or model_dim(model_name)
        key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("TROVEX_OPENAI_KEY")
        if not key:
            if base_url:
                # Local servers (Ollama et al.) often ignore the key — use a placeholder
                # so the client constructs, rather than forcing a real OpenAI key.
                key = "not-needed"
            else:
                raise RuntimeError(
                    "OpenAI embedder needs a key. Set OPENAI_API_KEY env or pass api_key. "
                    "For a local OpenAI-compatible server, set TROVEX_OPENAI_BASE_URL instead."
                )
        self._client = OpenAI(api_key=key, timeout=30, base_url=base_url or None)

    def embed(self, texts: Iterable[str]) -> Iterable[np.ndarray]:
        # Materialise to a list so we can batch + retry.
        batch: list[str] = []
        for text in texts:
            batch.append(text or " ")  # OpenAI rejects empty strings
            if len(batch) >= self.BATCH_SIZE:
                yield from self._embed_batch(batch)
                batch = []
        if batch:
            yield from self._embed_batch(batch)

    def _embed_batch(self, batch: list[str]) -> list[np.ndarray]:
        last_err: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self._client.embeddings.create(
                    model=self.name,
                    input=batch,
                )
                return [np.array(d.embedding, dtype=np.float32) for d in resp.data]
            except Exception as e:  # noqa: BLE001 — retry on any transient
                last_err = e
                time.sleep(0.5 * (2**attempt))
        raise RuntimeError(f"OpenAI embed failed after retries: {last_err}")


def build_embedder(
    model_name: str,
    *,
    provider: str = "",
    base_url: str = "",
    dim: int = 0,
) -> Embedder:
    """Construct an embedder for `model_name`.

    provider: "openai" | "fastembed" | "" (infer from the registry; unknown → local).
    base_url: an OpenAI-compatible endpoint (e.g. a local Ollama/LM Studio server).
    dim: explicit vector dimension for a bring-your-own model not in the registry.
    """
    prov = provider or model_provider(model_name)
    if prov == "openai":
        return OpenAIEmbedder(model_name, base_url=base_url or None, dim=dim or None)
    return FastEmbedEmbedder(model_name, dim=dim or None)


def embedder_from_settings(settings) -> Embedder:
    """Build the embedder described by a Settings object (the BYO-embedder path)."""
    return build_embedder(
        settings.embed_model,
        provider=settings.embed_provider,
        base_url=settings.openai_base_url,
        dim=settings.resolved_embed_dim(),
    )
