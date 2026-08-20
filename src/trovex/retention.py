"""Importance-gated retention (P3).

Two levers so old-but-critical docs stay findable while ephemeral trivia ages out:

  • importance — a derived score (status class + a pinned boost + access frequency
    from the query log) recomputed over the corpus and blended into the flagship
    ranking, so a heavily-referenced canonical doc outranks a fresh throwaway.
  • TTL eviction — a deterministic, idempotent lifecycle sweep that ages low-value
    OWNED docs active→archived→pending_delete and finally hard-deletes them
    (tombstone, recoverable) after a grace window. Owned records and pinned docs
    are NEVER evicted. Opt-in (Settings.retention_sweep_enabled), so the default
    build has zero eviction behavior.

importance defaults to 0 on every row until `recompute_importance` runs, so the
ranking blend is a no-op until retention is actually exercised.
"""

from __future__ import annotations

import sqlite3

# Base importance by quality/dup status. canonical is the live canon; a
# superseded/duplicate doc contributes nothing (it's already down-ranked/hidden).
STATUS_IMPORTANCE = {
    "canonical": 1.0,
    "plan": 0.6,
    "stale": 0.2,
    "duplicate": 0.0,
    "superseded": 0.0,
}
PIN_BOOST = 1.0  # a pinned doc is always high-importance
ACCESS_WEIGHT = 0.5  # max contribution from access frequency
ACCESS_SATURATION = 10  # query-result hits at which the access term saturates


def importance_for(status: str, pinned: int, access_count: int) -> float:
    """importance = status base + pin boost + saturating access frequency."""
    base = STATUS_IMPORTANCE.get(status, 0.5)
    pin = PIN_BOOST if pinned else 0.0
    access = ACCESS_WEIGHT * min(1.0, access_count / ACCESS_SATURATION)
    return round(base + pin + access, 4)


def recompute_importance(db: sqlite3.Connection) -> int:
    """Recompute + store docs.importance for every doc. Deterministic (a pure
    function of status/pinned + the query-log hit counts). Returns rows updated.
    Does NOT commit — the caller owns the transaction/lock."""
    access = {
        r["path"]: r["n"]
        for r in db.execute("SELECT path, COUNT(*) AS n FROM mcp_query_results GROUP BY path")
    }
    n = 0
    for r in db.execute("SELECT id, path, status, pinned FROM docs").fetchall():
        imp = importance_for(r["status"], r["pinned"], access.get(r["path"], 0))
        db.execute("UPDATE docs SET importance = ? WHERE id = ?", (imp, r["id"]))
        n += 1
    return n
