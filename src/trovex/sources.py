"""The `sources` table (steal #5, design 61a37a82 6.1): the registry that replaced
sources.yaml. The yaml is imported ONCE, on the first start that finds the table
empty; from then on the table wins (an empty table still falls back to the yaml,
then to the single project_root source, exactly as before)."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import yaml

from .config import RESERVED_SOURCE_ID, Settings, Source

log = logging.getLogger("trovex.sources")


def _row_dicts(db: sqlite3.Connection, where: str = "", params: tuple = ()) -> list[dict]:
    cur = db.execute(f"SELECT * FROM sources {where} ORDER BY id", params)  # sql-safe: literal clauses only
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def list_sources(db: sqlite3.Connection) -> list[dict]:
    return _row_dicts(db)


def get_source(db: sqlite3.Connection, source_id: str) -> dict | None:
    """The ENABLED source row, or None (unknown or disabled)."""
    rows = _row_dicts(db, "WHERE id = ? AND enabled = 1", (source_id,))
    return rows[0] if rows else None


def to_source(row: dict) -> Source:
    cfg = json.loads(row["config"])
    root = Path(cfg["root"]).expanduser().resolve()
    return Source(id=row["id"], label=row["label"], root=root, chunk_markdown=bool(cfg.get("chunk_markdown")))


def add_source(
    db: sqlite3.Connection,
    *,
    id: str,
    root: Path,
    kind: str = "fs",
    label: str | None = None,
    policy: str = "upsert_delete",
) -> None:
    if id == RESERVED_SOURCE_ID:
        raise ValueError(
            f"source id {id!r} is reserved for the trovex-owned store; pick another "
            f"(e.g. {RESERVED_SOURCE_ID}-repo)"
        )
    if db.execute("SELECT 1 FROM sources WHERE id = ?", (id,)).fetchone():
        raise ValueError(f"source {id!r} already exists")
    db.execute(
        "INSERT INTO sources (id, kind, label, config, policy) VALUES (?, ?, ?, ?, ?)",
        (id, kind, label or id, json.dumps({"root": str(Path(root).expanduser().resolve())}), policy),
    )
    db.commit()


def disable_source(db: sqlite3.Connection, source_id: str) -> bool:
    n = db.execute("UPDATE sources SET enabled = 0 WHERE id = ?", (source_id,)).rowcount
    db.commit()
    return n > 0


def import_yaml_once(db: sqlite3.Connection, settings: Settings) -> int:
    """Copy sources.yaml into an EMPTY table. Returns rows imported."""
    path = settings.sources_config_path
    if not path.exists() or db.execute("SELECT 1 FROM sources LIMIT 1").fetchone():
        return 0
    with path.open() as f:
        entries = (yaml.safe_load(f) or {}).get("sources", [])
    n = 0
    for entry in entries:
        if not entry.get("root"):
            continue
        src = Source.from_dict(entry)
        try:
            add_source(db, id=src.id, root=src.root, label=src.label)
        except ValueError as e:  # reserved id (the guard stays) or a duplicate id in the yaml
            log.warning("sources.yaml import skipped %r: %s", src.id, e)
            continue
        n += 1
    if n:
        log.info("imported %d source(s) from %s into the sources table", n, path)
    return n


def load_enabled(settings: Settings) -> list[Source] | None:
    """Enabled fs sources from the table, or None when the table is absent/empty
    (the caller then falls back to the yaml). Read-only: never creates the db."""
    db_path = settings.data_dir / "trovex.db"
    if not db_path.exists():
        return None
    db = sqlite3.connect(str(db_path), timeout=30)
    db.row_factory = sqlite3.Row
    try:
        try:
            rows = _row_dicts(db)
        except sqlite3.OperationalError:  # db predates the sources table
            return None
    finally:
        db.close()
    if not rows:
        return None
    return [to_source(r) for r in rows if r["enabled"] and r["kind"] == "fs"]
