"""`trovex bench` CLI — hermetic bits: query loading + the --eval key guard (which fires
BEFORE indexing, so no model download). The bench math itself is covered by test_benchmark
/ test_eval_bench."""

from __future__ import annotations

from typer.testing import CliRunner

from trovex.cli import _DEFAULT_QUERIES, _load_queries, app

runner = CliRunner()


def test_load_queries_default():
    assert _load_queries(None) == _DEFAULT_QUERIES
    assert len(_DEFAULT_QUERIES) >= 5


def test_load_queries_from_file(tmp_path):
    f = tmp_path / "q.txt"
    f.write_text("how do I install\n\n  what tests  \nhow to deploy\n", encoding="utf-8")
    assert _load_queries(f) == ["how do I install", "what tests", "how to deploy"]


def test_load_queries_missing_file(tmp_path):
    assert _load_queries(tmp_path / "nope.txt") == []


def test_bench_eval_requires_key(monkeypatch, tmp_path):
    # --eval without a key must fail fast (before the slow index), not crash later.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    res = runner.invoke(app, ["bench", "--eval", str(tmp_path)])
    assert res.exit_code == 1
    assert "OPENAI_API_KEY" in res.output


def test_bench_json_serializes_both_report_types():
    import json

    from trovex.benchmark import BenchResult
    from trovex.cli import _bench_json
    from trovex.eval_bench import CategoryStats, EvalReport

    br = BenchResult(
        n_queries=2, n_scored=2, median_ratio=0.6, p25_ratio=0.4, p75_ratio=0.8,
        total_saved=100, total_would_have_read=160, per_query=[{"query": "q", "ratio": 0.6}],
    )
    d = json.loads(_bench_json(br))
    assert d["median_ratio"] == 0.6 and d["per_query"][0]["query"] == "q"

    er = EvalReport(
        n_queries=1, n_equal_success=1, n_trovex_loss=0, median_saving=0.7, p25=0.7, p75=0.7,
        per_category=[CategoryStats("C1", 1, 1, 0, 0, 0.7, 0.7, 0.7)],
    )
    d2 = json.loads(_bench_json(er))
    assert d2["median_saving"] == 0.7 and d2["per_category"][0]["category"] == "C1"
