"""BYOK answer/judge/content wiring (eval_llm). Hermetic — fake OpenAI client, no network,
no key. Asserts: empty context abstains without a call; gpt-5* vs legacy param shapes;
judge CORRECT/WRONG + EXISTS plumbing; content_fn reads disk / degrades."""

from __future__ import annotations

from trovex.eval_bench import EvalQuery
from trovex.eval_llm import make_answer_fn, make_content_fn, make_judge_fn


class _Msg:
    def __init__(self, c):
        self.content = c


class _Choice:
    def __init__(self, c):
        self.message = _Msg(c)


class _Usage:
    completion_tokens = 11


class _Resp:
    def __init__(self, c):
        self.choices = [_Choice(c)]
        self.usage = _Usage()


class FakeClient:
    def __init__(self, content):
        self._content = content
        self.calls = []

        outer = self

        class _Completions:
            def create(self, **params):
                outer.calls.append(params)
                return _Resp(outer._content)

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def test_answer_empty_context_abstains_without_call():
    c = FakeClient("should-not-be-used")
    ans, tok = make_answer_fn(c, "gpt-5.4-mini")("q", "   ")
    assert ans == "NOT_IN_DOCS" and tok == 3
    assert c.calls == []  # no API call on empty context


def test_answer_gpt5_param_shape():
    c = FakeClient("trovex uses bge-small.")
    ans, tok = make_answer_fn(c, "gpt-5.4-mini")("model?", "context: bge-small")
    assert ans == "trovex uses bge-small." and tok == 11
    p = c.calls[0]
    assert "max_completion_tokens" in p and "temperature" not in p


def test_answer_legacy_param_shape():
    c = FakeClient("ans")
    make_answer_fn(c, "gpt-4o-mini")("q", "ctx")
    p = c.calls[0]
    assert p["max_tokens"] == 512 and p["temperature"] == 0


def test_judge_parses_and_passes_exists():
    yes = FakeClient("CORRECT")
    assert make_judge_fn(yes, "gpt-5.4-mini")(EvalQuery("q", "C1"), "a good answer") is True
    assert yes.calls[0]["messages"][-1]["content"].find("EXISTS: yes") != -1
    no = FakeClient("WRONG")
    assert make_judge_fn(no, "gpt-5.4-mini")(EvalQuery("q", "C6", in_corpus=False), "made up") is False
    assert no.calls[0]["messages"][-1]["content"].find("EXISTS: no") != -1


def test_content_fn_reads_and_degrades(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# Hello\n\nbody", encoding="utf-8")

    class R:
        absolute_path = str(f)

    class Missing:
        absolute_path = str(tmp_path / "nope.md")

    cf = make_content_fn()
    assert "Hello" in cf(R())
    assert cf(Missing()) == ""  # best-effort
