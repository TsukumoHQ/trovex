"""Direct tests for the links L2 resolution helpers and the best-effort
`_link_hint` logging (task 6664c8c9, follow-up to trovex/links L2 b9687dfb).

`resolve_doc_handle`'s LIKE-prefix and bare-path branches were only covered
indirectly through the MCP surface; these exercise them directly, in particular
the underscore-escape fix (a handle containing `_` must not widen to a wildcard
match). Hermetic: a plain sqlite DB built by `open_db`, no embedder, no model.
"""

from __future__ import annotations

import logging
import sqlite3
from types import SimpleNamespace

import pytest

from trovex.db import open_db
from trovex.links_parse import resolve_doc_handle
from trovex.search import Searcher


@pytest.fixture
def conn(tmp_path):
    c = open_db(tmp_path / "t.db")
    try:
        yield c
    finally:
        c.close()


def _add_doc(conn: sqlite3.Connection, *, source_id: str, path: str, ext_id: str | None):
    conn.execute(
        """INSERT INTO docs(workspace_id, source_id, path, absolute_path,
               content_hash, size_bytes, tokens_est, mtime, first_indexed,
               last_indexed, ext_id)
           VALUES('default', ?, ?, ?, '', 0, 0, 0, 0, 0, ?)""",
        (source_id, path, f"/abs/{source_id}/{path}", ext_id),
    )
    conn.commit()


# --- AC1: LIKE-prefix branch escapes '_' so it matches only the literal prefix


def test_like_prefix_underscore_is_literal_not_wildcard(conn):
    # Two ext_ids share the first three chars; one has a literal '_' at pos 4,
    # the other an arbitrary char. Without the LIKE escape, handle "abc_" would
    # treat '_' as "any single char" and match BOTH (ambiguous -> None).
    _add_doc(conn, source_id="code", path="one.md", ext_id="abc_one")
    _add_doc(conn, source_id="code", path="two.md", ext_id="abcZtwo")

    row = resolve_doc_handle(conn, "abc_")

    assert row is not None  # the escape keeps the match unique...
    assert row["ext_id"] == "abc_one"  # ...to the literal "abc_" prefix


# --- AC2: bare-path-unique resolves; an ambiguous bare path does not ---------


def test_bare_path_unique_resolves(conn):
    _add_doc(conn, source_id="code", path="notes/unique.md", ext_id="u1")

    row = resolve_doc_handle(conn, "notes/unique.md")

    assert row is not None
    assert row["path"] == "notes/unique.md"
    assert row["source_id"] == "code"


def test_bare_path_ambiguous_returns_none(conn):
    # Same path under two sources -> bare-path lookup sees 2 rows and refuses;
    # the handle isn't an ext_id prefix either, so resolution is None.
    _add_doc(conn, source_id="code", path="dup/x.md", ext_id="c1")
    _add_doc(conn, source_id="other", path="dup/x.md", ext_id="o1")

    assert resolve_doc_handle(conn, "dup/x.md") is None


# --- AC3: _link_hint logs at debug (and swallows) on an inner exception ------


def test_link_hint_logs_debug_on_exception(caplog):
    class Boom:
        def execute(self, *a, **k):
            raise sqlite3.OperationalError("boom")

    fake = SimpleNamespace(db=Boom())
    r = SimpleNamespace(source_id="code", path="x.md")

    with caplog.at_level(logging.DEBUG, logger="trovex.search"):
        out = Searcher._link_hint(fake, r)

    assert out == ""  # formatting is never broken by a hint failure
    assert any(
        rec.levelno == logging.DEBUG and "link hint failed" in rec.getMessage()
        for rec in caplog.records
    )
