"""Process-wide singleton for embedder + searcher (avoids reloading model)."""

from __future__ import annotations

from dataclasses import dataclass

import fastembed

from .config import Settings
from .indexer import Indexer
from .search import Searcher


@dataclass
class AppState:
    settings: Settings
    embedder: fastembed.TextEmbedding
    searcher: Searcher
    indexer: Indexer


_state: AppState | None = None


def get_state() -> AppState:
    global _state
    if _state is None:
        settings = Settings()
        embedder = fastembed.TextEmbedding(model_name=settings.embed_model)
        searcher = Searcher(settings, embedder=embedder)
        indexer = Indexer(settings, embedder=embedder)
        _state = AppState(
            settings=settings, embedder=embedder,
            searcher=searcher, indexer=indexer,
        )
    return _state


def reset_state() -> None:
    """Used by tests."""
    global _state
    _state = None
