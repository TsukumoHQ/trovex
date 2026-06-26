"""Answer+judge benchmark eval — the integrity spine of TSU-42 (back the ~60% claim).

The token MODEL (`benchmark.py`) counts avoided reads; it does NOT verify the answer is
still correct. THIS module adds the gate analytics requires (guard 3): for each query,
both arms are ANSWERED and JUDGED, and a token saving is counted ONLY when BOTH arms
succeed (EQUAL task-success). A token cut that breaks the answer is NOT a win — it's a
LOSS, and is reported loudly per category (esp. C6 miss-cases, C7 ambiguous).

This file is the pure ACCOUNTING + REPORTING core (no LLM, no retrieval) so it's fully
hermetic-testable. The LLM-in-loop driver (answer_fn + judge_fn + doc retrieval + the
trovex-vs-baseline arms) wires on top and feeds `QueryEval`s in. Categories C1-C8 per
analytics' taxonomy; the published number is the equal-success median + spread.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median, quantiles

# Analytics' representative taxonomy (the set must cover all 8, weighted to real frequency).
CATEGORIES = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")


@dataclass(frozen=True)
class ArmResult:
    """One arm's outcome on one query. `tokens` = the FULL cost we compare: context fed
    to the model + answer tokens + (trovex only) routing/index overhead."""

    correct: bool
    tokens: int


@dataclass(frozen=True)
class QueryEval:
    """One query scored on both arms. `trovex` = the 1 routed canonical doc; `baseline` =
    the realistic alternative (full read of the top-k candidates), same model + judge."""

    query: str
    category: str
    trovex: ArmResult
    baseline: ArmResult

    @property
    def equal_success(self) -> bool:
        return self.trovex.correct and self.baseline.correct

    @property
    def trovex_only_win(self) -> bool:
        return self.trovex.correct and not self.baseline.correct

    @property
    def trovex_loss(self) -> bool:
        """Baseline answered, trovex did not — a quality LOSS (what guard 3 catches)."""
        return self.baseline.correct and not self.trovex.correct

    @property
    def saving_ratio(self) -> float | None:
        """Token saving, counted ONLY at equal success. None otherwise (don't count a
        win where the routed answer was wrong)."""
        if not self.equal_success or self.baseline.tokens <= 0:
            return None
        return max(0.0, (self.baseline.tokens - self.trovex.tokens) / self.baseline.tokens)


@dataclass
class CategoryStats:
    category: str
    n: int  # total queries in the category
    n_equal_success: int  # both arms correct → counted toward the number
    n_trovex_only_win: int  # trovex right, baseline wrong
    n_trovex_loss: int  # baseline right, trovex wrong (LOSS — must surface)
    median_saving: float | None  # equal-success median
    p25: float | None
    p75: float | None


@dataclass
class EvalReport:
    n_queries: int
    n_equal_success: int
    n_trovex_loss: int  # total quality losses across all categories
    median_saving: float | None  # overall, equal-success only
    p25: float | None
    p75: float | None
    per_category: list[CategoryStats]


def _dist(ratios: list[float]) -> tuple[float | None, float | None, float | None]:
    if not ratios:
        return None, None, None
    med = median(ratios)
    if len(ratios) >= 2:
        q1, _q2, q3 = quantiles(sorted(ratios), n=4)
        return med, q1, q3
    return med, med, med


def aggregate(evals: list[QueryEval]) -> EvalReport:
    """Equal-success-gated distribution, overall + per category (incl. where trovex LOSES).
    The honest number = the overall equal-success median; losses are first-class, not hidden."""
    per_cat: list[CategoryStats] = []
    for cat in CATEGORIES:
        ce = [e for e in evals if e.category == cat]
        if not ce:
            continue
        ratios = [e.saving_ratio for e in ce if e.saving_ratio is not None]
        med, p25, p75 = _dist(ratios)
        per_cat.append(
            CategoryStats(
                category=cat,
                n=len(ce),
                n_equal_success=sum(1 for e in ce if e.equal_success),
                n_trovex_only_win=sum(1 for e in ce if e.trovex_only_win),
                n_trovex_loss=sum(1 for e in ce if e.trovex_loss),
                median_saving=med,
                p25=p25,
                p75=p75,
            )
        )

    all_ratios = [e.saving_ratio for e in evals if e.saving_ratio is not None]
    med, p25, p75 = _dist(all_ratios)
    return EvalReport(
        n_queries=len(evals),
        n_equal_success=sum(1 for e in evals if e.equal_success),
        n_trovex_loss=sum(1 for e in evals if e.trovex_loss),
        median_saving=med,
        p25=p25,
        p75=p75,
        per_category=per_cat,
    )


def format_eval_report(r: EvalReport, *, query_source: str = "") -> str:
    """Honest report: the equal-success number + spread, the n, and the LOSSES per category.
    Never a bare median without the success-rate + loss context."""
    pct = lambda x: f"{x * 100:.0f}%" if x is not None else "n/a"  # noqa: E731
    lines = [
        "# trovex answer+judge eval (equal task-success)",
        "",
        "Token saving counted ONLY when BOTH arms answer correctly (same judge). A token",
        "cut that breaks the answer is a LOSS, surfaced below — not a win.",
        f"Query set: {query_source or '(unspecified — must be pre-registered + representative)'}",
        "",
        f"Queries: {r.n_queries}  |  equal-success (counted): {r.n_equal_success}  "
        f"|  trovex quality-losses: {r.n_trovex_loss}",
        f"**Median token saving at equal success: {pct(r.median_saving)}**  "
        f"(p25 {pct(r.p25)} – p75 {pct(r.p75)})",
        "",
        "Per category (n / equal-success / trovex-only-win / TROVEX-LOSS / median):",
    ]
    for c in r.per_category:
        lines.append(
            f"  {c.category}: n={c.n} eq={c.n_equal_success} win+={c.n_trovex_only_win} "
            f"LOSS={c.n_trovex_loss} median={pct(c.median_saving)}"
        )
    if r.n_trovex_loss:
        lines.append("")
        lines.append(f"⚠ {r.n_trovex_loss} quality-loss(es) — report these; they cap the honest claim.")
    return "\n".join(lines)
