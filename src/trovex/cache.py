"""Exact-match query cache for the trovex() tool.

A repeat of the same query against an unchanged corpus skips the candidate
search + the LLM reranker (the cost driver). Keyed on (normalized query,
summary) + a corpus version derived from the docs table, so any trovex_write /
delete invalidates stale entries automatically — no write-path hook needed.

Exact match only: zero false-hit risk. Measured ~24% hit-rate on real traffic;
a semantic layer (cosine ≥ τ over cached query embeddings) can sit on top later
without changing this contract.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time

_WS = re.compile(r"\s+")

# TTL bounds staleness if an invalidation is ever missed, and (with the row cap)
# keeps the table from growing unbounded. Both tunable via env.
_TTL_SEC = float(os.environ.get("TROVEX_QUERY_CACHE_TTL_SEC", "3600"))
_MAX_ROWS = int(os.environ.get("TROVEX_QUERY_CACHE_MAX_ROWS", "2000"))


def _norm(q: str) -> str:
    return _WS.sub(" ", q.strip().lower())


def _key(q: str, summary: bool) -> str:
    return f"{_norm(q)}|{int(summary)}"


def _ensure(db: sqlite3.Connection) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS query_cache (
            key            TEXT PRIMARY KEY,
            corpus_version TEXT    NOT NULL,
            output         TEXT    NOT NULL,
            n_results      INTEGER NOT NULL,
            whr            INTEGER NOT NULL,
            top_tokens     INTEGER NOT NULL,
            resp_tokens    INTEGER NOT NULL,
            created_at     REAL    NOT NULL
        )"""
    )


def corpus_version(db: sqlite3.Connection, scope: str | None = None) -> str:
    """Cheap version string; changes on any write (mtime bumps) or delete (count).

    PER-SCOPE (T5): when `scope` is a source id, the version reflects ONLY that
    source's docs, so a write to another source no longer voids this scope's cache
    entries (the old global version invalidated the whole cache fleet-wide on any
    write). `scope=None` (the source='*' all-sources query) keeps the global
    version — any write there really can change the result."""
    if scope is None:
        r = db.execute("SELECT COUNT(*) AS c, COALESCE(MAX(mtime), 0) AS m FROM docs").fetchone()
        return f"*:{r['c']}:{r['m']}"
    r = db.execute(
        "SELECT COUNT(*) AS c, COALESCE(MAX(mtime), 0) AS m FROM docs WHERE source_id = ?",
        (scope,),
    ).fetchone()
    return f"{scope}:{r['c']}:{r['m']}"


def get(db: sqlite3.Connection, q: str, summary: bool, version: str) -> dict | None:
    _ensure(db)
    row = db.execute(
        """SELECT output, n_results, whr, top_tokens, resp_tokens
           FROM query_cache
           WHERE key = ? AND corpus_version = ? AND created_at >= ?""",
        (_key(q, summary), version, time.time() - _TTL_SEC),
    ).fetchone()
    return dict(row) if row else None


def put(
    db: sqlite3.Connection,
    q: str,
    summary: bool,
    version: str,
    output: str,
    n_results: int,
    whr: int,
    top_tokens: int,
    resp_tokens: int,
) -> None:
    _ensure(db)
    db.execute(
        """INSERT INTO query_cache
             (key, corpus_version, output, n_results, whr, top_tokens, resp_tokens, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET
             corpus_version = excluded.corpus_version, output = excluded.output,
             n_results = excluded.n_results, whr = excluded.whr,
             top_tokens = excluded.top_tokens, resp_tokens = excluded.resp_tokens,
             created_at = excluded.created_at""",
        (_key(q, summary), version, output, n_results, whr, top_tokens, resp_tokens, time.time()),
    )
    # Row cap (T5): keep only the newest _MAX_ROWS entries so the cache table can't
    # grow without bound. Runs on every put (deletes 0 rows while under the cap);
    # the DELETE is cheap since the kept-set subquery is an indexed LIMIT.
    db.execute(
        """DELETE FROM query_cache WHERE key NOT IN (
               SELECT key FROM query_cache ORDER BY created_at DESC LIMIT ?
           )""",
        (_MAX_ROWS,),
    )
    db.commit()
