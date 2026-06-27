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
    return MODEL_REGISTRY.get(model_name, (384, "fastembed"))[0]


def model_provider(model_name: str) -> str:
    return MODEL_REGISTRY.get(model_name, (384, "fastembed"))[1]


class Embedder(Protocol):
    dim: int
    name: str

    def embed(self, texts: Iterable[str]) -> Iterable[np.ndarray]: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str):
        import fastembed

        self.name = model_name
        self.dim = model_dim(model_name)
        self._client = fastembed.TextEmbedding(model_name=model_name)

    def embed(self, texts: Iterable[str]) -> Iterable[np.ndarray]:
        return self._client.embed(texts)


class OpenAIEmbedder:
    """Batches calls to OpenAI's embeddings endpoint.

    The OpenAI API limit per request is 2048 input items or ~300k tokens. We
    keep batches modest (64 items) to stay well under both limits while
    minimising round-trips.
    """

    BATCH_SIZE = 64
    MAX_RETRIES = 3

    def __init__(self, model_name: str, api_key: str | None = None):
        from openai import OpenAI

        self.name = model_name
        self.dim = model_dim(model_name)
        key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("TROVEX_OPENAI_KEY")
        if not key:
            raise RuntimeError(
                "OpenAI embedder needs a key. Set OPENAI_API_KEY env or pass api_key."
            )
        self._client = OpenAI(api_key=key, timeout=30)

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


def build_embedder(model_name: str) -> Embedder:
    provider = model_provider(model_name)
    if provider == "openai":
        return OpenAIEmbedder(model_name)
    return FastEmbedEmbedder(model_name)
