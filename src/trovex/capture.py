"""Active-memory capture (RFC 330e7d43, step 3).

Writes an agent's current-state record from a free summary — the PostCompact
free-summary path (NO LLM): the compaction already distilled the conversation,
so we store that verbatim. Upserts the deterministic doc
``owner-<agent>-current-state`` (owner/<agent> + kind=record + type/current-state)
so the next /api/boot recalls the FRESH state instead of a stale hand-written
resume. One canonical record per agent — the stable id makes every capture an
in-place overwrite, never a dup pile. Distil-from-transcript is step 4.
"""

from __future__ import annotations

from .store import SqliteStore


def capture_state(
    store: SqliteStore,
    agent: str,
    summary: str,
    *,
    reason: str = "postcompact",
) -> dict:
    summary = (summary or "").strip()
    if len(summary) < 20:
        return {"captured": False, "reason": "no durable signal"}
    doc_id = f"owner-{agent}-current-state"
    content = f"# {agent} — current state ({reason})\n\n{summary}"
    store.put(
        content,
        kind="record",
        ext_id=doc_id,
        tags=[f"owner/{agent}", "type/current-state", f"capture/{reason}"],
    )
    return {"captured": True, "doc_id": doc_id, "tokens": max(1, len(content) // 4)}
