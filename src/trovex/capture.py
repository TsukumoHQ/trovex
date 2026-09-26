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


GATE_PROBE_CHARS = 4000  # tail of a transcript embedded for the gate


def capture_state(
    store: SqliteStore,
    agent: str,
    summary: str = "",
    *,
    transcript: str = "",
    reason: str = "postcompact",
) -> dict:
    """Upsert the agent's current-state record, gated by surprisal (steal #13).

    The incoming text (the free summary, else the transcript tail) is embedded and
    compared to the agent's own owner/<agent> records BEFORE any LLM call:
    skip a near-duplicate, write the middle band (or a short capture) verbatim,
    distil only what is novel AND long. A transcript-only capture (no free summary)
    can only be skipped or distilled — a raw transcript is not a state record. See Settings.capture_* for the thresholds.
    """
    cfg = store.settings
    summary = (summary or "").strip()
    transcript = (transcript or "").strip()
    text = summary or transcript[-GATE_PROBE_CHARS:]
    if len(text) < 20:
        return {"captured": False, "reason": "no durable signal"}
    doc_id = f"owner-{agent}-current-state"
    existing = store.get(doc_id)
    nearest = store.nearest_owner_record(
        f"owner/{agent.lower()}", f"# {agent} — current state ({reason})\n\n{text}"
    )
    max_cos = nearest["cosine"] if nearest else None
    if (
        nearest
        and cfg.capture_skip_cosine < 1.0  # 1.0 disables the gate
        and max_cos > cfg.capture_skip_cosine
    ):
        decision = "skip"
    elif len(text) < cfg.capture_distil_min_chars or (
        max_cos is not None and max_cos >= cfg.capture_verbatim_cosine
    ):
        decision = "verbatim"
    else:
        decision = "distil"
    if decision == "verbatim" and not summary:
        decision = "distil"  # a raw transcript is never a state record: no free summary → distil
    counts = store.log_capture_decision(
        agent, decision, max_cos, nearest["ext_id"] if nearest else None, len(text)
    )
    gate = {
        "decision": decision,
        "max_cos": None if max_cos is None else round(max_cos, 4),
        "counts": counts,
    }
    if decision == "skip":
        return {
            "captured": False,
            "reason": "near-duplicate",
            "nearest_doc_id": nearest["ext_id"],
            **gate,
        }
    if decision == "distil":
        # Summary path distils the (long, novel) summary; transcript path distils the
        # transcript. Both merge the prior state forward. No key / error → the
        # summary is kept as-is; a transcript with no distillation captures nothing.
        prior = existing.content if existing else ""
        distilled = distil_summary(summary or transcript, prior=prior)
        summary = distilled or summary
    if len(summary) < 20:
        return {"captured": False, "reason": "no durable signal", **gate}
    content = f"# {agent} — current state ({reason})\n\n{summary}"
    store.put(
        content,
        kind="record",
        ext_id=doc_id,
        # lower-cased so the owner tag matches /api/boot's scope regardless of
        # the agent name's case (the store lower-cases tags on write anyway).
        tags=[f"owner/{agent.lower()}", "type/current-state", f"capture/{reason}"],
    )
    from .tokens import count_tokens

    return {"captured": True, "doc_id": doc_id, "tokens": count_tokens(content), **gate}
