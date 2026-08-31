"""Process-wide singleton for embedder + searcher (avoids reloading model)."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from .config import Settings
from .embedder import embedder_from_settings
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
    # Single-flight guard for /api/reindex (085f1d69): a 2nd concurrent reindex
    # piling onto the same long-running write is what turned a slow reindex into
    # a multi-minute reader stall on prod. Non-blocking acquire only — the route
    # rejects instead of queuing.
    reindex_lock: threading.Lock = field(default_factory=threading.Lock)


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
