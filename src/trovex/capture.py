"""Active-memory capture (RFC 330e7d43, steps 3-4).

Writes an agent's current-state record so the next /api/boot recalls FRESH state.
Two paths, in increasing risk:

- **free-summary** (step 3, frequent): PostCompact already distilled the
  conversation — store that summary verbatim, NO LLM.
- **transcript distil** (step 4, fallback for sessions with no compaction): an
  LLM compresses the transcript. BYOK + best-effort (no key / error → no
  capture, never raises). MERGES with the agent's prior state so a truncated
  window doesn't lose earlier work (RFC residual bet #2: 24k → merge).

Both upsert the deterministic doc ``owner-<agent>-current-state`` (owner/<agent>
+ kind=record + type/current-state) — stable id ⇒ in-place overwrite, one
canonical record, no dup pile.
"""

from __future__ import annotations

import logging
import os

from openai import OpenAI

from .store import SqliteStore
from .usage import current_openai_key, current_rerank_model

log = logging.getLogger(__name__)

DISTIL_MODEL = os.environ.get("TROVEX_DISTIL_MODEL", "gpt-5.4-mini")
DISTIL_TIMEOUT_SEC = 20.0
MAX_TRANSCRIPT_CHARS = 24000

DISTIL_SYSTEM = (
    "You compress one coding-agent session into a durable current-state record. "
    "You are given the agent's PRIOR state (may be empty) and the RECENT session "
    "transcript. Produce the UPDATED state as markdown with ONLY these sections, "
    "omitting any that are empty:\n"
    "### Done this session\n### In flight (verify/continue)\n### Gotchas (don't repeat)\n"
    "### Next\n### Pointers (trovex ids / files)\n"
    "Merge: carry forward still-relevant prior items, add new ones, drop done/stale. "
    "Terse, facts only, no narration. If nothing durable, output exactly NO-SIGNAL."
)


def distil_summary(transcript: str, *, prior: str = "") -> str | None:
    """LLM-distil a transcript into a current-state summary, merged with prior
    state. BYOK + best-effort: no key, short input, or any error → None (caller
    falls back). Never raises into the caller."""
    key = current_openai_key.get()
    transcript = (transcript or "").strip()
    if not key or len(transcript) < 40:
        return None
    model = current_rerank_model.get() or DISTIL_MODEL
    window = transcript[-MAX_TRANSCRIPT_CHARS:]
    user = f"PRIOR STATE:\n{prior or '(none)'}\n\nRECENT TRANSCRIPT:\n{window}"
    params: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": DISTIL_SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    if model.startswith(("gpt-5", "o1", "o3", "o4")):
        params["max_completion_tokens"] = 2048
    else:
        params["max_tokens"] = 1024
        params["temperature"] = 0
    try:
        client = OpenAI(api_key=key, timeout=DISTIL_TIMEOUT_SEC)
        resp = client.chat.completions.create(**params)
    except Exception:  # best-effort, never block the agent
        log.warning("distil failed")
        return None
    md = (resp.choices[0].message.content or "").strip()
    if md == "NO-SIGNAL" or len(md) < 40:
        return None
    return md


def capture_state(
    store: SqliteStore,
    agent: str,
    summary: str = "",
    *,
    transcript: str = "",
    reason: str = "postcompact",
) -> dict:
    summary = (summary or "").strip()
    # Free path takes the summary verbatim; transcript path distils (merging the
    # existing record forward so truncation doesn't lose earlier state).
    if not summary and transcript:
        existing = store.get(f"owner-{agent}-current-state")
        summary = distil_summary(transcript, prior=existing.content if existing else "") or ""
    if len(summary) < 20:
        return {"captured": False, "reason": "no durable signal"}
    doc_id = f"owner-{agent}-current-state"
    content = f"# {agent} — current state ({reason})\n\n{summary}"
    store.put(
        content,
        kind="record",
        ext_id=doc_id,
        # lower-cased so the owner tag matches /api/boot's scope regardless of
        # the agent name's case (the store lower-cases tags on write anyway).
        tags=[f"owner/{agent.lower()}", "type/current-state", f"capture/{reason}"],
    )
    return {"captured": True, "doc_id": doc_id, "tokens": max(1, len(content) // 4)}
