"""Query-embedding cache (perf T1).

A query embedding is the latency driver on the search path — a synchronous ONNX
forward pass. It is also deterministic per model, and the same text recurs
constantly: /api/boot re-embeds the SAME BOOT_QUERY every session, and agents
repeat queries. Caching the serialized query vector by (model, text) turns those
into a dict lookup and takes the ONNX call off the hot path entirely on a hit.

Thread-safe: search runs in a threadpool (off the event loop), so several
requests may hit this concurrently. The expensive embed runs OUTSIDE the lock —
a rare duplicate compute on a cold race is cheaper than serializing every query
embed on one lock.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

import sqlite_vec

# (model_name, text) -> serialized float32 blob. Bounded LRU.
_CACHE: OrderedDict[tuple[str, str], bytes] = OrderedDict()
_LOCK = threading.Lock()
_MAX = 1024


def embed_query_blob(embedder, text: str) -> bytes:
    """Serialized query embedding for `text`, LRU-cached by (model, text).

    Returns the same bytes a fresh `sqlite_vec.serialize_float32(embed(text))`
    would — no correctness change, just a cache in front of the ONNX call."""
    key = (getattr(embedder, "name", "?"), text)
    with _LOCK:
        hit = _CACHE.get(key)
        if hit is not None:
            _CACHE.move_to_end(key)
            return hit
    # Cold: embed outside the lock (the costly part).
    emb = next(iter(embedder.embed([text])))
    blob = sqlite_vec.serialize_float32(emb.tolist())
    with _LOCK:
        _CACHE[key] = blob
        _CACHE.move_to_end(key)
        while len(_CACHE) > _MAX:
            _CACHE.popitem(last=False)
    return blob


def clear_query_cache() -> None:
    """Drop all cached query embeddings (test hook; also safe on model change)."""
    with _LOCK:
        _CACHE.clear()
