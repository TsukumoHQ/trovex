"""Tag-based update check for the trovex CLI (TSU-65: all tools auto-update on a new tag).

Fail-safe by construction: any error (offline, GitHub down, bad JSON) returns no
update info and NEVER raises — a version check must never block or slow the CLI.
It checks GitHub's latest release tag at most once per ``CACHE_TTL`` (cached on
disk), only ever reports an UPGRADE (never a downgrade), and is pinned to the
``TsukumoHQ/trovex`` repo. The upgrade itself is opt-in (``trovex update`` or the
printed command) — we never mutate the user's environment behind their back.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# Pinned — the update source is never user-configurable (supply-chain guard).
REPO = "TsukumoHQ/trovex"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
CACHE_TTL = 24 * 3600  # check the network at most once per 24h
HTTP_TIMEOUT = 3.0  # seconds — short, so a slow/blocked GitHub never hangs the CLI


@dataclass
class UpdateInfo:
    installed: str
    latest: str
    newer: bool  # latest is strictly greater than installed (never a downgrade)


def installed_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("trovex")
    except PackageNotFoundError:
        return "0.0.0"


def _parse(v: str) -> tuple[int, ...]:
    """'v0.11.6' / '0.11.6+local' → (0, 11, 6). Best-effort; stops at the first
    non-numeric component so pre/build metadata can't crash the comparison."""
    core = v.strip().lstrip("vV").split("+")[0].split("-")[0]
    parts: list[int] = []
    for p in core.split("."):
        if p.isdigit():
            parts.append(int(p))
        else:
            break
    return tuple(parts) or (0,)


def is_newer(latest: str, installed: str) -> bool:
    """True only when latest > installed — the no-downgrade guard."""
    return _parse(latest) > _parse(installed)


def is_dev_build(version: str) -> bool:
    """True if the installed version looks like a dev / source / editable build
    (hatch-vcs ``.devN``, a local ``+g<hash>``, or a ``dirty`` marker). The
    auto-updater refuses to clobber such a build unless ``--force`` (wraith
    contract point 4 — protect contributors running from source)."""
    v = version.lower()
    return "dev" in v or "+" in v or "dirty" in v or bool(re.search(r"g[0-9a-f]{7}", v))


def _default_cache_path() -> Path:
    return Path.home() / ".trovex-data" / "update-check.json"


def _read_cache(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_cache(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass  # cache is best-effort; a write failure must not break anything


def _fetch_latest_tag(timeout: float = HTTP_TIMEOUT) -> str | None:
    """GitHub's latest release tag_name, or None on ANY failure (offline-safe)."""
    try:
        req = urllib.request.Request(
            LATEST_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "trovex-update-check",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (pinned https)
            data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name")
        return tag if isinstance(tag, str) and tag else None
    except Exception:
        # Offline, DNS failure, rate-limit, malformed JSON — all must be silent.
        return None


def check_for_update(
    *,
    now: float | None = None,
    force: bool = False,
    fetch=_fetch_latest_tag,
    cache_path: Path | None = None,
) -> UpdateInfo | None:
    """Return UpdateInfo when a result is available, else None (offline / no data).

    Honors the 24h on-disk cache unless ``force=True``. Never raises. ``now``,
    ``fetch`` and ``cache_path`` are injectable so the whole flow is hermetic in tests.
    """
    now = time.time() if now is None else now
    path = cache_path or _default_cache_path()
    installed = installed_version()

    if not force:
        cached = _read_cache(path)
        if (
            cached
            and isinstance(cached.get("ts"), (int, float))
            and (now - cached["ts"]) < CACHE_TTL
        ):
            latest = cached.get("latest")
            if isinstance(latest, str):
                return UpdateInfo(installed, latest, is_newer(latest, installed))
            return None

    latest = fetch()
    if latest is None:
        return None  # offline / GitHub down — no nag, no error
    _write_cache(path, {"ts": now, "latest": latest})
    return UpdateInfo(installed, latest, is_newer(latest, installed))


def upgrade_command() -> list[str]:
    """Best-effort upgrade command: ``uv tool upgrade`` when trovex runs from a uv
    tool install, else pip. Honest fallback — the user can always run it by hand."""
    import sys

    exe = (sys.executable or "").replace("\\", "/")
    if "uv/tools" in exe or "/tools/trovex" in exe:
        return ["uv", "tool", "upgrade", "trovex"]
    return [sys.executable or "python", "-m", "pip", "install", "-U", "trovex"]


def notice_line(info: UpdateInfo) -> str | None:
    """A single, non-naggy upgrade line, or None when already up to date."""
    if not info.newer:
        return None
    return f"trovex {info.latest} is available (you have {info.installed}). Upgrade: {' '.join(upgrade_command())}"


def cached_notice(cache_path: Path | None = None) -> str | None:
    """Zero-network notice for a light startup check: reads the cache only (never
    hits the network, never raises), returns the upgrade line if one is known."""
    try:
        path = cache_path or _default_cache_path()
        cached = _read_cache(path)
        if not cached or not isinstance(cached.get("latest"), str):
            return None
        info = UpdateInfo(
            installed_version(), cached["latest"], is_newer(cached["latest"], installed_version())
        )
        return notice_line(info)
    except Exception:
        return None
