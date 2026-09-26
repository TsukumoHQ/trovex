"""usage.mark_result_used (task b47301eb) — the free used-vs-served label a
served doc gets when the SAME session reads it back within the labeling window
— plus the additive `mcp_query_results.used` migration."""

from __future__ import annotations

import sqlite3
import time

import sqlite_vec

import trovex.db as db
from trovex.usage import log_pointer_query, mark_result_used


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


def test_migrate_add_query_source_adds_column_to_legacy_table(tmp_path):
    conn = _vec_conn(tmp_path)
    conn.execute(
        "CREATE TABLE mcp_queries (id INTEGER PRIMARY KEY, ts REAL, user TEXT, "
        "session_id TEXT, query TEXT, n_results INTEGER)"
    )
    conn.commit()
    assert "source" not in {r[1] for r in conn.execute("PRAGMA table_info(mcp_queries)")}

    db._migrate_add_query_source(conn)

    cols = {r[1] for r in conn.execute("PRAGMA table_info(mcp_queries)")}
    assert "source" in cols
    conn.execute(
        "INSERT INTO mcp_queries (ts, user, session_id, query, n_results) VALUES (0, 'u', 's', 'q', 0)"
    )
    # pre-migration rows were all explicit tool calls — default must say so, not 'unknown'.
    assert conn.execute("SELECT source FROM mcp_queries").fetchone()["source"] == "mcp"


def test_migrate_add_query_source_is_noop_without_table(tmp_path):
    conn = _vec_conn(tmp_path)
    db._migrate_add_query_source(conn)  # must not raise


def test_migrate_add_query_source_idempotent_when_column_present(tmp_path):
    conn = _vec_conn(tmp_path)
    conn.execute("CREATE TABLE mcp_queries (id INTEGER PRIMARY KEY, source TEXT NOT NULL DEFAULT 'mcp')")
    conn.commit()
    db._migrate_add_query_source(conn)  # second ALTER would raise "duplicate column"
    assert {r[1] for r in conn.execute("PRAGMA table_info(mcp_queries)")} == {"id", "source"}


def test_migrate_add_query_budget_adds_receipt_columns_to_legacy_table(tmp_path):
    conn = _vec_conn(tmp_path)
    conn.execute("CREATE TABLE mcp_queries (id INTEGER PRIMARY KEY)")
    conn.commit()

    db._migrate_add_query_budget(conn)
    db._migrate_add_query_budget(conn)

    cols = {r[1] for r in conn.execute("PRAGMA table_info(mcp_queries)")}
    assert {"budget_requested", "budget_used"} <= cols
    conn.execute("INSERT INTO mcp_queries DEFAULT VALUES")
    row = conn.execute("SELECT budget_requested, budget_used FROM mcp_queries").fetchone()
    assert dict(row) == {"budget_requested": None, "budget_used": 0}


def test_log_pointer_query_writes_one_row_and_its_served_ids(tmp_path):
    conn = db.open_db(tmp_path / "trovex.db")

    log_pointer_query(
        conn,
        source="boot",
        agent="coo",
        query="current state resume",
        pointers=[{"id": "doc-a", "score": 0.9}, {"id": "doc-b", "score": 0.7}],
        tokens_est=42,
        elapsed_ms=5,
    )

    row = conn.execute("SELECT * FROM mcp_queries").fetchone()
    assert row["source"] == "boot"
    assert row["session_id"] == "coo" and row["user"] == "coo"
    assert row["n_results"] == 2
    assert row["response_tokens_est"] == 42 and row["top_result_tokens"] == 42

    served = [r["path"] for r in conn.execute(
        "SELECT path FROM mcp_query_results WHERE query_id = ? ORDER BY rank", (row["id"],)
    )]
    assert served == ["doc-a", "doc-b"]


def test_log_pointer_query_source_labels_join_with_mark_result_used(tmp_path):
    """The used-label join is source-agnostic (task 2b7974cf AC2): a boot-served
    pointer this agent later reads back via trovex_read(doc_id=...) gets
    used=1 exactly like an explicit mcp-served result would."""
    conn = db.open_db(tmp_path / "trovex.db")
    log_pointer_query(
        conn, source="boot", agent="coo", query="q", pointers=[{"id": "doc-a", "score": 0.9}],
        tokens_est=10, elapsed_ms=1,
    )

    n = mark_result_used(conn, "doc-a", "coo", window_seconds=300)

    assert n == 1
    assert conn.execute("SELECT used FROM mcp_query_results").fetchone()["used"] == 1


def test_log_pointer_query_never_raises_on_a_bad_connection():
    """boot_pointers' own contract: boot must NEVER 500. A logging failure
    (e.g. the connection is already closed) must not propagate."""
    class _Boom:
        def execute(self, *a, **k):
            raise sqlite3.OperationalError("closed")

    log_pointer_query(
        _Boom(), source="boot", agent="coo", query="q", pointers=[], tokens_est=0, elapsed_ms=0
    )  # must not raise
