"""Implicit (inferred) edges: unlinked mentions + semantic neighbours
(task 07b7cdc4, trovex/links L3).

These are the edges trovex INFERS rather than reads from the text:
  - `mentions`: the doc names another doc (its title/basename, word-bounded,
    ≥4 chars, case-insensitive) WITHOUT an explicit link — surfaced so the two
    still connect, but kept a distinct kind so explicit links stay unambiguous.
  - `similar`: a semantic neighbour in a band BELOW the near-duplicate cosine
    threshold (top-3, with the score) — reuses the same vec0 KNN as the
    duplicate detector, so "similar" is "almost a dup, but not".

Both land in the L1 `doc_refs` table under their own kinds and are recomputed
incrementally: compute_status calls `sync_implicit_refs` for the touched docs
only (the KNN is the expensive part — scoping drivers to touched ids is what
matters, mirroring _detect_duplicates).

NOTE (DEBT): `1 - distance/2` mirrors the duplicate detector's similarity and
is NOT true cosine unless vec0's metric is squared-L2 on unit vectors; the
`similar` band is defined against that same quantity for consistency.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .config import Settings

__all__ = ["MENTIONS", "SIMILAR", "sync_implicit_refs"]

MENTIONS = "mentions"
SIMILAR = "similar"
_IMPLICIT_KINDS = (MENTIONS, SIMILAR)
# Explicit/extracted edge kinds that SUPPRESS an inferred edge to the same doc:
# an explicitly linked (or cited) doc is already connected, so don't also infer.
_EXPLICIT_KINDS = ("links-to", "embeds", "cites-code")
_MIN_NAME_LEN = 4
_SIMILAR_TOPK = 3
# `similar` = similarity in [threshold - band, threshold): near the dup line but
# under it. Documented against the non-true-cosine caveat above.
_SIMILAR_BAND = 0.15


def _basename_noext(path: str) -> str:
    base = path.rsplit("/", 1)[-1]
    return base.rsplit(".", 1)[0] if "." in base else base


def _drivers(db: sqlite3.Connection, driver_ids) -> list[int]:
    if driver_ids is not None:
        return list(driver_ids)
    return [
        r["id"]
        for r in db.execute(
            "SELECT id FROM docs WHERE status IN ('canonical', 'plan')"
        ).fetchall()
    ]


def _name_index(db: sqlite3.Connection) -> dict[str, int]:
    """{lowercased name → doc id} for every doc's title (and file basename),
    ≥4 chars, dropping any name that isn't unique (ambiguous → no mention)."""
    rows = db.execute(
        "SELECT id, title, path, source_id FROM docs WHERE status IN ('canonical', 'plan')"
    ).fetchall()
    idx: dict[str, int] = {}
    collide: set[str] = set()
    for r in rows:
        names = [r["title"] or ""]
        if r["source_id"] != "trovex":  # file-backed: a real filename, not an ext_id
            names.append(_basename_noext(r["path"]))
        for nm in names:
            nm = nm.strip()
            if len(nm) < _MIN_NAME_LEN:
                continue
            key = nm.lower()
            if key in idx and idx[key] != r["id"]:
                collide.add(key)
            else:
                idx.setdefault(key, r["id"])
    for key in collide:
        idx.pop(key, None)
    return idx


def _doc_text(db: sqlite3.Connection, doc_id: int) -> str:
    row = db.execute("SELECT content, absolute_path FROM docs WHERE id = ?", (doc_id,)).fetchone()
    if row is None:
        return ""
    if row["content"] is not None:
        return row["content"]
    if row["absolute_path"]:
        try:
            return Path(row["absolute_path"]).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    return ""


def sync_implicit_refs(db: sqlite3.Connection, settings: Settings, driver_ids=None) -> None:
    """Recompute inferred (mentions + similar) edges for the driver docs.

    driver_ids=None → every canonical/plan doc (full recompute); a list →
    only those (incremental). Does NOT commit — the caller owns the txn."""
    drivers = _drivers(db, driver_ids)
    if not drivers:
        return
    names = _name_index(db)
    for doc_id in drivers:
        _sync_one(db, settings, doc_id, names)


def _sync_one(db: sqlite3.Connection, settings: Settings, doc_id: int, names: dict[str, int]) -> None:
    db.execute(
        f"DELETE FROM doc_refs WHERE src_id = ? AND kind IN ({','.join('?' * len(_IMPLICIT_KINDS))})",
        (doc_id, *_IMPLICIT_KINDS),
    )
    # Docs this one already connects to explicitly/by citation — never also infer.
    explicit = {
        r["dst_id"]
        for r in db.execute(
            f"""SELECT DISTINCT dst_id FROM doc_refs
                WHERE src_id = ? AND dst_id IS NOT NULL
                  AND kind IN ({','.join('?' * len(_EXPLICIT_KINDS))})""",
            (doc_id, *_EXPLICIT_KINDS),
        ).fetchall()
    }
    _mentions(db, doc_id, names, explicit)
    _similar(db, settings, doc_id, explicit)


def _mentions(db, doc_id: int, names: dict[str, int], explicit: set) -> None:
    text = _doc_text(db, doc_id).lower()
    if not text:
        return
    for name, tgt in names.items():
        if tgt == doc_id or tgt in explicit:
            continue
        if re.search(rf"\b{re.escape(name)}\b", text):
            db.execute(
                """INSERT OR IGNORE INTO doc_refs
                       (src_id, dst_id, dst_raw, dst_norm, anchor, alias, context, kind)
                   VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)""",
                (doc_id, tgt, name, name, name, MENTIONS),
            )


def _similar(db, settings: Settings, doc_id: int, explicit: set) -> None:
    emb = db.execute("SELECT embedding FROM vec_docs WHERE rowid = ?", (doc_id,)).fetchone()
    if not emb:
        return
    row = db.execute("SELECT kind, source_id FROM docs WHERE id = ?", (doc_id,)).fetchone()
    if row is None:
        return
    threshold = settings.dup_threshold_for(row["kind"])
    floor = threshold - _SIMILAR_BAND
    kind_clause = "d.kind IS NULL" if row["kind"] is None else "d.kind = :kind"
    neighbours = db.execute(
        f"""SELECT v.rowid, v.distance FROM vec_docs v JOIN docs d ON d.id = v.rowid
            WHERE v.embedding MATCH :emb AND k = 20
              AND d.source_id = :source_id AND {kind_clause}
              AND d.status IN ('canonical', 'plan')
            ORDER BY v.distance""",
        {"emb": emb["embedding"], "source_id": row["source_id"], "kind": row["kind"]},
    ).fetchall()
    added = 0
    for nb in neighbours:
        if nb["rowid"] == doc_id:
            continue
        sim = 1.0 - nb["distance"] / 2
        if sim >= threshold:
            continue  # duplicate band — excluded (kept distinct from 'similar')
        if sim < floor:
            break  # sorted by distance asc → similarity desc; nothing closer remains
        if nb["rowid"] in explicit:
            continue
        dst = db.execute("SELECT title, path, source_id FROM docs WHERE id = ?", (nb["rowid"],)).fetchone()
        raw = (dst["title"] if dst and dst["title"] else "") or (dst["path"] if dst else str(nb["rowid"]))
        db.execute(
            """INSERT OR IGNORE INTO doc_refs
                   (src_id, dst_id, dst_raw, dst_norm, anchor, alias, context, kind)
               VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)""",
            (doc_id, nb["rowid"], raw, raw.lower(), f"{sim:.3f}", SIMILAR),
        )
        added += 1
        if added >= _SIMILAR_TOPK:
            break
