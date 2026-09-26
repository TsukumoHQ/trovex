"""FsConnector: the filesystem walk behind the Connector protocol.

The cursor is the newest mtime_ns already yielded. An mtime cursor cannot see a file
that arrives with an OLDER mtime (rsync -t, git checkout); the `scan_source` job's
full reindex is the backstop for that. Deletions are not poll's job — gc_source
diffs list_slim against the index."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from pathlib import Path

from ..config import Source
from ..indexer import Indexer
from .base import Cursor, RecordFailure, SlimRef, SourceRecord


class FsConnector:
    kind = "fs"

    def __init__(self, source: Source, indexer: Indexer) -> None:
        self.source = source
        self.indexer = indexer
        self._root = source.root.resolve()

    def _rel(self, path: Path) -> str:
        return path.relative_to(self.source.root).as_posix()

    @staticmethod
    def _parents(rel: str) -> list[str]:
        parent = Path(rel).parent.as_posix()
        return [] if parent == "." else [parent]

    def list_slim(self) -> Iterator[SlimRef]:
        for path in self.indexer.scan(self.source.root):
            try:
                mtime_ns = path.stat().st_mtime_ns
            except OSError:
                continue  # vanished mid-walk: not listed, so gc sees it as gone
            rel = self._rel(path)
            yield SlimRef(rel, str(mtime_ns), [], self._parents(rel))

    def _record(self, rel: str, path: Path) -> SourceRecord:
        content = path.read_text(encoding="utf-8", errors="replace")
        st = path.stat()
        return SourceRecord(
            external_id=rel,
            title=self.indexer._extract_title(content, path.name),
            markdown=content,
            record_locator={"path": rel},
            remote_version=str(st.st_mtime_ns),
            remote_updated_at=st.st_mtime,
            parents=self._parents(rel),
        )

    def poll(self, cursor: Cursor | None) -> Generator[SourceRecord | RecordFailure, None, Cursor]:
        after = int((cursor.opaque if cursor else {}).get("mtime_ns", 0))
        seen = cursor.seen_count if cursor else 0
        fresh = []
        for path in self.indexer.scan(self.source.root):
            try:
                mtime_ns = path.stat().st_mtime_ns
            except OSError:
                continue
            if mtime_ns > after:
                fresh.append((mtime_ns, path))
        newest = after
        for mtime_ns, path in sorted(fresh):
            rel = self._rel(path)
            newest = max(newest, mtime_ns)
            try:
                record = self._record(rel, path)
            except OSError as e:
                yield RecordFailure(rel, str(e), retryable=True)
                continue
            seen += 1
            yield record
        return Cursor({"mtime_ns": newest}, seen)

    def fetch(self, ref: SlimRef) -> SourceRecord:
        path = (self._root / ref.external_id).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"external_id {ref.external_id!r} escapes the source root")
        return self._record(ref.external_id, path)
