"""Local, key-free cross-encoder reranker — the DEFAULT rerank tier.

Reranking is the single biggest retrieval-accuracy jump in the literature, but
trovex's only reranker was LLM BYOK: gated on the caller's key, so in practice
most queries got NO rerank. This adds a LOCAL ONNX cross-encoder
(fastembed `TextCrossEncoder`, ms-marco-MiniLM by default) that runs on CPU,
offline (after a one-time model fetch), deterministically, with zero key — so
rerank is on by default for everyone.

It re-scores only the top candidates from the hybrid step (a cross-encoder is
O(candidates) model passes, so we cap it) and returns them reordered. Never
raises into the caller: a missing dep, a failed model load (e.g. offline first
run), or an encode error all degrade to the input order — rerank is an upgrade,
never a hard dependency.

Tiers (see rerank.maybe_rerank): LLM BYOK (premium, when a key is present) →
this local cross-encoder (default) → passthrough (disabled / unavailable).
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Default local model: ms-marco-MiniLM-L-6-v2 (~80MB ONNX, CPU-fast, ~ms/query).
# Override with TROVEX_RERANK_LOCAL_MODEL; disable the whole tier with
# TROVEX_DISABLE_LOCAL_RERANK=1 (falls back to passthrough / LLM tier only).
DEFAULT_LOCAL_MODEL = os.environ.get(
    "TROVEX_RERANK_LOCAL_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2"
)
# A cross-encoder does one model pass per candidate, so cap what we rerank —
# the top of the hybrid list is where the right doc almost always already is.
MAX_LOCAL_CANDIDATES = 20
_SNIPPET_CHARS = 400  # per-candidate body text fed to the cross-encoder

_encoder = None
_tried = False


def enabled() -> bool:
    return os.environ.get("TROVEX_DISABLE_LOCAL_RERANK") not in ("1", "true", "True")


def _get_encoder():
    """Lazy-load + memoize the cross-encoder; None if it can't be loaded.

    First call fetches the ONNX model (network); cached under fastembed's cache
    afterwards. Any failure (missing dep, offline, bad model) → None, and the
    caller passes through untouched."""
    global _encoder, _tried
    if _tried:
        return _encoder
    _tried = True
    if not enabled():
        return None
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        _encoder = TextCrossEncoder(DEFAULT_LOCAL_MODEL)
    except Exception:  # noqa: BLE001 — offline/missing dep/bad model all degrade the same
        log.debug("local cross-encoder unavailable; rerank passthrough", exc_info=True)
        _encoder = None
    return _encoder


def _read_snippet(absolute_path: str) -> str:
    if not absolute_path:
        return ""
    try:
        return Path(absolute_path).read_text(encoding="utf-8", errors="replace")[:_SNIPPET_CHARS]
    except OSError:
        return ""


def _default_text(c) -> str:
    """Cross-encoder document text for a SearchResult: title + a leading body
    snippet (read from disk for file-backed docs). Falls back to title/path so a
    doc with no readable body still contributes its (descriptive) title."""
    head = (getattr(c, "title", "") or getattr(c, "path", "") or "").strip()
    snip = _read_snippet(getattr(c, "absolute_path", "") or "")
    return f"{head}. {snip}".strip() if snip else head


def rerank(query, candidates, limit, text_fn=None):
    """Reorder `candidates` by cross-encoder relevance; return (results, info).

    info is a dict {model, tokens_in, tokens_out, elapsed_ms} (tokens are 0 — a
    local model spends no API tokens) or None when rerank didn't run. Always
    returns at least the original top-`limit` so the caller can use it blindly.
    """
    enc = _get_encoder()
    if enc is None or not candidates:
        return candidates[:limit], None
    cands = candidates[:MAX_LOCAL_CANDIDATES]
    tf = text_fn or _default_text
    docs = [tf(c) for c in cands]
    try:
        t0 = time.perf_counter()
        scores = list(enc.rerank(query, docs))
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
    except Exception:  # noqa: BLE001 — never block the tool
        log.debug("local rerank encode failed; passthrough", exc_info=True)
        return candidates[:limit], None
    if len(scores) != len(cands):
        return candidates[:limit], None
    order = sorted(range(len(cands)), key=lambda i: scores[i], reverse=True)
    reordered = [cands[i] for i in order]
    info = {
        "model": DEFAULT_LOCAL_MODEL,
        "tokens_in": 0,
        "tokens_out": 0,
        "elapsed_ms": elapsed_ms,
    }
    return reordered[:limit], info


def rerank_results(query, candidates, limit, text_fn=None):
    """Convenience: just the reordered list (drops the info) — for the eval path."""
    results, _ = rerank(query, candidates, limit, text_fn=text_fn)
    return results
