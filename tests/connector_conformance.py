"""Conformance checks every Connector must pass (task 960a4b64, design 61a37a82
section 6.2). A connector test module builds a fixture exposing three hooks and
calls the check_* functions:

  connector            the Connector under test, already pointed at a source
                       holding >= 2 records
  add_record()         makes ONE new record appear (newer than anything polled)
  break_record()       makes one existing record unreadable; returns its external_id
                       (the connector must report it as an inline RecordFailure, not raise)
"""

from __future__ import annotations

from trovex.connectors.base import Cursor, RecordFailure, SlimRef, SourceRecord


def drain(gen):
    """Consume a poll() generator: (items, the Cursor carried by StopIteration.value)."""
    items = []
    while True:
        try:
            items.append(next(gen))
        except StopIteration as stop:
            return items, stop.value


def check_list_slim(connector) -> list[SlimRef]:
    refs = list(connector.list_slim())
    assert len(refs) >= 2
    for ref in refs:
        assert isinstance(ref, SlimRef)
        assert ref.external_id and isinstance(ref.remote_version, str)
        assert isinstance(ref.acl, list) and isinstance(ref.parents, list)
    assert len({r.external_id for r in refs}) == len(refs), "external_id must be unique"
    return refs


def check_fetch_returns_one_record(connector) -> None:
    ref = check_list_slim(connector)[0]
    rec = connector.fetch(ref)
    assert isinstance(rec, SourceRecord)
    assert rec.external_id == ref.external_id
    assert rec.markdown and rec.remote_version == ref.remote_version


def check_poll_resumes_from_cursor(connector, add_record) -> None:
    first, cursor = drain(connector.poll(None))
    assert isinstance(cursor, Cursor) and cursor.opaque
    assert {r.external_id for r in first if isinstance(r, SourceRecord)} == {
        r.external_id for r in connector.list_slim()
    }
    assert cursor.seen_count == len(first)

    again, cursor2 = drain(connector.poll(cursor))
    assert again == [], "a poll from the returned cursor must yield nothing new"
    assert cursor2.opaque == cursor.opaque

    new_id = add_record()
    resumed, cursor3 = drain(connector.poll(cursor2))
    assert [r.external_id for r in resumed] == [new_id], "resume yields ONLY the new record"
    assert cursor3.opaque != cursor2.opaque


def check_failures_are_inline(connector, break_record) -> None:
    broken = break_record()
    items, cursor = drain(connector.poll(None))
    failures = [i for i in items if isinstance(i, RecordFailure)]
    records = [i for i in items if isinstance(i, SourceRecord)]
    assert [f.external_id for f in failures] == [broken]
    assert failures[0].error and failures[0].retryable is True
    assert records, "one bad record must not abort the rest of the poll"
    assert isinstance(cursor, Cursor)
