"""Blind-judged eval harness (TSU-eval-harness) — borrows the i-have-adhd evals/ design:
a versioned `cases.jsonl`, a weighted rubric score, a $ budget, resumability, and a release
gate. Ties together retrieval_eval (IR metrics, no LLM) + eval_rubric (blind weighted judge,
needs an LLM) into one runnable, gate-able report over ONE case set.

Runner isolation: this module never reads ambient config (no ~/.claude, no CLAUDE.md, no env
lookups of its own) — the model is a parameter the caller must pass explicitly (pinned, not
env-sniffed), and the index it searches is built fresh into a throwaway dir by the caller
(see cli.py's `eval` command), so a run never inherits stray state from the host.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .eval_bench import EvalQuery
from .eval_rubric import RubricScore
from .retrieval_eval import LabeledQuery, RetrievalStats, evaluate_retrieval


@dataclass(frozen=True)
class EvalCase:
    """One pre-registered case: a query, its honest category, whether the answer lives in
    the corpus (False = a miss-case, the correct behavior is to abstain), and the doc(s)
    that correctly answer it (empty for a miss-case — there is nothing to route to)."""

    query: str
    category: str
    in_corpus: bool = True
    expected_docs: list[str] = field(default_factory=list)

    def as_labeled_query(self) -> LabeledQuery:
        return LabeledQuery(self.query, list(self.expected_docs))

    def as_eval_query(self) -> EvalQuery:
        return EvalQuery(self.query, self.category, in_corpus=self.in_corpus)


def load_cases(path: Path) -> list[EvalCase]:
    """One JSON object per line: {"query", "category", "in_corpus"?, "expected_docs"?}.
    Blank lines and `#`-prefixed comment lines are skipped."""
    cases: list[EvalCase] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        obj = json.loads(line)
        cases.append(
            EvalCase(
                query=obj["query"],
                category=obj["category"],
                in_corpus=obj.get("in_corpus", True),
                expected_docs=list(obj.get("expected_docs", [])),
            )
        )
    return cases


@dataclass
class CaseResult:
    query: str
    category: str
    rubric: RubricScore


@dataclass
class CategoryScore:
    category: str
    n: int
    mean_weighted: float


@dataclass
class HarnessReport:
    n_cases: int
    n_scored: int  # rubric-judged this run or resumed from a prior run
    n_pending: int  # not yet scored (budget-stopped) — never silently dropped
    mean_weighted: float | None  # None when n_scored == 0
    per_category: list[CategoryScore]
    retrieval: RetrievalStats
    results: list[CaseResult]


def _load_resume(resume_path: Path | None) -> dict[str, CaseResult]:
    if resume_path is None or not resume_path.exists():
        return {}
    done: dict[str, CaseResult] = {}
    for raw in resume_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        obj = json.loads(raw)
        r = obj["rubric"]
        done[obj["query"]] = CaseResult(
            query=obj["query"],
            category=obj["category"],
            rubric=RubricScore(
                correctness=r["correctness"],
                autonomy=r["autonomy"],
                actionability=r["actionability"],
                safety=r["safety"],
                concision=r["concision"],
                raw=r.get("raw", ""),
            ),
        )
    return done


def _append_resume(resume_path: Path | None, result: CaseResult) -> None:
    if resume_path is None:
        return
    row = {
        "query": result.query,
        "category": result.category,
        "rubric": {
            "correctness": result.rubric.correctness,
            "autonomy": result.rubric.autonomy,
            "actionability": result.rubric.actionability,
            "safety": result.rubric.safety,
            "concision": result.rubric.concision,
            "raw": result.rubric.raw,
        },
    }
    with resume_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def run_harness(
    cases: list[EvalCase],
    searcher,
    *,
    answer_fn: Callable[[str, str], tuple[str, int]] | None = None,
    judge_fn: Callable[[EvalQuery, str], RubricScore] | None = None,
    content_fn: Callable[[object], str] | None = None,
    k: int = 5,
    rerank: bool = False,
    budget_usd: float | None = None,
    cost_per_case_usd: float = 0.002,
    resume_path: Path | None = None,
    retrieval_only: bool = False,
) -> HarnessReport:
    """Score `cases` on BOTH axes: retrieval quality (free, no LLM, always run in full) and
    the blind weighted rubric (LLM, the budgeted/resumable part).

    Resumable: a case already present in `resume_path` is reused, never re-judged (no
    double spend on a re-run). Budget: stops issuing NEW judge calls once the running
    estimate would exceed `budget_usd` — already-scored cases are kept, the rest are
    reported as `n_pending` (never silently dropped, so a re-run with more budget or a
    later `--resume` finishes them).

    `retrieval_only=True` skips the LLM rubric pass entirely (no answer_fn/judge_fn/content_fn
    call, no key needed) — the report comes back with n_scored=0 by design; gate on it with
    `gate_retrieval_only`, not `gate` (which treats n_scored==0 as a failure to score).
    """
    labeled = [c.as_labeled_query() for c in cases if c.expected_docs]
    retrieval = evaluate_retrieval(searcher, labeled, k=k, rerank=rerank)

    if retrieval_only:
        return HarnessReport(
            n_cases=len(cases),
            n_scored=0,
            n_pending=0,
            mean_weighted=None,
            per_category=[],
            retrieval=retrieval,
            results=[],
        )

    assert answer_fn is not None and judge_fn is not None and content_fn is not None, (
        "answer_fn/judge_fn/content_fn are required unless retrieval_only=True"
    )

    done = _load_resume(resume_path)
    results: list[CaseResult] = []
    spent = 0.0
    n_pending = 0
    for case in cases:
        if case.query in done:
            results.append(done[case.query])
            continue
        if budget_usd is not None and spent + cost_per_case_usd > budget_usd:
            n_pending += 1
            continue
        search_results = searcher.search(case.query, limit=max(k, 20) if rerank else max(k, 3))
        if rerank:
            from .rerank_local import rerank_results

            search_results = rerank_results(case.query, search_results, max(k, 3))
        context = content_fn(search_results[0]) if search_results else ""
        answer, _ans_tokens = answer_fn(case.query, context)
        score = judge_fn(case.as_eval_query(), answer)
        result = CaseResult(query=case.query, category=case.category, rubric=score)
        _append_resume(resume_path, result)
        results.append(result)
        spent += cost_per_case_usd

    n_scored = len(results)
    mean_weighted = sum(r.rubric.weighted for r in results) / n_scored if n_scored else None

    per_category: list[CategoryScore] = []
    for cat in sorted({r.category for r in results}):
        rows = [r for r in results if r.category == cat]
        per_category.append(
            CategoryScore(category=cat, n=len(rows), mean_weighted=sum(r.rubric.weighted for r in rows) / len(rows))
        )

    return HarnessReport(
        n_cases=len(cases),
        n_scored=n_scored,
        n_pending=n_pending,
        mean_weighted=mean_weighted,
        per_category=per_category,
        retrieval=retrieval,
        results=results,
    )


def gate(report: HarnessReport, baseline: dict) -> tuple[bool, str]:
    """Compare a report against a baseline file's thresholds. `baseline` = {"min_weighted":
    float, "min_hit_at_1": float}. Fails closed: no scored cases, or missing/unmeasurable
    metrics, is NOT a pass."""
    if report.n_scored == 0:
        return False, "no cases scored (nothing to gate on)"
    if report.n_pending:
        return False, f"{report.n_pending} case(s) still pending (budget-stopped) — resume before gating"

    min_weighted = float(baseline.get("min_weighted", 0))
    min_hit_at_1 = float(baseline.get("min_hit_at_1", 0))
    reasons = []
    if report.mean_weighted is None or report.mean_weighted < min_weighted:
        reasons.append(f"weighted score {report.mean_weighted} < baseline {min_weighted}")
    if report.retrieval.hit_at_1 < min_hit_at_1:
        reasons.append(f"hit@1 {report.retrieval.hit_at_1:.2f} < baseline {min_hit_at_1}")
    if reasons:
        return False, "; ".join(reasons)
    return True, "ok"


def gate_retrieval_only(report: HarnessReport, baseline: dict) -> tuple[bool, str]:
    """Gate on retrieval quality alone — for a `retrieval_only=True` report, where n_scored
    is always 0 by design (no LLM ran), not a failure to score. No key needed, CI-safe."""
    min_hit_at_1 = float(baseline.get("min_hit_at_1", 0))
    if report.retrieval.hit_at_1 < min_hit_at_1:
        return False, f"hit@1 {report.retrieval.hit_at_1:.2f} < baseline {min_hit_at_1}"
    return True, "ok"


def format_harness_report(report: HarnessReport) -> str:
    lines = [
        f"eval harness: {report.n_scored}/{report.n_cases} scored"
        + (f" ({report.n_pending} pending — budget-stopped)" if report.n_pending else ""),
        f"retrieval: hit@1={report.retrieval.hit_at_1:.2f} hit@{report.retrieval.k}="
        f"{report.retrieval.hit_at_k:.2f} MRR={report.retrieval.mrr:.3f} "
        f"recall@{report.retrieval.k}={report.retrieval.recall_at_k:.2f}",
    ]
    if report.mean_weighted is not None:
        lines.append(f"rubric weighted score: {report.mean_weighted:.1f}/100")
        for c in report.per_category:
            lines.append(f"  {c.category}: n={c.n} weighted={c.mean_weighted:.1f}")
    return "\n".join(lines)
