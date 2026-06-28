"""Server bind default is loopback, and an all-interfaces bind warns loudly.

The dashboard + query-log views (/usage, /insights) are read-open, so a public
bind exposes a team's query text. The safe default is 127.0.0.1; opting into
0.0.0.0 must surface a warning so it's never silent.
"""

from __future__ import annotations

import pytest

from trovex import cli
from trovex.config import Settings


def test_default_host_is_loopback(tmp_path):
    s = Settings(data_dir=tmp_path)
    assert s.host == "127.0.0.1"


def test_serve_command_default_host_is_loopback():
    # The `serve` CLI option default must match the Settings default (no silent 0.0.0.0).
    # typer wraps the default in an OptionInfo; read the declared default off it.
    import inspect

    host_opt = inspect.signature(cli.serve).parameters["host"].default
    assert getattr(host_opt, "default", host_opt) == "127.0.0.1"


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "[::]"])
def test_run_server_warns_on_all_interfaces(monkeypatch, host):
    import uvicorn

    # Stub build_app + uvicorn so the test never builds the real OpenAI embedder
    # (no OPENAI_API_KEY in CI) — we only assert the bind warning, not a live app.
    monkeypatch.setattr("trovex.server.build_app", lambda: object())
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
    printed: list[str] = []
    monkeypatch.setattr(cli.console, "print", lambda msg="", *a, **k: printed.append(str(msg)))

    cli._run_server(host, 8765)
    assert any("ALL interfaces" in m for m in printed)


def test_run_server_quiet_on_loopback(monkeypatch):
    import uvicorn

    monkeypatch.setattr("trovex.server.build_app", lambda: object())
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
    printed: list[str] = []
    monkeypatch.setattr(cli.console, "print", lambda msg="", *a, **k: printed.append(str(msg)))

    cli._run_server("127.0.0.1", 8765)
    assert not any("ALL interfaces" in m for m in printed)
