"""`trovex import --dry-run` (task 7111f05a): this was the exact repro that
crashed on every real install — `from . import onboarding` inside
cli.py's _scan_dir, onboarding.py never committed."""

from __future__ import annotations

from typer.testing import CliRunner

from trovex.cli import app

runner = CliRunner()


def test_import_dry_run_exits_zero_on_fixture_dir(tmp_path, monkeypatch):
    src = tmp_path / "notes"
    src.mkdir()
    (src / "a.md").write_text("# Alpha\n\nsome content", encoding="utf-8")
    (src / "b.md").write_text("# Bravo\n\nmore content", encoding="utf-8")

    monkeypatch.setenv("TROVEX_DATA_DIR", str(tmp_path / "data"))

    result = runner.invoke(app, ["import", str(src), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "2" in result.output  # "Found 2 markdown files"
    assert "Re-run without --dry-run" in result.output
