"""open_db — SQLite bootstrap, including the loadable-extension guard.

Some Python builds (pyenv / Homebrew on macOS) compile sqlite3 without
loadable-extension support, so `enable_load_extension` is missing and sqlite-vec
can't load. That must surface as an actionable RuntimeError on the first index,
not a raw AttributeError traceback (the classic cold-dev install wall).
"""

import pytest

import trovex.db as db


def test_open_db_reports_missing_extension_support(tmp_path, monkeypatch):
    class _FakeConn:
        def __init__(self):
            self.row_factory = None

        def execute(self, *a, **k):
            return self

        def enable_load_extension(self, *a):
            raise AttributeError("enable_load_extension")

    monkeypatch.setattr(db.sqlite3, "connect", lambda *a, **k: _FakeConn())

    with pytest.raises(RuntimeError) as exc:
        db.open_db(tmp_path / "store.db")

    msg = str(exc.value)
    assert "loadable-extension" in msg
    assert "uv tool install" in msg  # points to the fix
