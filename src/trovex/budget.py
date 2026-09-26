"""Token-budget fitting for ranked, graduated retrieval results."""

from __future__ import annotations

from dataclasses import dataclass

from .tokens import count_tokens

TIERS = ("stub", "card", "passage")


@dataclass(frozen=True)
class BudgetCandidate:
    doc_id: str
    variants: dict[str, str]


def fit_budget(candidates: list[BudgetCandidate], budget: int) -> dict:
    """Fit a ranked prefix, then spend remaining budget upgrading its tiers.

    Prefix size is found by binary search at the cheapest (stub) tier. Upgrades
    preserve ranking and are atomic, so the result never exceeds ``budget``.
    """
    costs = [{tier: count_tokens(c.variants[tier]) for tier in TIERS} for c in candidates]

    def prefix_cost(count: int) -> int:
        return sum(costs[i]["stub"] for i in range(count))

    lo, hi = 0, len(candidates)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if prefix_cost(mid) <= budget:
            lo = mid
        else:
            hi = mid - 1

    selected_tiers = ["stub"] * lo
    used = prefix_cost(lo)
    for tier in TIERS[1:]:
        for i in range(lo):
            current = selected_tiers[i]
            extra = costs[i][tier] - costs[i][current]
            if extra <= budget - used:
                selected_tiers[i] = tier
                used += extra

    selected = [
        {
            "doc_id": candidates[i].doc_id,
            "tier": tier,
            "text": candidates[i].variants[tier],
            "tokens_est": costs[i][tier],
        }
        for i, tier in enumerate(selected_tiers)
    ]
    trimmed: list[dict[str, str]] = []
    for i, candidate in enumerate(candidates):
        if i >= lo:
            trimmed.append({"doc_id": candidate.doc_id, "tier": "stub"})
            continue
        chosen = selected_tiers[i]
        chosen_index = TIERS.index(chosen)
        for dropped in TIERS[chosen_index + 1 :]:
            trimmed.append({"doc_id": candidate.doc_id, "tier": dropped})

    return {
        "budget_requested": budget,
        "budget_used": used,
        "results": selected,
        "trimmed": trimmed,
    }
