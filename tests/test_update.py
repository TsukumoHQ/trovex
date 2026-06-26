"""Auto-update check (TSU-65). Hermetic: fetch / now / cache_path are injected, so
no network and no real ~/.trovex-data are touched. Pins the guards: no-downgrade,
24h cache, offline fail-safe, opt-in upgrade command."""

from __future__ import annotations

from trovex.update import (
    CACHE_TTL,
    UpdateInfo,
    _parse,
    cached_notice,
    check_for_update,
    is_newer,
    notice_line,
    upgrade_command,
)


def test_parse_strips_v_and_metadata():
    assert _parse("v0.11.6") == (0, 11, 6)
    assert _parse("0.11.6+local.dirty") == (0, 11, 6)
    assert _parse("v1.2") == (1, 2)
    assert _parse("garbage") == (0,)


def test_is_newer_no_downgrade():
    assert is_newer("v0.11.7", "0.11.6") is True
    assert is_newer("0.11.6", "0.11.6") is False  # equal is not newer
    assert is_newer("0.11.5", "0.11.6") is False  # older never suggested (no downgrade)
    assert is_newer("v1.0.0", "0.11.6") is True


def test_check_reports_newer_and_writes_cache(tmp_path):
    cache = tmp_path / "u.json"
    info = check_for_update(now=1000.0, fetch=lambda: "v9.9.9", cache_path=cache)
    assert info is not None and info.newer is True and info.latest == "v9.9.9"
    assert cache.exists()  # result cached for next time


def test_offline_fetch_returns_none_no_raise(tmp_path):
    # fetch yields None (offline / GitHub down) → no info, no cache write, no exception.
    info = check_for_update(now=1.0, fetch=lambda: None, cache_path=tmp_path / "u.json")
    assert info is None
    assert not (tmp_path / "u.json").exists()


def test_fresh_cache_skips_network(tmp_path):
    cache = tmp_path / "u.json"
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return "v0.11.6"

    # First call hits the network + caches.
    check_for_update(now=1000.0, fetch=fetch, cache_path=cache)
    # Second call within TTL must NOT hit the network.
    check_for_update(now=1000.0 + CACHE_TTL - 1, fetch=fetch, cache_path=cache)
    assert calls["n"] == 1


def test_stale_cache_refetches(tmp_path):
    cache = tmp_path / "u.json"
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return "v0.11.6"

    check_for_update(now=1000.0, fetch=fetch, cache_path=cache)
    check_for_update(now=1000.0 + CACHE_TTL + 1, fetch=fetch, cache_path=cache)
    assert calls["n"] == 2


def test_force_bypasses_cache(tmp_path):
    cache = tmp_path / "u.json"
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return "v0.11.6"

    check_for_update(now=1000.0, fetch=fetch, cache_path=cache)
    check_for_update(now=1000.0, force=True, fetch=fetch, cache_path=cache)
    assert calls["n"] == 2


def test_notice_line():
    assert notice_line(UpdateInfo("0.11.6", "0.11.6", False)) is None
    line = notice_line(UpdateInfo("0.11.6", "v0.11.7", True))
    assert line is not None and "v0.11.7" in line and "0.11.6" in line


def test_upgrade_command_is_uv_or_pip():
    cmd = upgrade_command()
    assert cmd[:3] == ["uv", "tool", "upgrade"] or cmd[1:3] == ["-m", "pip"]
    assert "trovex" in cmd


def test_cached_notice_zero_network(tmp_path):
    cache = tmp_path / "u.json"
    # No cache yet → no notice, no network.
    assert cached_notice(cache_path=cache) is None
    # Seed a cache with a very high latest → notice appears, still no network.
    check_for_update(now=1.0, fetch=lambda: "v999.0.0", cache_path=cache)
    note = cached_notice(cache_path=cache)
    assert note is not None and "v999.0.0" in note


def test_cli_update_offline(monkeypatch):
    from typer.testing import CliRunner

    import trovex.cli as cli

    monkeypatch.setattr("trovex.update.check_for_update", lambda **k: None)
    res = CliRunner().invoke(cli.app, ["update", "--check"])
    assert res.exit_code == 0 and "offline" in res.output.lower()


def test_cli_update_check_reports_newer(monkeypatch):
    from typer.testing import CliRunner

    import trovex.cli as cli

    monkeypatch.setattr(
        "trovex.update.check_for_update", lambda **k: UpdateInfo("0.11.6", "v0.11.7", True)
    )
    res = CliRunner().invoke(cli.app, ["update", "--check"])
    assert res.exit_code == 0 and "v0.11.7" in res.output
