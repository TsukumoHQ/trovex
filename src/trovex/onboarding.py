"""File-gathering + date/tag resolution for `trovex import` and `trovex onboard`
(cli.py's `_scan_dir`).

gather() walks a directory for importable .md files (reusing indexer's
ignore-dir-pruning walk); build() resolves one file's real date — git's first
commit for it, else an explicit frontmatter `date:`, else the file's mtime,
in that priority — and derives tags from its folder path, so an import lands
dated and findable the same way a file-indexed doc is.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .indexer import FRONTMATTER_RE, _walk_files
from .store import _extract_title

IMPORT_EXTENSIONS = (".md", ".mdx", ".markdown")


@dataclass
class ImportFile:
    path: Path
    rel: str  # display path, relative to the import root
    content: str
    title: str
    ext_id: str  # stable across re-imports of the same (label, rel)
    mtime: float
    date_source: str  # "git" | "frontmatter" | "mtime"
    tags: list[str]


def gather(root: Path, ignore_dirs: set[str], *, max_bytes: int) -> list[Path]:
    """Every markdown file under root worth importing: ignore_dirs pruned,
    skips empty and oversized files. Deterministic order (sorted)."""
    out = []
    for p in _walk_files(root, ignore_dirs):
        if p.suffix.lower() not in IMPORT_EXTENSIONS:
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size == 0 or size > max_bytes:
            continue
        out.append(p)
    return sorted(out)


def build(path: Path, root: Path, label: str) -> ImportFile | None:
    """Resolve one gathered file into an ImportFile, or None if unreadable /
    empty after decoding (e.g. a binary file gather()'s extension check let
    through)."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not content.strip():
        return None

    rel = str(path.relative_to(root))
    title = _extract_title(content)
    mtime, date_source = _resolve_date(path, content)

    return ImportFile(
        path=path,
        rel=rel,
        content=content,
        title=title,
        ext_id=_stable_ext_id(label, rel),
        mtime=mtime,
        date_source=date_source,
        tags=_tags_from_path(rel, label),
    )


def _stable_ext_id(label: str, rel: str) -> str:
    """Deterministic from (label, rel) — re-importing the same directory
    updates docs in place instead of piling up duplicates."""
    import hashlib

    digest = hashlib.sha256(f"{label}:{rel}".encode()).hexdigest()[:24]
    return f"import-{digest}"


def _tags_from_path(rel: str, label: str) -> list[str]:
    """The source label plus every folder segment between the import root and
    the file, lowercased/dashed — e.g. import root "notes", file
    "Team Updates/2026 Q1.md" -> ["notes", "team-updates"]."""
    parts = Path(rel).parent.parts
    tags = [label] + [p.lower().replace("_", "-").replace(" ", "-") for p in parts]
    seen: set[str] = set()
    out = []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _resolve_date(path: Path, content: str) -> tuple[float, str]:
    git_ts = _git_first_commit_ts(path)
    if git_ts is not None:
        return git_ts, "git"
    fm_ts = _frontmatter_date_ts(content)
    if fm_ts is not None:
        return fm_ts, "frontmatter"
    try:
        return path.stat().st_mtime, "mtime"
    except OSError:
        return time.time(), "mtime"


def _git_first_commit_ts(path: Path) -> float | None:
    """The file's earliest commit timestamp (its true creation date) via
    `git log --follow` (survives a rename/move). None if not in a git repo,
    not tracked, or git isn't on PATH — callers fall through to the next
    date source, never raise."""
    try:
        result = subprocess.run(
            ["git", "log", "--follow", "--format=%at", "--", path.name],
            cwd=path.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    lines = [ln for ln in result.stdout.strip().splitlines() if ln]
    if not lines:
        return None
    try:
        return float(lines[-1])  # git log lists newest-first; oldest is last
    except ValueError:
        return None


def _frontmatter_date_ts(content: str) -> float | None:
    m = FRONTMATTER_RE.match(content)
    if not m:
        return None
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line.startswith("date:"):
            continue
        raw = line.split(":", 1)[1].strip().strip("\"'")
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return None
