"""Opt-in chunk-level indexing for an fs source's markdown (task 52385ebc).

Chunks are what passage/card/section reads and the provenance link resolve against,
but every chunk is a vec_chunks row and a partition is capped by the vec0 KNN
ceiling (capacity.VEC0_K_CEILING). So the source's `chunk_markdown` flag is off by
default and this module is the only thing that turns it on: it projects the cost,
refuses (journaling why) when the partition would pass the ceiling, otherwise sets
the flag and backfills the docs that were indexed before it. Docs indexed after
that are chunked by Indexer._upsert_doc."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .capacity import VEC0_K_CEILING, partition_counts
from .chunking import CHUNKER_VERSION as MD_CHUNKER_VERSION
from .chunking import chunk_markdown
from .db import sync_doc_chunks
from .indexer import MARKDOWN_EXTENSIONS, Indexer
from .sources import get_source
from .sync import _journal

BACKFILL_BATCH = 32  # chunks embedded + committed per write burst


def _require(indexer: Indexer, source_id: str) -> dict:
    row = get_source(indexer.db, source_id)
    if row is None:
        raise ValueError(f"unknown or disabled source {source_id!r}")
    if row["kind"] != "fs":
        raise ValueError(f"chunk_markdown applies to fs sources, {source_id!r} is {row['kind']!r}")
    return row


def _unchunked_md_docs(indexer: Indexer, source_id: str) -> list:
    rows = indexer.db.execute(
        """SELECT d.id, d.title, d.absolute_path FROM docs d
           WHERE d.source_id = ? AND d.workspace_id = 'default' AND d.content IS NULL
             AND NOT EXISTS (SELECT 1 FROM chunks c WHERE c.doc_id = d.id)
           ORDER BY d.id""",
        (source_id,),
    ).fetchall()
    return [r for r in rows if Path(r["absolute_path"]).suffix.lower().lstrip(".") in MARKDOWN_EXTENSIONS]


def _read(row) -> str | None:
    try:
        return Path(row["absolute_path"]).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None  # vanished since the last index: gc_source's business, not ours


def project_markdown_chunks(indexer: Indexer, source_id: str) -> dict:
    """What flipping the flag on would add, without writing anything."""
    _require(indexer, source_id)
    docs = _unchunked_md_docs(indexer, source_id)
    new_chunks = tokens = 0
    for d in docs:
        content = _read(d)
        if content is None:
            continue
        chunks = chunk_markdown(content)
        new_chunks += len(chunks)
        tokens += sum(c.tokens_est for c in chunks)
    current = partition_counts(indexer.db).get(source_id, {}).get("chunks", 0)
    return {
        "source_id": source_id,
        "docs": len(docs),
        "new_chunks": new_chunks,
        "embed_tokens": tokens,
        "current_chunks": current,
        "ceiling": VEC0_K_CEILING,
    }


def _set_flag(indexer: Indexer, source_id: str, on: bool) -> None:
    db = indexer.db
    cfg = json.loads(db.execute("SELECT config FROM sources WHERE id = ?", (source_id,)).fetchone()["config"])
    cfg["chunk_markdown"] = on
    db.execute("UPDATE sources SET config = ? WHERE id = ?", (json.dumps(cfg), source_id))
    db.commit()


def enable_chunk_markdown(indexer: Indexer, source_id: str) -> dict:
    _require(indexer, source_id)
    started = time.time()
    proj = project_markdown_chunks(indexer, source_id)
    total = proj["current_chunks"] + proj["new_chunks"]
    if total > VEC0_K_CEILING:
        reason = (
            f"chunk_markdown would put partition {source_id!r} at {total} chunks "
            f"({proj['current_chunks']} now + {proj['new_chunks']} new), over the vec0 KNN "
            f"ceiling of {VEC0_K_CEILING}; left off"
        )
        _journal(indexer, source_id, "guard", started, error=reason)
        return {"enabled": False, "reason": reason, **proj}
    _set_flag(indexer, source_id, True)
    db = indexer.db
    pending: list[tuple[int, str]] = []
    written = 0
    for d in _unchunked_md_docs(indexer, source_id):
        content = _read(d)
        if content is None:
            continue
        pending.extend(
            sync_doc_chunks(db, d["id"], content, d["title"] or "", chunk_markdown, chunker_version=MD_CHUNKER_VERSION)
        )
        if len(pending) >= BACKFILL_BATCH:
            written += len(pending)
            indexer._commit_progress([], pending)
            pending = []
    written += len(pending)
    indexer._commit_progress([], pending)
    return {"enabled": True, "chunks": written, **proj}


def disable_chunk_markdown(indexer: Indexer, source_id: str) -> int:
    """Flag off and purge this source's markdown chunks: with the flag off nothing
    would keep them in step with the files, so they would go stale. Returns rows purged."""
    _require(indexer, source_id)
    _set_flag(indexer, source_id, False)
    db = indexer.db
    purged = 0
    rows = db.execute(
        """SELECT c.id, d.path FROM chunks c JOIN docs d ON d.id = c.doc_id
           WHERE d.source_id = ? AND d.workspace_id = 'default'""",
        (source_id,),
    ).fetchall()
    for r in rows:
        if Path(r["path"]).suffix.lower().lstrip(".") not in MARKDOWN_EXTENSIONS:
            continue  # code chunks are not this flag's
        db.execute("DELETE FROM vec_chunks WHERE rowid = ?", (r["id"],))
        db.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (r["id"],))
        db.execute("DELETE FROM chunks WHERE id = ?", (r["id"],))
        purged += 1
    db.commit()
    return purged
