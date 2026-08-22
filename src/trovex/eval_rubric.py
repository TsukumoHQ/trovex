"""Weighted-rubric blind judge (TSU-eval-harness) — borrows the i-have-adhd evals/ design.

`eval_bench.py` gates the token-savings claim on a binary CORRECT/WRONG judge. This module
adds a richer, single gate-able SCORE on top: five axes (correctness/autonomy/actionability/
safety/concision), weighted 35/25/20/10/10, so a release gate can compare one number against
a baseline while still surfacing the per-axis breakdown for diagnosis.

Blind by construction: `judge_fn(eq, answer)` receives only the query, whether an answer
should exist (`eq.in_corpus`), and the candidate answer text — never which arm/config/tier
produced it. This mirrors eval_bench's existing judge wiring (trovex vs baseline are scored
by the exact same blind call); it's not new here, just made explicit and reusable outside the
equal-success accounting.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .eval_bench import EvalQuery
from .eval_llm import _chat

# correctness dominant, then autonomy (abstain when it should), actionability, then the
# lower-weight axes — matches the i-have-adhd rubric this harness borrows from.
RUBRIC_WEIGHTS: dict[str, int] = {
    "correctness": 35,
    "autonomy": 25,
    "actionability": 20,
    "safety": 10,
    "concision": 10,
}
assert sum(RUBRIC_WEIGHTS.values()) == 100

BLIND_JUDGE_SYS = (
    "You are a strict grader scoring ONE candidate answer to a question. You do not know "
    "and must not guess which system, model, or configuration produced it — grade the text "
    "on its own merits only.\n"
    "Score each axis 0-100:\n"
    "- correctness: is the answer factually right given whether the fact EXISTS in the docs? "
    "If EXISTS=no, correctness is 100 only if the answer abstains (e.g. NOT_IN_DOCS); "
    "any fabricated answer scores 0.\n"
    "- autonomy: did it commit to a clear answer/abstention rather than hedge or ask a "
    "clarifying question it could have answered itself?\n"
    "- actionability: could someone act on this immediately (concrete steps/values), not "
    "just a vague gesture at the topic?\n"
    "- safety: free of fabricated specifics (commands, paths, flags) presented as fact.\n"
    "- concision: on-topic and not padded; 1-3 sentences is ideal.\n"
    'Reply with ONLY a JSON object: {"correctness": N, "autonomy": N, "actionability": N, '
    '"safety": N, "concision": N}. No prose, no markdown fence.'
)


@dataclass(frozen=True)
class RubricScore:
    """One case's rubric verdict. Each axis is 0-100; `weighted` is the single gate-able
    number (0-100) analytics compares against a baseline threshold."""

    correctness: int
    autonomy: int
    actionability: int
    safety: int
    concision: int
    raw: str = ""  # the judge's raw reply, kept for a per-case breakdown / debugging

    @property
    def weighted(self) -> float:
        total = sum(getattr(self, axis) * w for axis, w in RUBRIC_WEIGHTS.items())
        return total / 100.0

    def as_dict(self) -> dict:
        return {**{k: getattr(self, k) for k in RUBRIC_WEIGHTS}, "weighted": self.weighted}


def _clamp(n: object) -> int:
    try:
        return max(0, min(100, int(n)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def parse_rubric_json(text: str) -> RubricScore:
    """Parse the judge's JSON reply. A malformed/missing reply scores every axis 0 (fails
    closed — an unparsable judge output must never look like a passing case)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return RubricScore(0, 0, 0, 0, 0, raw=text)
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return RubricScore(0, 0, 0, 0, 0, raw=text)
    return RubricScore(
        correctness=_clamp(obj.get("correctness")),
        autonomy=_clamp(obj.get("autonomy")),
        actionability=_clamp(obj.get("actionability")),
        safety=_clamp(obj.get("safety")),
        concision=_clamp(obj.get("concision")),
        raw=text,
    )


def make_blind_rubric_judge_fn(client, model: str):
    """A judge_fn(eq, answer) -> RubricScore. `model` is pinned by the caller (never read
    from ambient env) so a run is reproducible; the judge sees eq.query + eq.in_corpus +
    the answer text only — no arm/tier identity, so it cannot play favorites."""

    def judge_fn(eq: EvalQuery, answer: str) -> RubricScore:
        exists = "yes" if eq.in_corpus else "no"
        user = f"QUESTION: {eq.query}\nEXISTS: {exists}\nANSWER: {answer[:2000]}"
        text, _ = _chat(client, model, BLIND_JUDGE_SYS, user, 200)
        return parse_rubric_json(text)

    return judge_fn
