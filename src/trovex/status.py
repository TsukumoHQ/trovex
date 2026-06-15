"""Status detection heuristics: ★ canonical / ◯ plan / ✗ stale / ⚠ duplicate.

Runs after indexing. Doc-local rules first (path patterns, frontmatter,
content cues), then pairwise duplicate detection via sqlite-vec.
"""

from __future__ import annotations

import re
import sqlite3
import time

from .config import Settings
from .indexer import FRONTMATTER_RE

PLAN_TITLE_RE = re.compile(r"^\s*(?:plan|todo|draft|wip|brouillon)\b", re.IGNORECASE)


def compute_status(db: sqlite3.Connection, settings: Settings) -> dict:
    """Apply heuristics and update docs.status for all rows.

    Order matters:
      1. Reset everything to canonical (clears stale flags from prior runs)
      2. plan: path patterns / title cues / frontmatter
      3. stale: frontmatter explicit / age threshold
      4. duplicate: nearest-neighbour cosine > threshold, older wins
      5. stale (cascading): if duplicate's canonical is fresher than X
    """
    db.execute("UPDATE docs SET status = 'canonical', dup_of_id = NULL")

    plan_re = re.compile("|".join(settings.plan_path_patterns))
    now = time.time()
    stale_cutoff = now - settings.stale_age_days * 86400

    # Pass 1: plan + stale (single-doc rules)
    rows = db.execute(
        "SELECT id, path, absolute_path, mtime, kind FROM docs WHERE workspace_id = 'default'"
    ).fetchall()

    plan_count = stale_count = 0
    for row in rows:
        doc_id = row["id"]
        path = row["path"]
        new_status = None

        # Plan via path or title
        if plan_re.search(path):
            new_status = "plan"
        else:
            try:
                head = _read_head(row["absolute_path"], 2000)
                if _looks_like_plan(head):
                    new_status = "plan"
            except OSError:
                pass

        # Stale: explicit frontmatter
        try:
            head = _read_head(row["absolute_path"], 1500)
            if _frontmatter_status(head) == "stale":
                new_status = "stale"
        except OSError:
            pass

        # Stale: age (only if not already plan). Records are event-anchored —
        # a 2-year-old incident report is still true, so never age-stale them.
        if (new_status is None and row["kind"] != "record"
                and row["mtime"] < stale_cutoff):
            new_status = "stale"

        if new_status is not None and new_status != "canonical":
            db.execute(
                "UPDATE docs SET status = ? WHERE id = ?",
                (new_status, doc_id),
            )
            if new_status == "plan":
                plan_count += 1
            elif new_status == "stale":
                stale_count += 1

    # Pass 2: duplicate detection (pairwise, only for canonical+plan docs)
    dup_count = _detect_duplicates(db, settings)

    db.commit()
    return {
        "plan": plan_count,
        "stale": stale_count,
        "duplicate": dup_count,
        "canonical": len(rows) - plan_count - stale_count - dup_count,
    }


def _detect_duplicates(db: sqlite3.Connection, settings: Settings) -> int:
    """For each doc, find nearest neighbour. If cosine sim > threshold,
    older doc becomes duplicate of newer."""
    threshold = settings.dup_cosine_threshold
    # Records are unique by definition (each incident/decision is its own event)
    # — exclude them from dedup entirely, as drivers and as neighbours.
    rows = db.execute(
        """SELECT d.id, d.mtime FROM docs d
           WHERE d.status IN ('canonical', 'plan')
             AND d.workspace_id = 'default'
             AND (d.kind IS NULL OR d.kind != 'record')"""
    ).fetchall()
    if len(rows) < 2:
        return 0

    dup_marked: set[int] = set()
    for row in rows:
        if row["id"] in dup_marked:
            continue
        # Get this doc's embedding
        emb_row = db.execute(
            "SELECT embedding FROM vec_docs WHERE rowid = ?", (row["id"],)
        ).fetchone()
        if not emb_row:
            continue

        # Find nearest neighbour (k=2 to skip self)
        neighbours = db.execute(
            """SELECT v.rowid, v.distance, d.mtime, d.kind
               FROM vec_docs v
               JOIN docs d ON d.id = v.rowid
               WHERE v.embedding MATCH ? AND k = 3
               ORDER BY v.distance""",
            (emb_row["embedding"],),
        ).fetchall()

        for nb in neighbours:
            if nb["rowid"] == row["id"]:
                continue
            if nb["kind"] == "record":
                continue  # never pair a record into a duplicate
            similarity = 1.0 - nb["distance"] / 2
            if similarity < threshold:
                break  # neighbours are sorted by distance asc
            # Found a duplicate. Older becomes duplicate of newer.
            if row["mtime"] >= nb["mtime"]:
                older_id = nb["rowid"]
                newer_id = row["id"]
            else:
                older_id = row["id"]
                newer_id = nb["rowid"]
            if older_id in dup_marked:
                continue
            db.execute(
                "UPDATE docs SET status = 'duplicate', dup_of_id = ? WHERE id = ?",
                (newer_id, older_id),
            )
            dup_marked.add(older_id)
            break  # one duplicate marking per doc

    return len(dup_marked)


def detect_duplicate_for(db: sqlite3.Connection, settings: Settings, doc_id: int) -> int | None:
    """Single-doc duplicate check for the live write path (store.put).

    The batch _detect_duplicates() ran only from the retired indexer; this is its
    one-doc equivalent so trovex_write flags near-dups as they land. If the doc's
    nearest non-record neighbour is within the cosine threshold, the OLDER of the
    two becomes a duplicate of the newer. Returns the id marked duplicate, or None.
    """
    row = db.execute(
        "SELECT id, mtime, kind, status FROM docs WHERE id = ?", (doc_id,)
    ).fetchone()
    if not row or row["kind"] == "record" or row["status"] not in ("canonical", "plan"):
        return None
    emb = db.execute("SELECT embedding FROM vec_docs WHERE rowid = ?", (doc_id,)).fetchone()
    if not emb:
        return None
    threshold = settings.dup_cosine_threshold
    neighbours = db.execute(
        """SELECT v.rowid, v.distance, d.mtime, d.kind, d.status
           FROM vec_docs v JOIN docs d ON d.id = v.rowid
           WHERE v.embedding MATCH ? AND k = 3 ORDER BY v.distance""",
        (emb["embedding"],),
    ).fetchall()
    for nb in neighbours:
        if nb["rowid"] == doc_id or nb["kind"] == "record":
            continue
        if nb["status"] not in ("canonical", "plan"):
            continue
        if 1.0 - nb["distance"] / 2 < threshold:
            break  # neighbours sorted by distance asc → none closer remain
        older_id, newer_id = (
            (nb["rowid"], doc_id) if row["mtime"] >= nb["mtime"]
            else (doc_id, nb["rowid"])
        )
        db.execute(
            "UPDATE docs SET status = 'duplicate', dup_of_id = ? WHERE id = ?",
            (newer_id, older_id),
        )
        db.commit()
        return older_id
    return None


def _read_head(path: str, n: int) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read(n)


def _looks_like_plan(head: str) -> bool:
    stripped = FRONTMATTER_RE.sub("", head)
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()][:5]
    return any(
        ln.startswith("#") and PLAN_TITLE_RE.search(ln.lstrip("#").strip())
        for ln in lines
    )


def _frontmatter_status(head: str) -> str | None:
    m = FRONTMATTER_RE.match(head)
    if not m:
        return None
    for line in m.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("status:"):
            return stripped.split(":", 1)[1].strip().strip("\"'").lower()
    return None
