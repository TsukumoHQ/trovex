"""Online SQLite backups for the trovex store (now the sole corpus).

Uses the sqlite backup API for a consistent snapshot even while the server is
writing, after a WAL checkpoint. Keeps the last N, prunes the rest.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

KEEP = 7  # the db is ~340MB (chunk vectors) — 7 daily = ~2.4GB


def backup_dir(data_dir: Path) -> Path:
    return data_dir / "backups"


def make_backup(db_path: Path, data_dir: Path) -> Path:
    bdir = backup_dir(data_dir)
    bdir.mkdir(parents=True, exist_ok=True)
    # Best-effort pre-checkpoint, PASSIVE only (task 2081581c): TRUNCATE needs
    # EXCLUSIVE access and busy-waits up to busy_timeout (30s) against any
    # reader holding an older WAL frame — under the server's read traffic
    # there's almost always one, so this path reintroduced the exact stall
    # db.checkpoint_if_wal_large already documents and fixed elsewhere (prod
    # 2026-08-31 task 7768dbe6: trovex_write/search stalled to exactly
    # 30000ms). src.backup(dst) below copies a CONSISTENT snapshot including
    # WAL content regardless — this checkpoint is a pure size/speed
    # optimization, never required for correctness. PASSIVE "does as much
    # work as it can without interfering with other database connections"
    # (sqlite.org/wal.html): it never blocks, so a busy store just gets a
    # smaller optimization for free instead of a stall.
    flush = sqlite3.connect(str(db_path))
    try:
        flush.execute("PRAGMA wal_checkpoint(PASSIVE)")
    finally:
        flush.close()
    dest = bdir / f"trovex-{time.strftime('%Y%m%d-%H%M%S')}.db"
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(dest))
    try:
        src.backup(dst)  # consistent online copy
    finally:
        dst.close()
        src.close()
    prune(data_dir)
    return dest


def list_backups(data_dir: Path) -> list[dict]:
    bdir = backup_dir(data_dir)
    if not bdir.exists():
        return []
    out = []
    for p in sorted(bdir.glob("trovex-*.db"), reverse=True):
        st = p.stat()
        out.append({"name": p.name, "size_bytes": st.st_size, "mtime": st.st_mtime})
    return out


def prune(data_dir: Path, keep: int = KEEP) -> int:
    backups = sorted(backup_dir(data_dir).glob("trovex-*.db"), reverse=True)
    removed = 0
    for p in backups[keep:]:
        p.unlink()
        removed += 1
    return removed
