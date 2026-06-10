"""ctx-owned doc store — the write side of the refonte.

Where the router *indexes* files that live on disk, the Store lets ctx *own*
a doc's content directly (records, memory, coordination). Owned docs live under
a virtual ``source_id='ctx'`` that the filesystem indexer never scans — so they
are never purged for lacking a file on disk (see indexer.reindex cleanup).

The ``Store`` protocol is the swappable seam (Pôle A → Supabase): callers
address docs by an **opaque stable ext_id**, never by filesystem path, so a
substrate swap is a drop-in. ``SqliteStore`` is the Pôle A implementation,
backed by the same sqlite-vec DB the rest of ctx uses.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Protocol

import sqlite_vec

from .config import Settings
from .db import open_db
from .embedder import Embedder, build_embedder

CTX_SOURCE_ID = "ctx"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
TITLE_RE = re.compile(r"^\s*#\s+(.+)$", re.MULTILINE)


@dataclass
class StoredDoc:
    ext_id: str
    title: str
    content: str
    kind: str | None
    status: str
    tokens_est: int
    mtime: float


class Store(Protocol):
    """Swappable system-of-record for ctx-owned docs (Pôle A sqlite ↔ B Supabase)."""

    def put(self, content: str, *, kind: str | None = None,
            ext_id: str | None = None, title: str | None = None,
            author: str | None = None) -> str: ...

    def get(self, ext_id: str) -> StoredDoc | None: ...

    def list_docs(self) -> list[StoredDoc]: ...

    def delete(self, ext_id: str) -> bool: ...


class SqliteStore:
    """Pôle A: ctx-owned docs as rows in the shared sqlite-vec DB."""

    def __init__(self, settings: Settings, embedder: Embedder | None = None):
        self.settings = settings
        self.db: sqlite3.Connection = open_db(
            settings.data_dir / "ctx.db", settings.resolved_embed_dim()
        )
        self.embedder = embedder or build_embedder(settings.embed_model)
        # Serialize writes: the sqlite connection is shared across the server's
        # worker threads, and put() is a multi-statement insert+embed+commit.
        self._lock = threading.Lock()

    def put(self, content: str, *, kind: str | None = None,
            ext_id: str | None = None, title: str | None = None,
            author: str | None = None) -> str:
        """Create or replace a ctx-owned doc; return its opaque ext_id."""
        ext_id = ext_id or uuid.uuid4().hex
        title = title or _extract_title(content)
        now = time.time()
        tokens_est = len(content) // 4
        size = len(content.encode("utf-8"))

        with self._lock:
            existing = self.db.execute(
                "SELECT id FROM docs WHERE ext_id = ?", (ext_id,)
            ).fetchone()

            if existing:
                doc_id = existing["id"]
                self.db.execute(
                    """UPDATE docs SET content=?, title=?, kind=?, tokens_est=?,
                           size_bytes=?, mtime=?, last_indexed=?, author_agent=?
                       WHERE id=?""",
                    (content, title, kind, tokens_est, size, now, now, author, doc_id),
                )
            else:
                cur = self.db.execute(
                    """INSERT INTO docs
                           (source_id, path, absolute_path, content_hash, size_bytes,
                            tokens_est, mtime, first_indexed, last_indexed, title,
                            author_agent, content, ext_id, kind)
                       VALUES (?, ?, '', '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (CTX_SOURCE_ID, ext_id, size, tokens_est,
                     now, now, now, title, author, content, ext_id, kind),
                )
                doc_id = cur.lastrowid

            self._embed(doc_id, content, title)
            self.db.commit()
        return ext_id

    def get(self, ext_id: str) -> StoredDoc | None:
        row = self.db.execute(
            """SELECT ext_id, title, content, kind, status, tokens_est, mtime
               FROM docs WHERE ext_id = ?""",
            (ext_id,),
        ).fetchone()
        if not row or row["content"] is None:
            return None
        return _row_to_doc(row)

    def list_docs(self) -> list[StoredDoc]:
        rows = self.db.execute(
            """SELECT ext_id, title, content, kind, status, tokens_est, mtime
               FROM docs WHERE source_id = ? ORDER BY mtime DESC""",
            (CTX_SOURCE_ID,),
        ).fetchall()
        return [_row_to_doc(r) for r in rows if r["content"] is not None]

    def delete(self, ext_id: str) -> bool:
        """Remove a ctx-owned doc (row + its embedding). True if it existed."""
        with self._lock:
            row = self.db.execute(
                "SELECT id FROM docs WHERE ext_id = ?", (ext_id,)
            ).fetchone()
            if not row:
                return False
            self.db.execute("DELETE FROM vec_docs WHERE rowid = ?", (row["id"],))
            self.db.execute("DELETE FROM docs WHERE id = ?", (row["id"],))
            self.db.commit()
            return True

    def put_batch(self, items: list[dict]) -> list[str]:
        """Bulk insert/update + a single batched embed call. For migrations.

        Each item: {content, kind?, ext_id?, title?}. Embeds all texts in one
        go (the embedder batches internally) — far faster than per-doc put().
        """
        now = time.time()
        to_embed: list[tuple[int, str]] = []
        ext_ids: list[str] = []
        with self._lock:
            for it in items:
                content = it["content"]
                ext_id = it.get("ext_id") or uuid.uuid4().hex
                title = it.get("title") or _extract_title(content)
                kind = it.get("kind")
                size = len(content.encode("utf-8"))
                tok = len(content) // 4
                existing = self.db.execute(
                    "SELECT id FROM docs WHERE ext_id = ?", (ext_id,)
                ).fetchone()
                if existing:
                    doc_id = existing["id"]
                    self.db.execute(
                        """UPDATE docs SET content=?, title=?, kind=?, tokens_est=?,
                               size_bytes=?, mtime=?, last_indexed=? WHERE id=?""",
                        (content, title, kind, tok, size, now, now, doc_id),
                    )
                else:
                    cur = self.db.execute(
                        """INSERT INTO docs
                               (source_id, path, absolute_path, content_hash,
                                size_bytes, tokens_est, mtime, first_indexed,
                                last_indexed, title, content, ext_id, kind)
                           VALUES (?, ?, '', '', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (CTX_SOURCE_ID, ext_id, size, tok, now, now, now,
                         title, content, ext_id, kind),
                    )
                    doc_id = cur.lastrowid
                ext_ids.append(ext_id)
                text = f"{title}\n\n{FRONTMATTER_RE.sub('', content)}"[:8000]
                to_embed.append((doc_id, text))

            embeddings = list(self.embedder.embed([t for _, t in to_embed]))
            for (doc_id, _), emb in zip(to_embed, embeddings, strict=True):
                self.db.execute("DELETE FROM vec_docs WHERE rowid = ?", (doc_id,))
                self.db.execute(
                    "INSERT INTO vec_docs(rowid, embedding) VALUES (?, ?)",
                    (doc_id, sqlite_vec.serialize_float32(emb.tolist())),
                )
            self.db.commit()
        return ext_ids

    def _embed(self, doc_id: int, content: str, title: str) -> None:
        text = f"{title}\n\n{FRONTMATTER_RE.sub('', content)}"[:8000]
        emb = next(iter(self.embedder.embed([text])))
        self.db.execute("DELETE FROM vec_docs WHERE rowid = ?", (doc_id,))
        self.db.execute(
            "INSERT INTO vec_docs(rowid, embedding) VALUES (?, ?)",
            (doc_id, sqlite_vec.serialize_float32(emb.tolist())),
        )


def _row_to_doc(row: sqlite3.Row) -> StoredDoc:
    return StoredDoc(
        ext_id=row["ext_id"], title=row["title"] or "", content=row["content"],
        kind=row["kind"], status=row["status"], tokens_est=row["tokens_est"],
        mtime=row["mtime"],
    )


def _extract_title(content: str) -> str:
    stripped = FRONTMATTER_RE.sub("", content)
    m = TITLE_RE.search(stripped[:2000])
    return m.group(1).strip() if m else "Untitled"


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def extract_section(content: str, heading: str) -> str | None:
    """Return the markdown section under `heading` — from that heading down to
    the next same-or-higher-level heading. None if the heading isn't found.

    Lets ctx_read serve only the relevant slice of a long doc instead of the
    whole body (the token-efficiency north star).
    """
    target = heading.strip().lstrip("#").strip().lower()
    lines = content.splitlines()
    start = level = None
    for i, ln in enumerate(lines):
        m = HEADING_RE.match(ln)
        if m and m.group(2).strip().lower() == target:
            start, level = i, len(m.group(1))
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = HEADING_RE.match(lines[j])
        if m and len(m.group(1)) <= level:
            end = j
            break
    return "\n".join(lines[start:end]).strip()
