"""eval_bench accounting (TSU-42 spine). The load-bearing assertion: a token cut that
breaks the answer is NOT a win — saving is counted ONLY at equal task-success, and a
trovex-wrong/baseline-right query is a reported LOSS. Pure, no LLM."""

from __future__ import annotations

from trovex.eval_bench import (
    ArmResult,
    QueryEval,
    aggregate,
    format_eval_report,
)


def _q(cat, t_correct, t_tok, b_correct, b_tok, query="q"):
    return QueryEval(
        query=query,
        category=cat,
        trovex=ArmResult(correct=t_correct, tokens=t_tok),
        baseline=ArmResult(correct=b_correct, tokens=b_tok),
    )


def test_saving_counted_only_at_equal_success():
    e = _q("C1", True, 100, True, 300)  # both correct
    assert e.equal_success
    assert abs(e.saving_ratio - (200 / 300)) < 1e-9  # ~0.67


def test_fewer_tokens_but_wrong_is_not_a_win():
    # trovex reads less (50) but is WRONG; baseline correct. The gate: NOT counted, and a LOSS.
    e = _q("C7", False, 50, True, 300)
    assert e.saving_ratio is None  # not counted toward the number
    assert e.trovex_loss is True
    assert e.equal_success is False


def test_trovex_only_win_not_counted_as_saving():
    # trovex right, baseline wrong → a quality win for trovex, but NOT an equal-success token saving.
    e = _q("C8", True, 100, False, 300)
    assert e.trovex_only_win is True
    assert e.saving_ratio is None
    assert e.trovex_loss is False


def test_miss_case_both_abstain_counts_as_equal_success():
    # C6: answer not in corpus. Both correctly abstain (correct=True). Near-zero saving is fine.
    e = _q("C6", True, 40, True, 60)
    assert e.equal_success
    assert e.saving_ratio is not None and e.saving_ratio >= 0.0


def test_aggregate_gates_and_surfaces_losses():
    evals = [
        _q("C1", True, 100, True, 300),   # counted, ~0.67
        _q("C1", True, 200, True, 400),   # counted, 0.50
        _q("C7", False, 50, True, 300),   # LOSS, not counted
        _q("C8", True, 80, False, 300),   # trovex-only win, not counted
        _q("C6", True, 40, True, 50),     # counted, 0.20
    ]
    r = aggregate(evals)
    assert r.n_queries == 5
    assert r.n_equal_success == 3            # C1x2 + C6
    assert r.n_trovex_loss == 1              # the C7 loss is surfaced
    assert r.median_saving is not None and 0.0 <= r.median_saving <= 1.0
    cats = {c.category: c for c in r.per_category}
    assert cats["C7"].n_trovex_loss == 1
    assert cats["C8"].n_trovex_only_win == 1
    assert cats["C1"].n_equal_success == 2


def test_report_states_number_losses_and_equal_success():
    r = aggregate([_q("C1", True, 100, True, 300), _q("C7", False, 50, True, 300)])
    out = format_eval_report(r, query_source="test set (NOT pre-registered)")
    assert "equal task-success" in out
    assert "Median token saving at equal success" in out
    assert "LOSS" in out and "quality-loss" in out  # losses surfaced, not hidden
