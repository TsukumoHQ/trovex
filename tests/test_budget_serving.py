"""Named acceptance tests for task 59e9ff0e budget-fitted serving."""

from __future__ import annotations

import pytest

from trovex.budget import BudgetCandidate, fit_budget


@pytest.mark.parametrize("budget", [200, 1000, 5000])
def test_budget_fitter_hits_50_record_fixture_within_fifteen_percent(budget):
    candidates = [
        BudgetCandidate(
            f"doc-{i}",
            {
                "stub": f"Document {i} — trovex:doc-{i}",
                "card": f"Document {i} — trovex:doc-{i}\n" + "summary " * 40,
                "passage": f"Document {i} — trovex:doc-{i}\n" + "passage detail " * 220,
            },
        )
        for i in range(50)
    ]

    fitted = fit_budget(candidates, budget)

    assert sum(result["tokens_est"] for result in fitted["results"]) == fitted["budget_used"]
    assert budget * 0.85 <= fitted["budget_used"] <= budget
    assert all(result["tier"] in {"stub", "card", "passage"} for result in fitted["results"])
    assert all(set(item) == {"doc_id", "tier"} for item in fitted["trimmed"])
