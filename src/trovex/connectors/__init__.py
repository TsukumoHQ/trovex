"""Connector registry: source.kind -> factory(source, indexer)."""

from __future__ import annotations

from .fs import FsConnector

REGISTRY: dict[str, type] = {"fs": FsConnector}


def build_connector(kind: str, source, indexer):
    """KeyError for an unregistered kind."""
    return REGISTRY[kind](source, indexer)
