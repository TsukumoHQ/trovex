"""Process-wide singleton for embedder + searcher (avoids reloading model)."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from .config import Settings
from .embedder import embedder_from_settings
from .index_jobs import Applier
from .indexer import Indexer
from .search import Searcher
from .store import SqliteStore

log = logging.getLogger("trovex.state")


@dataclass
class AppState:
    settings: Settings
    embedder: Any
    searcher: Searcher
    indexer: Indexer
    store: SqliteStore
    # Guards index_jobs' read-modify-write transactions (task dab8766b,
    # replacing 085f1d69/67ebd68c's per-request reindex_lock): enqueue()'s
    # coalesce-or-insert decision and the Applier's claim/finish steps all take
    # this, so two threads never race the same index_jobs row.
    index_jobs_lock: threading.Lock = field(default_factory=threading.Lock)
    _applier: Applier | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def applier(self) -> Applier:
        """The single reindex-queue drainer for this process, bound lazily to
        this state's indexer — most tests build AppState directly and never
        touch the queue, so nothing here runs unless something actually reads
        .applier (e.g. the server's lifespan, or a test exercising the queue)."""
        if self._applier is None:
            self._applier = Applier(self.indexer, self.store, lock=self.index_jobs_lock)
        return self._applier


_state: AppState | None = None


def get_state() -> AppState:
    global _state
    if _state is None:
        settings = Settings()
        # Resolve the effective write token: fail-closed by default (auto-generate
        # + persist a per-instance token) unless an explicit token or the
        # TROVEX_ALLOW_UNAUTH_WRITES opt-in is set. See config.resolve_write_token.
        settings.write_token = settings.resolve_write_token()
        if not settings.write_token:
            log.warning(
                "TROVEX_ALLOW_UNAUTH_WRITES is set — write endpoints accept "
                "ANONYMOUS writes (no token). Only safe on localhost / a trusted "
                "network; set TROVEX_WRITE_TOKEN to require auth."
            )
        embedder = embedder_from_settings(settings)
        searcher = Searcher(settings, embedder=embedder)
        indexer = Indexer(settings, embedder=embedder)
        store = SqliteStore(settings, embedder=embedder)
        _state = AppState(
            settings=settings,
            embedder=embedder,
            searcher=searcher,
            indexer=indexer,
            store=store,
        )
    return _state


def reset_state() -> None:
    """Used by tests."""
    global _state
    _state = None
