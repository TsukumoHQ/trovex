"""Weighted-rubric blind judge (eval_rubric). Hermetic — fake OpenAI client, no network.
Asserts: RUBRIC_WEIGHTS sums to 100, weighted-score arithmetic, JSON parsing fails closed
on garbage/partial/out-of-range input, and the judge_fn round-trips through a fake client
without leaking arm/config identity into the prompt."""

from __future__ import annotations

from trovex.eval_bench import EvalQuery
from trovex.eval_rubric import RUBRIC_WEIGHTS, RubricScore, make_blind_rubric_judge_fn, parse_rubric_json


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


def test_rubric_weights_sum_to_100():
    assert sum(RUBRIC_WEIGHTS.values()) == 100


def test_weighted_arithmetic():
    s = RubricScore(correctness=100, autonomy=100, actionability=100, safety=100, concision=100)
    assert s.weighted == 100.0
    s2 = RubricScore(correctness=0, autonomy=0, actionability=0, safety=0, concision=0)
    assert s2.weighted == 0.0
    # correctness (35) dominant: a perfect correctness score alone outweighs the rest combined.
    s3 = RubricScore(correctness=100, autonomy=0, actionability=0, safety=0, concision=0)
    assert s3.weighted == 35.0


def test_as_dict_includes_weighted():
    s = RubricScore(correctness=80, autonomy=60, actionability=40, safety=20, concision=0)
    d = s.as_dict()
    assert d["weighted"] == s.weighted
    assert set(d) == {"correctness", "autonomy", "actionability", "safety", "concision", "weighted"}


def test_parse_valid_json():
    s = parse_rubric_json(
        '{"correctness": 90, "autonomy": 80, "actionability": 70, "safety": 100, "concision": 60}'
    )
    assert (s.correctness, s.autonomy, s.actionability, s.safety, s.concision) == (90, 80, 70, 100, 60)


def test_parse_json_embedded_in_prose():
    s = parse_rubric_json(
        'Sure, here is my grading:\n{"correctness": 50, "autonomy": 50, "actionability": 50, '
        '"safety": 50, "concision": 50}\nHope that helps.'
    )
    assert s.correctness == 50


def test_parse_garbage_fails_closed():
    s = parse_rubric_json("not json at all")
    assert (s.correctness, s.autonomy, s.actionability, s.safety, s.concision) == (0, 0, 0, 0, 0)
    assert s.raw == "not json at all"


def test_parse_malformed_json_fails_closed():
    s = parse_rubric_json('{"correctness": 90, "autonomy": }')
    assert s.weighted == 0.0


def test_parse_partial_fields_missing_default_to_zero():
    s = parse_rubric_json('{"correctness": 90}')
    assert s.correctness == 90
    assert s.autonomy == 0 and s.actionability == 0 and s.safety == 0 and s.concision == 0


def test_parse_out_of_range_clamped():
    s = parse_rubric_json(
        '{"correctness": 150, "autonomy": -20, "actionability": "bad", "safety": 50, "concision": 50}'
    )
    assert s.correctness == 100  # clamped down
    assert s.autonomy == 0  # clamped up from negative
    assert s.actionability == 0  # unparsable -> 0, not a crash


def test_judge_fn_round_trip_and_blind_prompt():
    c = FakeClient('{"correctness": 90, "autonomy": 80, "actionability": 70, "safety": 90, "concision": 60}')
    judge = make_blind_rubric_judge_fn(c, "gpt-5.4-mini")
    score = judge(EvalQuery("how do I create an api token", "C1"), "Run `trovex token create`.")
    assert score.correctness == 90
    assert score.weighted > 0
    params = c.calls[0]
    user_content = params["messages"][-1]["content"]
    assert "how do I create an api token" in user_content
    assert "EXISTS: yes" in user_content
    # blind: the prompt never mentions an arm/config/tier identity.
    assert "trovex" not in params["messages"][0]["content"].lower()
    assert "baseline" not in params["messages"][0]["content"].lower()


def test_judge_fn_passes_exists_no_for_miss_case():
    c = FakeClient('{"correctness": 100, "autonomy": 100, "actionability": 100, "safety": 100, "concision": 100}')
    judge = make_blind_rubric_judge_fn(c, "gpt-5.4-mini")
    judge(EvalQuery("how do I set up SSO with Okta", "C6", in_corpus=False), "NOT_IN_DOCS")
    assert "EXISTS: no" in c.calls[0]["messages"][-1]["content"]
