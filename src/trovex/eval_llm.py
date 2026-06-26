"""BYOK LLM answer/judge + content retrieval for the answer+judge eval (TSU-42).

Wires real functions into `eval_bench.eval_query`/`run_eval`:
- `answer_fn(query, context)` → answer the query from ONLY the context (abstain if absent).
- `judge_fn(eq, answer)` → CORRECT/WRONG, with abstain-correct for C6 miss-cases.
- `content_fn(result)` → the doc text behind a SearchResult.

Best-effort BYOK: the key comes from the caller's `OpenAI` client (built from env/header) —
this module never reads, logs, or inlines the key. gpt-5* vs legacy param shapes mirror
`capture.py`. The functions are injected, so the eval stays hermetic-testable elsewhere.
"""

from __future__ import annotations

from pathlib import Path

from .eval_bench import EvalQuery

ANSWER_SYS = (
    "Answer the QUESTION using ONLY the CONTEXT. Be concise (1-3 sentences). "
    "If the answer is not present in the CONTEXT, reply with exactly: NOT_IN_DOCS"
)
JUDGE_SYS = (
    "You are a strict grader. Given a QUESTION, a candidate ANSWER, and whether the answer "
    "EXISTS in the project's docs, output exactly one word: CORRECT or WRONG.\n"
    "- If EXISTS=no: CORRECT only if the ANSWER abstains (says it's not in the docs / "
    "NOT_IN_DOCS); WRONG if it makes up an answer.\n"
    "- If EXISTS=yes: CORRECT if the ANSWER is on-topic and factually answers the QUESTION; "
    "WRONG if it abstains, is empty, or is incorrect."
)


def _chat(client, model: str, system: str, user: str, max_tok: int) -> tuple[str, int]:
    """One chat call → (text, completion_tokens). gpt-5*/o-series drop temperature + use
    max_completion_tokens (mirrors capture.py)."""
    params: dict = {"model": model, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]}
    if model.startswith(("gpt-5", "o1", "o3", "o4")):
        params["max_completion_tokens"] = max_tok
    else:
        params["max_tokens"] = max_tok
        params["temperature"] = 0
    resp = client.chat.completions.create(**params)
    text = (resp.choices[0].message.content or "").strip()
    comp = resp.usage.completion_tokens if getattr(resp, "usage", None) else max(1, len(text) // 4)
    return text, comp


def make_answer_fn(client, model: str, *, max_context_chars: int = 12000):
    def answer_fn(query: str, context: str) -> tuple[str, int]:
        if not context.strip():
            return "NOT_IN_DOCS", 3
        user = f"CONTEXT:\n{context[:max_context_chars]}\n\nQUESTION: {query}"
        return _chat(client, model, ANSWER_SYS, user, 512)

    return answer_fn


def make_judge_fn(client, model: str):
    def judge_fn(eq: EvalQuery, answer: str) -> bool:
        exists = "yes" if eq.in_corpus else "no"
        user = f"QUESTION: {eq.query}\nEXISTS: {exists}\nANSWER: {answer[:2000]}"
        verdict, _ = _chat(client, model, JUDGE_SYS, user, 8)
        return verdict.upper().startswith("CORRECT")

    return judge_fn


def make_content_fn():
    """Read a SearchResult's doc text from disk (the indexed `.md`). Best-effort."""

    def content_fn(result) -> str:
        try:
            return Path(result.absolute_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    return content_fn
