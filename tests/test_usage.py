"""usage.mark_result_used (task b47301eb) — the free used-vs-served label a
served doc gets when the SAME session reads it back within the labeling window
— plus the additive `mcp_query_results.used` migration."""

from __future__ import annotations

import sqlite3
import time

import sqlite_vec

import trovex.db as db
from trovex.usage import mark_result_used


def _vec_conn(tmp_path, name="raw.db"):
    conn = sqlite3.connect(str(tmp_path / name))
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def test_migrate_add_query_used_adds_column_to_legacy_table(tmp_path):
    conn = _vec_conn(tmp_path)
    conn.execute(
        """CREATE TABLE mcp_query_results (
               query_id INTEGER NOT NULL,
               rank INTEGER NOT NULL,
               path TEXT NOT NULL,
               status TEXT,
               tokens_est INTEGER,
               score REAL,
               PRIMARY KEY (query_id, rank)
           )"""
    )
    conn.commit()
    assert "used" not in {r[1] for r in conn.execute("PRAGMA table_info(mcp_query_results)")}

    db._migrate_add_query_used(conn)

    cols = {r[1] for r in conn.execute("PRAGMA table_info(mcp_query_results)")}
    assert "used" in cols
    conn.execute("INSERT INTO mcp_query_results (query_id, rank, path) VALUES (1, 0, 'x')")
    assert conn.execute("SELECT used FROM mcp_query_results").fetchone()["used"] == 0


def test_migrate_add_query_used_is_noop_without_table(tmp_path):
    conn = _vec_conn(tmp_path)
    db._migrate_add_query_used(conn)  # must not raise


def test_migrate_add_query_used_idempotent_when_column_present(tmp_path):
    conn = _vec_conn(tmp_path)
    conn.execute(
        "CREATE TABLE mcp_query_results (query_id INTEGER, rank INTEGER, path TEXT, "
        "used INTEGER NOT NULL DEFAULT 0)"
    )
    conn.commit()
    db._migrate_add_query_used(conn)  # second ALTER would raise "duplicate column"
    assert {r[1] for r in conn.execute("PRAGMA table_info(mcp_query_results)")} == {
        "query_id", "rank", "path", "used"
    }


def _seed_query(conn, *, query_id: int, session_id: str, ts: float, path: str) -> None:
    conn.execute(
        """INSERT INTO mcp_queries (id, ts, user, session_id, query)
           VALUES (?, ?, 'test', ?, 'q')""",
        (query_id, ts, session_id),
    )
    conn.execute(
        "INSERT INTO mcp_query_results (query_id, rank, path) VALUES (?, 0, ?)",
        (query_id, path),
    )
    conn.commit()


def test_mark_result_used_marks_within_window_same_session(tmp_path):
    conn = db.open_db(tmp_path / "trovex.db")
    now = time.time()
    _seed_query(conn, query_id=1, session_id="s1", ts=now - 60, path="doc-a")

    n = mark_result_used(conn, "doc-a", "s1", window_seconds=300)

    assert n == 1
    assert conn.execute("SELECT used FROM mcp_query_results WHERE query_id=1").fetchone()["used"] == 1


def test_mark_result_used_ignores_other_session(tmp_path):
    conn = db.open_db(tmp_path / "trovex.db")
    now = time.time()
    _seed_query(conn, query_id=1, session_id="s1", ts=now - 60, path="doc-a")

    n = mark_result_used(conn, "doc-a", "s2", window_seconds=300)

    assert n == 0
    assert conn.execute("SELECT used FROM mcp_query_results WHERE query_id=1").fetchone()["used"] == 0


def test_mark_result_used_ignores_outside_window(tmp_path):
    conn = db.open_db(tmp_path / "trovex.db")
    now = time.time()
    _seed_query(conn, query_id=1, session_id="s1", ts=now - 3600, path="doc-a")

    n = mark_result_used(conn, "doc-a", "s1", window_seconds=300)

    assert n == 0


def test_mark_result_used_skips_unknown_session(tmp_path):
    conn = db.open_db(tmp_path / "trovex.db")
    now = time.time()
    _seed_query(conn, query_id=1, session_id="unknown", ts=now - 10, path="doc-a")

    n = mark_result_used(conn, "doc-a", "unknown", window_seconds=300)

    assert n == 0
    assert conn.execute("SELECT used FROM mcp_query_results WHERE query_id=1").fetchone()["used"] == 0


def test_mark_result_used_marks_every_unused_row_for_path_in_session(tmp_path):
    """Two recent queries in the same session both served the same doc — a single
    read back plausibly answers either, so both get labelled."""
    conn = db.open_db(tmp_path / "trovex.db")
    now = time.time()
    _seed_query(conn, query_id=1, session_id="s1", ts=now - 60, path="doc-a")
    _seed_query(conn, query_id=2, session_id="s1", ts=now - 30, path="doc-a")

    n = mark_result_used(conn, "doc-a", "s1", window_seconds=300)

    assert n == 2
