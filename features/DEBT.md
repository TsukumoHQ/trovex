# Tech-debt backlog — auto-collected by the niwa scribe

- [LEGACY_OPPORTUNITY]: store.py::_insert_chunks previously duplicated Merkle-hash chunk-sync logic inline (MCP-write-path only). Now delegates to the shared db.sync_doc_chunks — any future chunker (e.g. a markdown-chunker upgrade) can reuse the same sync path without re-deriving hash-reuse/cascade-prune semantics.
