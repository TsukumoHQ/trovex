"""BYOK reranker — uses the caller's OpenAI key to re-rank top-N candidates.

The vector search returns a wide list (top-20). The LLM judges each candidate's
actual relevance to the query and returns a re-ordered list. Improves top-1
quality without changing the rest of the pipeline.

Falls back gracefully:
  - no key on the request    → return input order, no LLM call
  - LLM error / timeout      → return input order, log nothing
  - bad/missing parsed order → return input order

The function NEVER raises into the caller. Reranking is a best-effort
upgrade, not a hard dependency.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

from openai import OpenAI

from .search import SearchResult
from .usage import current_openai_key, current_rerank_model

log = logging.getLogger(__name__)

# Default rerank model. Override globally with TROVEX_RERANK_MODEL, or per-request
# with the X-TROVEX-Rerank-Model header (allow-list: gpt-5.* family).
DEFAULT_MODEL = os.environ.get("TROVEX_RERANK_MODEL", "gpt-5.4-mini")
RERANK_TIMEOUT_SEC = 8.0
MAX_CANDIDATES = 20
MAX_SNIPPET_CHARS = 400  # ~100 tokens per candidate


def _pick_model() -> str:
    override = current_rerank_model.get()
    return override or DEFAULT_MODEL


@dataclass
class RerankInfo:
    model: str
    tokens_in: int
    tokens_out: int
    elapsed_ms: int


def maybe_rerank(
    query: str,
    candidates: list[SearchResult],
    limit: int,
) -> tuple[list[SearchResult], RerankInfo | None]:
    """Return (results, rerank_info or None).

    Always returns at least the original top-`limit` candidates so the caller
    can blindly use the result.
    """
    key = current_openai_key.get()
    if not key or not candidates:
        return candidates[:limit], None

    try:
        client = OpenAI(api_key=key, timeout=RERANK_TIMEOUT_SEC)
        return _rerank(client, query, candidates, limit)
    except Exception as e:  # noqa: BLE001 — never block the tool
        log.warning("rerank failed: %s", e.__class__.__name__)
        return candidates[:limit], None


def _rerank(
    client: OpenAI,
    query: str,
    candidates: list[SearchResult],
    limit: int,
) -> tuple[list[SearchResult], RerankInfo | None]:
    cands = candidates[:MAX_CANDIDATES]
    indexed_snippets = [_candidate_line(i, c) for i, c in enumerate(cands)]

    system = (
        "You rank documentation snippets for relevance to a developer's query. "
        "Markers: ★ canonical (preferred), ◯ plan, ✗ stale (avoid), ⚠ duplicate. "
        "Return ONLY a JSON object {\"order\": [indices]} with the most relevant first. "
        "Include every input index exactly once. No prose."
    )
    user = f"Query: {query}\n\nCandidates:\n" + "\n".join(indexed_snippets)

    model = _pick_model()
    # GPT-5.x family uses max_completion_tokens; older models accept either.
    # Send both as kwargs, swallow the deprecated one if API rejects it via fallback.
    params = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    # max_completion_tokens for gpt-5.x / o-series (which may consume hidden
    # reasoning tokens before emitting). max_tokens for legacy chat models.
    # Headroom: a 20-candidate JSON order array is ~80 tokens; 2048 leaves
    # plenty for reasoning without runaway cost.
    if model.startswith(("gpt-5", "o1", "o3", "o4")):
        params["max_completion_tokens"] = 2048
    else:
        params["max_tokens"] = 512
        params["temperature"] = 0
    t0 = time.perf_counter()
    resp = client.chat.completions.create(**params)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    content = (resp.choices[0].message.content or "").strip()
    try:
        parsed = json.loads(content)
        order = parsed.get("order", [])
    except (json.JSONDecodeError, AttributeError):
        return candidates[:limit], None

    seen: set[int] = set()
    reordered: list[SearchResult] = []
    for idx in order:
        if not isinstance(idx, int) or idx in seen or idx < 0 or idx >= len(cands):
            continue
        seen.add(idx)
        reordered.append(cands[idx])
    for i, c in enumerate(cands):
        if i not in seen:
            reordered.append(c)
    final = reordered[:limit]

    usage = resp.usage
    info = RerankInfo(
        model=model,
        tokens_in=usage.prompt_tokens if usage else 0,
        tokens_out=usage.completion_tokens if usage else 0,
        elapsed_ms=elapsed_ms,
    )
    return final, info


def _candidate_line(idx: int, c: SearchResult) -> str:
    marker = c.marker
    title = c.title[:80] if c.title else ""
    return f"[{idx}] {marker} {c.path} — {title}"
