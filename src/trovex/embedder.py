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


class Int8QueryEmbedder:
    """Int8-quantized bge-small ONNX, QUERY-side only (perf A, task 62c53f35).

    The search hot path embeds one short query per request, synchronously, on the
    offload pool. fastembed runs that through an fp32 ONNX session whose ORT
    intra-op pool spin-waits across every physical core (18 here) — measurably
    slower on an oversubscribed fleet host and contending between concurrent
    requests. fastembed exposes no way to disable spin-wait (only
    enable_cpu_mem_arena), so this is a raw ORT session we fully control:
      • the int8 `model_quantized.onnx` (Xenova mirror) — ~2x cheaper CPU math;
      • intra/inter-op threads=1 and `session.intra_op.allow_spinning=0` — no
        spin contention (cto research: 6.9 ms p50 / 62 ms p95 at 16 concurrent vs
        16 / 172 ms with the fp32 fastembed session).

    DOC vectors stay fp32 fastembed (index path) — this only touches the query
    side. int8-query vs fp32-doc cosine drift is negligible (same model, same
    384-d space, CLS+L2 pooling); it is checked on the replay eval before ship.

    Pooling MUST match fastembed's bge path exactly or the query lands in a
    different space than the docs: take the CLS token (last_hidden_state[:, 0])
    then L2-normalise (see fastembed OnnxTextEmbedding._post_process_onnx_output).
    """

    def __init__(
        self,
        model_name: str = "Xenova/bge-small-en-v1.5",
        model_file: str = "onnx/model_quantized.onnx",
        dim: int = 384,
        threads: int = 1,
        spinning: bool = False,
    ):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        self.name = f"{model_name}:int8"
        self.dim = dim
        model_path = hf_hub_download(model_name, model_file)
        tok_path = hf_hub_download(model_name, "tokenizer.json")
        self._tok = Tokenizer.from_file(tok_path)
        self._tok.enable_truncation(max_length=512)

        so = ort.SessionOptions()
        if threads and threads > 0:
            so.intra_op_num_threads = threads
            so.inter_op_num_threads = threads
        # Disable ORT's spin-wait on a loaded host: spinning threads burn CPU that
        # the rest of the fleet needs and add latency under oversubscription.
        if not spinning:
            so.add_session_config_entry("session.intra_op.allow_spinning", "0")
            so.add_session_config_entry("session.inter_op.allow_spinning", "0")
        self._sess = ort.InferenceSession(model_path, sess_options=so, providers=["CPUExecutionProvider"])
        self._input_names = {i.name for i in self._sess.get_inputs()}

    def embed(self, texts: Iterable[str]) -> Iterable[np.ndarray]:
        encs = self._tok.encode_batch([t for t in texts])
        if not encs:
            return
        maxlen = max(len(e.ids) for e in encs)
        ids = np.zeros((len(encs), maxlen), dtype=np.int64)
        mask = np.zeros((len(encs), maxlen), dtype=np.int64)
        for row, e in enumerate(encs):
            n = len(e.ids)
            ids[row, :n] = e.ids
            mask[row, :n] = e.attention_mask
        feeds: dict[str, np.ndarray] = {"input_ids": ids, "attention_mask": mask}
        # bge exports a token_type_ids input (all zeros for a single sequence).
        if "token_type_ids" in self._input_names:
            feeds["token_type_ids"] = np.zeros_like(ids)
        feeds = {k: v for k, v in feeds.items() if k in self._input_names}
        out = self._sess.run(None, feeds)[0]
        # Match fastembed's bge pooling: CLS token then L2-normalise.
        pooled = out[:, 0] if out.ndim == 3 else out
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        yield from (pooled / norms).astype(np.float32)


def query_embedder_from_settings(settings, doc_embedder: Embedder) -> Embedder:
    """The embedder for the SEARCH/query path.

    Defaults to the int8 raw-ORT query session (perf A) when the doc model is the
    local bge-small fastembed default; falls back to the shared `doc_embedder` for
    any other provider/model (a BYO OpenAI or custom-dim model has no matching int8
    build) or if the int8 session can't be built (offline, missing file). Falling
    back keeps the query space identical to the doc space — never a hard failure."""
    if not settings.query_embed_int8:
        return doc_embedder
    if model_provider(settings.embed_model) != "fastembed" or settings.embed_model != "BAAI/bge-small-en-v1.5":
        return doc_embedder
    try:
        return Int8QueryEmbedder(
            model_name=settings.query_embed_model,
            model_file=settings.query_embed_file,
            dim=settings.resolved_embed_dim(),
            threads=settings.query_embed_threads,
            spinning=settings.query_embed_spinning,
        )
    except Exception:  # noqa: BLE001 — never let the query path fail to build
        import logging

        logging.getLogger("trovex.embedder").warning(
            "int8 query embedder unavailable — falling back to the fp32 doc embedder",
            exc_info=True,
        )
        return doc_embedder
