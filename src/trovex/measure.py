"""Measurement tool for the -60% target.

Reads the baseline JSONL (from trovex-baseline.sh hook) and reports
token-consumption stats. After trovex is in active use, compare two
time windows to validate the savings.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class WindowStats:
    label: str
    n_reads: int
    total_tokens: int
    distinct_files: int
    sessions: int

    @property
    def tokens_per_read(self) -> float:
        return self.total_tokens / max(1, self.n_reads)

    @property
    def reads_per_session(self) -> float:
        return self.n_reads / max(1, self.sessions)


def parse_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def window_stats(entries: list[dict], since: datetime, until: datetime, label: str) -> WindowStats:
    keep = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(e["ts"])
        except (KeyError, ValueError):
            continue
        if since <= ts < until:
            keep.append(e)
    return WindowStats(
        label=label,
        n_reads=len(keep),
        total_tokens=sum(e.get("tokens_est", 0) for e in keep),
        distinct_files=len({e.get("path") for e in keep}),
        sessions=len({e.get("session_id") for e in keep if e.get("session_id")}),
    )


def by_path(entries: list[dict], top: int = 20) -> list[tuple[str, int, int]]:
    """Return [(path, reads, total_tokens), ...] sorted by tokens desc."""
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for e in entries:
        path = e.get("path")
        if not path:
            continue
        agg[path][0] += 1
        agg[path][1] += e.get("tokens_est", 0)
    rows = [(p, c, t) for p, (c, t) in agg.items()]
    rows.sort(key=lambda r: -r[2])
    return rows[:top]


def report(log_path: Path, baseline_days: int = 7, current_days: int = 7) -> str:
    entries = parse_log(log_path)
    if not entries:
        return f"No baseline data in {log_path}. Hook may not be installed or no .md reads yet."

    now = datetime.fromisoformat(entries[-1]["ts"].replace("Z", "+00:00"))
    current = window_stats(
        entries,
        now - timedelta(days=current_days),
        now + timedelta(seconds=1),
        f"last {current_days}d",
    )
    baseline = window_stats(
        entries,
        now - timedelta(days=baseline_days + current_days),
        now - timedelta(days=current_days),
        f"prior {baseline_days}d",
    )

    lines = []
    lines.append(f"Source: {log_path}  ({len(entries)} total events)")
    lines.append("")
    lines.append(f"{'window':<14}  {'reads':>7}  {'tokens':>12}  {'tok/read':>10}  {'sessions':>9}")
    for w in (baseline, current):
        lines.append(
            f"{w.label:<14}  {w.n_reads:>7}  {w.total_tokens:>12,}  "
            f"{w.tokens_per_read:>10.0f}  {w.sessions:>9}"
        )

    if baseline.n_reads > 0 and current.n_reads > 0:
        delta_pct = (1 - current.tokens_per_read / baseline.tokens_per_read) * 100
        verdict = (
            "✓ HIT" if delta_pct >= 60 else ("~ on track" if delta_pct >= 30 else "✗ below target")
        )
        lines.append("")
        lines.append(f"Δ tokens/read: {delta_pct:+.1f}%  (target: -60%)  {verdict}")

    lines.append("")
    lines.append("Top 10 paths by total tokens read:")
    for path, reads, tok in by_path(entries, top=10):
        lines.append(f"  {tok:>9,} tok  ({reads:>3}×)  {path}")
    return "\n".join(lines)
