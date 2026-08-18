"""Live filesystem-watch → debounced, scoped incremental re-index.

Sits on top of the already-merged incremental reindex(): instead of polling the
whole corpus, it watches the source roots and re-indexes ONLY the paths a file
event names. A real fs event fires regardless of mtime, so this also closes the
mtime-preserving-content-edit gap the mtime fast-path leaves.

Design: the debounce + reindex core (`notify` / `_flush`) has NO watchdog
dependency, so it is fully unit-testable without real, timing-flaky fs events.
`start()` wires a watchdog Observer that simply feeds event paths into `notify`.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from pathlib import Path

from .config import Source
from .indexer import Indexer

log = logging.getLogger("trovex.watch")


class Watcher:
    def __init__(
        self,
        indexer: Indexer,
        sources: Iterable[Source],
        *,
        debounce_sec: float = 0.5,
        on_reindex: Callable[[dict], None] | None = None,
    ) -> None:
        self.indexer = indexer
        self.sources = [s for s in sources if s.root.exists()]
        self.debounce_sec = debounce_sec
        self.on_reindex = on_reindex
        self._pending: set[str] = set()
        self._lock = threading.Lock()  # guards _pending + _timer
        self._reindex_lock = threading.Lock()  # serializes flushes (never overlap)
        self._timer: threading.Timer | None = None
        self._observer = None

    # ── debounce core (no watchdog dependency) ────────────────────────────

    def notify(self, path: str | Path) -> None:
        """Record a changed path and (re)arm the debounce timer. Rapid bursts
        collapse into a single _flush once `debounce_sec` of quiet passes."""
        with self._lock:
            self._pending.add(str(path))
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_sec, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> dict:
        """Re-index everything accumulated since the last flush. Serialized so two
        flushes never touch the DB concurrently."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()  # no-op if this call IS the timer firing
                self._timer = None
            batch = self._pending
            self._pending = set()
        if not batch:
            return {}
        with self._reindex_lock:
            stats = self.indexer.reindex_paths(batch, sources=self.sources)
        if self.on_reindex:
            try:
                self.on_reindex(stats)
            except Exception:  # noqa: BLE001 — a logging callback must never kill the watch
                log.debug("on_reindex callback failed", exc_info=True)
        return stats

    # ── watchdog wiring ───────────────────────────────────────────────────

    def start(self) -> None:
        """Begin watching the source roots. Requires the `watchdog` package."""
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        watcher = self

        class _Handler(FileSystemEventHandler):
            def on_any_event(self, event) -> None:
                if event.is_directory:
                    return
                watcher.notify(event.src_path)
                dest = getattr(event, "dest_path", None)  # moves/renames
                if dest:
                    watcher.notify(dest)

        self._observer = Observer()
        handler = _Handler()
        for s in self.sources:
            self._observer.schedule(handler, str(s.root), recursive=True)
        self._observer.start()
        log.info("watching %d source(s)", len(self.sources))

    def stop(self) -> None:
        """Stop the observer and cancel any pending timer, then flush once more so
        a change that landed inside the debounce window is not lost. Idempotent."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._flush()
