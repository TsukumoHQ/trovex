"""The connector contract (steal #5, design 61a37a82 section 6.2).

Onyx's five protocols collapsed to three: `list_slim` (ids + version, cheap, for
GC), `poll` (resumable; the next Cursor is the generator's return value, and a
bad record is yielded inline as a RecordFailure instead of aborting the run) and
`fetch` (one record on demand). The source alone owns its opaque cursor (Airbyte)."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class SlimRef:
    external_id: str
    remote_version: str
    acl: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Cursor:
    opaque: dict[str, Any]
    seen_count: int = 0


@dataclass(frozen=True)
class SourceRecord:
    external_id: str
    title: str
    markdown: str
    sections: list[dict] = field(default_factory=list)  # [{anchor, text, link}]
    source_url: str | None = None
    record_locator: dict = field(default_factory=dict)
    remote_version: str = ""
    remote_updated_at: float | None = None
    owners: list[str] = field(default_factory=list)
    acl: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)
    kind: str = "doc"
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RecordFailure:
    external_id: str | None
    error: str
    retryable: bool = True
    missed_range: dict | None = None


@runtime_checkable
class Connector(Protocol):
    kind: str

    def list_slim(self) -> Iterator[SlimRef]: ...

    def poll(
        self, cursor: Cursor | None
    ) -> Generator[SourceRecord | RecordFailure, None, Cursor]: ...

    def fetch(self, ref: SlimRef) -> SourceRecord: ...
