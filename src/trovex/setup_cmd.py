"""trovex setup — land the Claude Code skill, hooks, and MCP registration.

The one post-install step after `uv tool install trovex`, so a cold install is
documented as a single command instead of a manual copy dance. Everything here
is idempotent and non-destructive: re-running is safe, existing skill/hook files
are left alone unless --force, and settings.json is merged (never clobbered).
"""

from __future__ import annotations

import importlib.resources as ir
import json
import os
import shutil
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()

MCP_URL = "http://localhost:8765/mcp"

# Claude Code hook event → bundled script. These are the Active-Memory recall +
# capture hooks; each degrades to a silent no-op when trovex is down, and the
# agent name defaults to the cwd basename, so they need zero configuration.
HOOK_EVENTS = {
    "SessionStart": "trovex-boot.sh",
    "UserPromptSubmit": "trovex-prompt.sh",
    "PostCompact": "trovex-postcompact.sh",
}


def _claude_dir() -> Path:
    """Where Claude Code resolves config — CLAUDE_CONFIG_DIR or ~/.claude."""
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env).expanduser() if env else Path.home() / ".claude"


def _asset(*parts: str):
    return ir.files("trovex").joinpath("assets", *parts)


def install_skill(force: bool) -> bool:
    """Copy the bundled skill to <claude>/skills/trovex/SKILL.md."""
    dest = _claude_dir() / "skills" / "trovex" / "SKILL.md"
    if dest.exists() and not force:
        console.print(f"[dim]skill:    already present — {dest} (--force to overwrite)[/dim]")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_asset("skill", "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[green]skill:[/green]    installed → {dest}")
    return True


def install_hooks(force: bool) -> Path:
    """Copy the bundled hooks to <claude>/hooks/trovex/ (executable)."""
    dest_dir = _claude_dir() / "hooks" / "trovex"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for fname in HOOK_EVENTS.values():
        dst = dest_dir / fname
        if dst.exists() and not force:
            continue
        dst.write_text(_asset("hooks", fname).read_text(encoding="utf-8"), encoding="utf-8")
        dst.chmod(0o755)
    console.print(f"[green]hooks:[/green]    installed → {dest_dir}")
    return dest_dir


def merge_settings(hook_dir: Path) -> None:
    """Register the trovex hooks in settings.json without clobbering existing ones."""
    settings = _claude_dir() / "settings.json"
    data: dict = {}
    if settings.exists():
        try:
            data = json.loads(settings.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            console.print(
                f"[yellow]settings:[/yellow] {settings} is not valid JSON — not touching it. "
                "Add the trovex hooks manually."
            )
            return
    hooks = data.setdefault("hooks", {})
    changed = False
    for event, fname in HOOK_EVENTS.items():
        cmd = str(hook_dir / fname)
        entries = hooks.setdefault(event, [])
        present = any(
            h.get("command") == cmd
            for entry in entries
            if isinstance(entry, dict)
            for h in entry.get("hooks", [])
            if isinstance(h, dict)
        )
        if present:
            continue
        entries.append({"hooks": [{"type": "command", "command": cmd}]})
        changed = True
    if changed:
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        console.print(f"[green]settings:[/green] registered trovex hooks → {settings}")
    else:
        console.print("[dim]settings: trovex hooks already registered[/dim]")


def configure_mcp() -> None:
    """Register the MCP server with Claude Code (idempotent), or print the command."""
    manual = f"claude mcp add --transport http trovex {MCP_URL}"
    claude = shutil.which("claude")
    if not claude:
        console.print("[yellow]mcp:[/yellow]      `claude` CLI not on PATH. Register manually:")
        console.print(f"            [cyan]{manual}[/cyan]")
        return
    try:
        listed = subprocess.run(
            [claude, "mcp", "list"], capture_output=True, text=True, timeout=15
        )
        if "trovex" in (listed.stdout or ""):
            console.print("[dim]mcp:      already registered with Claude Code[/dim]")
            return
    except Exception:  # noqa: BLE001 — listing is best-effort; fall through to add
        pass
    try:
        r = subprocess.run(
            [claude, "mcp", "add", "--transport", "http", "trovex", MCP_URL],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            console.print(f"[green]mcp:[/green]      registered trovex ({MCP_URL})")
        else:
            console.print("[yellow]mcp:[/yellow]      `claude mcp add` failed. Run manually:")
            console.print(f"            [cyan]{manual}[/cyan]")
    except Exception as e:  # noqa: BLE001 — never crash setup on the MCP step
        console.print(f"[yellow]mcp:[/yellow]      couldn't run claude ({e}). Run manually:")
        console.print(f"            [cyan]{manual}[/cyan]")


def run_setup(*, skill: bool = True, hooks: bool = True, mcp: bool = True, force: bool = False) -> int:
    """Wire trovex into Claude Code. Returns a process exit code (0 = ok)."""
    console.print("[bold]trovex setup[/bold] — wiring trovex into Claude Code\n")
    try:
        if skill:
            install_skill(force)
        if hooks:
            merge_settings(install_hooks(force))
        if mcp:
            configure_mcp()
    except OSError as e:
        console.print(f"\n[red]setup failed:[/red] {e}")
        return 1
    console.print("\n[bold]Next[/bold]")
    console.print("  1. [cyan]trovex index /path/to/your/repo[/cyan]   index your docs")
    console.print("  2. [cyan]trovex serve[/cyan]                       start the MCP server")
    console.print("  3. Restart Claude Code so it loads the skill + hooks")
    return 0
