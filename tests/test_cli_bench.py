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
