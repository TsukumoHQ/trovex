"""trovex-owned doc store — the write side of the refonte.

Where the router *indexes* files that live on disk, the Store lets trovex *own*
a doc's content directly (records, memory, coordination). Owned docs live under
a virtual ``source_id='trovex'`` that the filesystem indexer never scans — so they
are never purged for lacking a file on disk (see indexer.reindex cleanup).

The ``Store`` protocol is the swappable seam (Pôle A → Supabase): callers
address docs by an **opaque stable ext_id**, never by filesystem path, so a
substrate swap is a drop-in. ``SqliteStore`` is the Pôle A implementation,
backed by the same sqlite-vec DB the rest of trovex uses.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Protocol

import sqlite_vec

from .chunking import chunk_markdown
from .config import Settings
from .db import like_escape, open_db
from .embedder import Embedder, build_embedder

TROVEX_SOURCE_ID = "trovex"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
TITLE_RE = re.compile(r"^\s*#\s+(.+)$", re.MULTILINE)
ANY_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$", re.MULTILINE)
FM_TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)


@dataclass
class StoredDoc:
    ext_id: str
    title: str
    content: str
    kind: str | None
    status: str
    tokens_est: int
    mtime: float
    tags: list[str] = field(default_factory=list)
    origin: str | None = None


class Store(Protocol):
    """Swappable system-of-record for trovex-owned docs (Pôle A sqlite ↔ B Supabase)."""

    def put(
        self,
        content: str,
        *,
        kind: str | None = None,
        ext_id: str | None = None,
        title: str | None = None,
        author: str | None = None,
        tags: list[str] | None = None,
    ) -> str: ...

    def get(self, ext_id: str) -> StoredDoc | None: ...

    def list_docs(self) -> list[StoredDoc]: ...

    def delete(self, ext_id: str) -> bool: ...


class SqliteStore:
    """Pôle A: trovex-owned docs as rows in the shared sqlite-vec DB."""

    def __init__(self, settings: Settings, embedder: Embedder | None = None):
        self.settings = settings
        self.db: sqlite3.Connection = open_db(
            settings.data_dir / "trovex.db", settings.resolved_embed_dim()
        )
        self.embedder = embedder or build_embedder(settings.embed_model)
        # Serialize writes: the sqlite connection is shared across the server's
        # worker threads, and put() is a multi-statement insert+embed+commit.
        self._lock = threading.Lock()

    def put(
        self,
        content: str,
        *,
        kind: str | None = None,
        ext_id: str | None = None,
        title: str | None = None,
        author: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Create or replace a trovex-owned doc; return its opaque ext_id."""
        ext_id = ext_id or uuid.uuid4().hex
        title = title or _extract_title(content)
        now = time.time()
        tokens_est = len(content) // 4
        size = len(content.encode("utf-8"))

        with self._lock:
            existing = self.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext_id,)).fetchone()

            if existing:
                doc_id = existing["id"]
                # Snapshot the current content before overwriting it (undo-able).
                old = self.db.execute(
                    "SELECT content, title FROM docs WHERE id = ?", (doc_id,)
                ).fetchone()
                if old and old["content"] is not None:
                    self.db.execute(
                        "INSERT INTO doc_versions(doc_id, content, title, ts) VALUES (?, ?, ?, ?)",
                        (doc_id, old["content"], old["title"], now),
                    )
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
                    (
                        TROVEX_SOURCE_ID,
                        ext_id,
                        size,
                        tokens_est,
                        now,
                        now,
                        now,
                        title,
                        author,
                        content,
                        ext_id,
                        kind,
                    ),
                )
                doc_id = cur.lastrowid

            self._embed(doc_id, content, title)
            self._embed_chunks(self._insert_chunks(doc_id, content, title))
            self._set_tags(doc_id, list(tags or []) + ([f"kind/{kind}"] if kind else []))
            self.db.commit()
            # Rebranch dedup onto the live write path: the indexer that used to
            # run compute_status() is retired, so flag near-duplicates here as
            # docs land. Best-effort — never let it block a write.
            try:
                from .status import detect_duplicate_for

                detect_duplicate_for(self.db, self.settings, doc_id)
            except Exception:
                pass
        return ext_id

    def check_duplicate(self, content: str, title: str | None = None) -> dict | None:
        """Pre-insert near-duplicate check for the interactive write path.

        Embeds `content` TRANSIENTLY (no insert) and returns the nearest existing
        CANONICAL doc within the cosine threshold — so trovex_write can block-and-point
        ('this duplicates <id> — update it or pass force') instead of creating another
        near-copy (43% of the store was such bloat). Returns {ext_id, title, similarity}
        or None. Mirrors detect_duplicate_for's threshold; never raises into the caller.
        """
        try:
            text = f"{title or ''}\n\n{FRONTMATTER_RE.sub('', content)}"[:8000]
            emb = next(iter(self.embedder.embed([text])))
            qv = sqlite_vec.serialize_float32(emb.tolist())
            threshold = self.settings.dup_cosine_threshold
            with self._lock:
                neighbours = self.db.execute(
                    """SELECT v.rowid, v.distance, d.ext_id, d.title, d.kind, d.status
                       FROM vec_docs v JOIN docs d ON d.id = v.rowid
                       WHERE v.embedding MATCH ? AND k = 3 ORDER BY v.distance""",
                    (qv,),
                ).fetchall()
            for nb in neighbours:
                if nb["kind"] == "record" or nb["status"] not in ("canonical", "plan"):
                    continue
                similarity = 1.0 - nb["distance"] / 2
                if similarity < threshold:
                    break  # neighbours sorted by distance asc → none closer remain
                return {
                    "ext_id": nb["ext_id"],
                    "title": nb["title"],
                    "similarity": round(similarity, 4),
                }
        except Exception:
            return None  # a guard failure must never block a legit write
        return None

    def get(self, ext_id: str) -> StoredDoc | None:
        row = self.db.execute(
            """SELECT d.ext_id, d.title, d.content, d.kind, d.status, d.tokens_est,
                      d.mtime, d.origin, GROUP_CONCAT(t.tag) AS tags
               FROM docs d LEFT JOIN doc_tags t ON t.doc_id = d.id
               WHERE d.ext_id = ? GROUP BY d.id""",
            (ext_id,),
        ).fetchone()
        if not row or row["content"] is None:
            return None
        return _row_to_doc(row)

    def resolve_ext_id(self, ref: str) -> str | None:
        """Resolve a full OR short/prefix ext_id to the unique full ext_id. Exact match
        wins; otherwise a unique prefix match; None if absent OR ambiguous (>1 match).
        Lets a caller pass a short id (e.g. `b8e05fa3`) instead of the full 32-char id
        without silently getting `(not found)`."""
        ref = (ref or "").strip()
        if not ref:
            return None
        exact = self.db.execute("SELECT ext_id FROM docs WHERE ext_id = ?", (ref,)).fetchone()
        if exact:
            return exact["ext_id"]
        rows = self.db.execute(
            "SELECT ext_id FROM docs WHERE ext_id LIKE ? ESCAPE '\\' LIMIT 2",
            (like_escape(ref) + "%",),
        ).fetchall()
        return rows[0]["ext_id"] if len(rows) == 1 else None

    def list_docs(
        self,
        *,
        tag: str | None = None,
        kind: str | None = None,
        q: str | None = None,
        limit: int = 60,
        offset: int = 0,
    ) -> list[StoredDoc]:
        where = ["d.source_id = ?"]
        params: list = [TROVEX_SOURCE_ID]
        if tag:
            where.append("d.id IN (SELECT doc_id FROM doc_tags WHERE tag = ?)")
            params.append(tag)
        if kind:
            where.append("d.kind = ?")
            params.append(kind)
        if q:
            # Lightweight browse filter (title/content substring) — NOT semantic
            # search; that lives on /search via search_chunks. Escape LIKE
            # wildcards so a bare `%`/`_` filters literally, not match-all.
            where.append("(d.title LIKE ? ESCAPE '\\' OR d.content LIKE ? ESCAPE '\\')")
            pat = f"%{like_escape(q)}%"
            params += [pat, pat]
        rows = self.db.execute(
            f"""SELECT d.ext_id, d.title, d.content, d.kind, d.status, d.tokens_est,
                       d.mtime, GROUP_CONCAT(t.tag) AS tags
                FROM docs d LEFT JOIN doc_tags t ON t.doc_id = d.id
                WHERE {" AND ".join(where)}
                GROUP BY d.id ORDER BY d.mtime DESC LIMIT ? OFFSET ?""",
            (*params, limit, offset),
        ).fetchall()
        return [_row_to_doc(r) for r in rows if r["content"] is not None]

    def count_docs(
        self, *, tag: str | None = None, kind: str | None = None, q: str | None = None
    ) -> int:
        where = ["source_id = ?"]
        params: list = [TROVEX_SOURCE_ID]
        if tag:
            where.append("id IN (SELECT doc_id FROM doc_tags WHERE tag = ?)")
            params.append(tag)
        if kind:
            where.append("kind = ?")
            params.append(kind)
        if q:
            where.append("(title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')")
            pat = f"%{like_escape(q)}%"
            params += [pat, pat]
        return self.db.execute(
            f"SELECT COUNT(*) AS c FROM docs WHERE {' AND '.join(where)}", params
        ).fetchone()["c"]

    def delete(self, ext_id: str) -> bool:
        """Remove a trovex-owned doc (row + its embedding) by ext_id. True if it existed."""
        with self._lock:
            row = self.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext_id,)).fetchone()
            if not row:
                return False
            self._delete_cascade_locked(row["id"])
            self.db.commit()
            return True

    def delete_by_id(self, doc_id: int) -> bool:
        """Remove a doc by its internal id (handles rows with a NULL ext_id, e.g.
        agent/MCP-written docs). Same cascade as delete(). True if it existed."""
        with self._lock:
            row = self.db.execute("SELECT id FROM docs WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                return False
            self._delete_cascade_locked(doc_id)
            self.db.commit()
            return True

    def _delete_cascade_locked(self, doc_id: int) -> None:
        """Proper cascade delete by internal id — no orphan vec rows. Caller holds _lock
        and commits. Removes chunks (+ vec_chunks/chunks_fts), doc_versions, vec_docs, docs."""
        for c in self.db.execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,)).fetchall():
            self.db.execute("DELETE FROM vec_chunks WHERE rowid = ?", (c["id"],))
            self.db.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (c["id"],))
        self.db.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        self.db.execute("DELETE FROM doc_versions WHERE doc_id = ?", (doc_id,))
        self.db.execute("DELETE FROM vec_docs WHERE rowid = ?", (doc_id,))
        self.db.execute("DELETE FROM docs WHERE id = ?", (doc_id,))

    def put_batch(self, items: list[dict], *, embed_chunks: bool = False) -> list[str]:
        """Bulk insert/update + a single batched embed call. For migrations + import.

        Each item: {content, kind?, ext_id?, title?, mtime?, tags?}. ``mtime`` (a
        unix timestamp) sets the doc's date — used by ``import`` to preserve a
        file's real creation date (git/frontmatter) instead of stamping ``now``;
        omit it to default to now. ``tags`` are attached after insert (the
        ``kind/<kind>`` facet is added automatically, matching put()).

        Embeds all doc texts in one go (the embedder batches internally) — far
        faster than per-doc put(). Pass ``embed_chunks=True`` to also (re)chunk +
        embed every doc for chunk-level retrieval, so the import is queryable
        without a separate backfill-chunks pass.
        """
        now = time.time()
        to_embed: list[tuple[int, str]] = []
        ext_ids: list[str] = []
        tag_jobs: list[tuple[int, list[str]]] = []
        chunk_pairs: list[tuple[int, str]] = []
        with self._lock:
            for it in items:
                content = it["content"]
                ext_id = it.get("ext_id") or uuid.uuid4().hex
                title = it.get("title") or _extract_title(content)
                kind = it.get("kind")
                mtime = float(it.get("mtime") or now)
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
                        (content, title, kind, tok, size, mtime, now, doc_id),
                    )
                else:
                    cur = self.db.execute(
                        """INSERT INTO docs
                               (source_id, path, absolute_path, content_hash,
                                size_bytes, tokens_est, mtime, first_indexed,
                                last_indexed, title, content, ext_id, kind)
                           VALUES (?, ?, '', '', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            TROVEX_SOURCE_ID,
                            ext_id,
                            size,
                            tok,
                            mtime,
                            mtime,
                            now,
                            title,
                            content,
                            ext_id,
                            kind,
                        ),
                    )
                    doc_id = cur.lastrowid
                ext_ids.append(ext_id)
                text = f"{title}\n\n{FRONTMATTER_RE.sub('', content)}"[:8000]
                to_embed.append((doc_id, text))
                if it.get("tags") is not None or kind:
                    tags = list(it.get("tags") or [])
                    if kind:
                        tags.append(f"kind/{kind}")
                    tag_jobs.append((doc_id, tags))
                if embed_chunks:
                    chunk_pairs.extend(self._insert_chunks(doc_id, content, title))

            embeddings = list(self.embedder.embed([t for _, t in to_embed]))
            for (doc_id, _), emb in zip(to_embed, embeddings, strict=True):
                self.db.execute("DELETE FROM vec_docs WHERE rowid = ?", (doc_id,))
                self.db.execute(
                    "INSERT INTO vec_docs(rowid, embedding) VALUES (?, ?)",
                    (doc_id, sqlite_vec.serialize_float32(emb.tolist())),
                )
            for doc_id, tags in tag_jobs:
                self._set_tags(doc_id, tags)
            self._embed_chunks(chunk_pairs)
            self.db.commit()
        return ext_ids

    def _insert_chunks(self, doc_id: int, content: str, title: str) -> list[tuple[int, str]]:
        """(Re)chunk a doc into the chunks table; return (chunk_id, embed_text)."""
        for c in self.db.execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,)).fetchall():
            self.db.execute("DELETE FROM vec_chunks WHERE rowid = ?", (c["id"],))
            self.db.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (c["id"],))
        self.db.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        pairs: list[tuple[int, str]] = []
        for ch in chunk_markdown(content):
            cur = self.db.execute(
                """INSERT INTO chunks (doc_id, chunk_index, heading_path, content, tokens_est)
                   VALUES (?, ?, ?, ?, ?)""",
                (doc_id, ch.index, " > ".join(ch.heading_path), ch.text, ch.tokens_est),
            )
            self.db.execute(
                "INSERT INTO chunks_fts(content, chunk_id) VALUES (?, ?)",
                (ch.text, cur.lastrowid),
            )
            pairs.append((cur.lastrowid, ch.embed_text(title)))
        return pairs

    def _embed_chunks(self, pairs: list[tuple[int, str]]) -> None:
        """Batch-embed chunk texts (prefix-fused) into vec_chunks."""
        if not pairs:
            return
        embs = list(self.embedder.embed([t for _, t in pairs]))
        for (cid, _), emb in zip(pairs, embs, strict=True):
            self.db.execute(
                "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                (cid, sqlite_vec.serialize_float32(emb.tolist())),
            )

    def search_chunks(
        self,
        query: str,
        limit: int = 5,
        *,
        kind: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """Hybrid chunk retrieval: vector + BM25 fused by reciprocal rank, then
        metadata-filtered. Vector finds semantic matches; BM25 catches exact terms
        (error codes, function names, ids) the embedding blurs."""
        if not query.strip():
            return []
        pool = max(limit * 6, 30)
        qemb = next(iter(self.embedder.embed([query])))
        vec_ids = [
            r["rowid"]
            for r in self.db.execute(
                "SELECT v.rowid FROM vec_chunks v WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
                (sqlite_vec.serialize_float32(qemb.tolist()), pool),
            )
        ]

        terms = re.findall(r"[a-z0-9]{2,}", query.lower())[:24]
        bm_ids: list[int] = []
        if terms:
            try:
                bm_ids = [
                    r["chunk_id"]
                    for r in self.db.execute(
                        "SELECT chunk_id FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
                        (" OR ".join(terms), pool),
                    )
                ]
            except sqlite3.OperationalError:
                bm_ids = []

        # Reciprocal rank fusion (k0=60, the standard).
        scores: dict[int, float] = {}
        for rank, cid in enumerate(vec_ids):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (60 + rank)
        for rank, cid in enumerate(bm_ids):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (60 + rank)
        ranked = sorted(scores, key=lambda c: -scores[c])

        tagset = set(tags or [])
        out: list[dict] = []
        for cid in ranked:
            r = self.db.execute(
                """SELECT c.doc_id, c.heading_path, c.content, c.tokens_est,
                          d.ext_id, d.title, d.kind, d.source_id, d.tokens_est AS doc_tokens
                   FROM chunks c JOIN docs d ON d.id = c.doc_id WHERE c.id = ?""",
                (cid,),
            ).fetchone()
            if not r:
                continue
            if kind and r["kind"] != kind:
                continue
            if source and r["source_id"] != source:
                continue
            if tagset:
                dtags = {
                    t["tag"]
                    for t in self.db.execute(
                        "SELECT tag FROM doc_tags WHERE doc_id = ?", (r["doc_id"],)
                    )
                }
                if not (tagset & dtags):
                    continue
            hit = dict(r)
            hit["score"] = scores[cid]
            out.append(hit)
            if len(out) >= limit:
                break
        return out

    def section_text(self, doc_id: int, heading_path: str) -> str:
        """Small-to-big: all chunks of a doc sharing a heading path = the section."""
        rows = self.db.execute(
            """SELECT content FROM chunks WHERE doc_id = ? AND heading_path = ?
               ORDER BY chunk_index""",
            (doc_id, heading_path),
        ).fetchall()
        return "\n\n".join(r["content"] for r in rows)

    def _set_tags(self, doc_id: int, tags: list[str]) -> None:
        self.db.execute("DELETE FROM doc_tags WHERE doc_id = ?", (doc_id,))
        for raw in tags:
            tag = raw.strip().strip("/").lower()
            if tag:
                self.db.execute(
                    "INSERT OR IGNORE INTO doc_tags(doc_id, tag) VALUES (?, ?)",
                    (doc_id, tag),
                )

    def set_tags(
        self, ext_id: str, add: list[str] | None = None, remove: list[str] | None = None
    ) -> list[str]:
        """Add/remove tags on a doc (trovex_tag tool + reader UI). Returns new set."""
        with self._lock:
            row = self.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext_id,)).fetchone()
            if not row:
                return []
            doc_id = row["id"]
            for raw in remove or []:
                self.db.execute(
                    "DELETE FROM doc_tags WHERE doc_id = ? AND tag = ?",
                    (doc_id, raw.strip().strip("/").lower()),
                )
            for raw in add or []:
                tag = raw.strip().strip("/").lower()
                if tag:
                    self.db.execute(
                        "INSERT OR IGNORE INTO doc_tags(doc_id, tag) VALUES (?, ?)",
                        (doc_id, tag),
                    )
            self.db.commit()
            return [
                r["tag"]
                for r in self.db.execute(
                    "SELECT tag FROM doc_tags WHERE doc_id = ? ORDER BY tag", (doc_id,)
                )
            ]

    def all_tags(self, limit: int = 40) -> list[tuple[str, int]]:
        """Top tags by doc count, for the filter sidebar (capped — can be many)."""
        return [
            (r["tag"], r["c"])
            for r in self.db.execute(
                """SELECT t.tag, COUNT(*) AS c FROM doc_tags t
               JOIN docs d ON d.id = t.doc_id WHERE d.source_id = ?
               GROUP BY t.tag ORDER BY c DESC, t.tag LIMIT ?""",
                (TROVEX_SOURCE_ID, limit),
            )
        ]

    def tags_by_facet(self, other_limit: int = 12) -> tuple[dict, list]:
        """Group tags for the sidebar: namespaced (facet/value) into facets,
        flat ones into 'other' (capped). Each facet entry = (full_tag, label, count)."""
        rows = self.db.execute(
            """SELECT t.tag, COUNT(*) AS c FROM doc_tags t
               JOIN docs d ON d.id = t.doc_id WHERE d.source_id = ?
               GROUP BY t.tag ORDER BY c DESC, t.tag""",
            (TROVEX_SOURCE_ID,),
        ).fetchall()
        facets: dict[str, list] = {}
        other: list = []
        for r in rows:
            tag, c = r["tag"], r["c"]
            if "/" in tag:
                facet, _, label = tag.partition("/")
                facets.setdefault(facet, []).append((tag, label, c))
            else:
                other.append((tag, c))
        return facets, other[:other_limit]

    def create_collection(self, name: str, filter_dict: dict) -> None:
        """A collection = a named saved filter (kind/tag/source)."""
        with self._lock:
            self.db.execute(
                """INSERT OR REPLACE INTO collections(name, kind, filter_json, created)
                   VALUES (?, 'filter', ?, ?)""",
                (name.strip(), json.dumps(filter_dict), time.time()),
            )
            self.db.commit()

    def list_collections(self) -> list[dict]:
        return [
            {"name": r["name"], "filter": json.loads(r["filter_json"] or "{}")}
            for r in self.db.execute("SELECT name, filter_json FROM collections ORDER BY name")
        ]

    def get_collection(self, name: str) -> dict | None:
        r = self.db.execute(
            "SELECT filter_json FROM collections WHERE name = ?", (name,)
        ).fetchone()
        return json.loads(r["filter_json"] or "{}") if r else None

    def delete_collection(self, name: str) -> None:
        with self._lock:
            self.db.execute("DELETE FROM collections WHERE name = ?", (name,))
            self.db.commit()

    def list_versions(self, ext_id: str) -> list[dict]:
        """Previous content snapshots of a doc (newest first)."""
        return [
            dict(r)
            for r in self.db.execute(
                """SELECT v.id, v.title, v.ts, LENGTH(v.content) AS size
               FROM doc_versions v JOIN docs d ON d.id = v.doc_id
               WHERE d.ext_id = ? ORDER BY v.ts DESC""",
                (ext_id,),
            )
        ]

    def restore_version(self, ext_id: str, version_id: int) -> bool:
        """Restore a previous version — put() snapshots the current one first."""
        row = self.db.execute(
            """SELECT v.content FROM doc_versions v JOIN docs d ON d.id = v.doc_id
               WHERE d.ext_id = ? AND v.id = ?""",
            (ext_id, version_id),
        ).fetchone()
        if not row:
            return False
        self.put(row["content"], ext_id=ext_id)
        return True

    def _embed(self, doc_id: int, content: str, title: str) -> None:
        text = f"{title}\n\n{FRONTMATTER_RE.sub('', content)}"[:8000]
        emb = next(iter(self.embedder.embed([text])))
        self.db.execute("DELETE FROM vec_docs WHERE rowid = ?", (doc_id,))
        self.db.execute(
            "INSERT INTO vec_docs(rowid, embedding) VALUES (?, ?)",
            (doc_id, sqlite_vec.serialize_float32(emb.tolist())),
        )


def _row_to_doc(row: sqlite3.Row) -> StoredDoc:
    try:
        raw_tags = row["tags"]
    except IndexError:
        raw_tags = None
    tags = sorted(set(raw_tags.split(","))) if raw_tags else []
    try:
        origin = row["origin"]
    except IndexError:
        origin = None
    return StoredDoc(
        ext_id=row["ext_id"],
        title=row["title"] or "",
        content=row["content"],
        kind=row["kind"],
        status=row["status"],
        tokens_est=row["tokens_est"],
        mtime=row["mtime"],
        tags=tags,
        origin=origin,
    )


def _extract_title(content: str) -> str:
    """Derive a doc's title, robust to docs that don't lead with an H1.

    Order: an H1 anywhere (preferred) → the first heading of any level
    (``##``-led docs) → a frontmatter ``title:`` → the first non-empty body
    line → "Untitled". Fixes docs that indexed as "Untitled" because the store
    only ever matched ``# `` (H1).
    """
    body = FRONTMATTER_RE.sub("", content)
    head = body[:2000]
    m = TITLE_RE.search(head) or ANY_HEADING_RE.search(head)
    if m:
        return m.group(1).strip()
    fm = FRONTMATTER_RE.match(content)
    if fm:
        tm = FM_TITLE_RE.search(fm.group(1))
        if tm:
            return tm.group(1).strip().strip("\"'")
    for line in body.splitlines():
        if line.strip():
            return line.strip()[:120]
    return "Untitled"


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def extract_section(content: str, heading: str) -> str | None:
    """Return the markdown section under `heading` — from that heading down to
    the next same-or-higher-level heading. None if the heading isn't found.

    Lets trovex_read serve only the relevant slice of a long doc instead of the
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


def replace_section(content: str, heading: str, new_text: str) -> str | None:
    """Patch ONE section in place: replace the `heading` section (its heading line down
    to just before the next same-or-higher heading) with `new_text`, returning the full
    patched document. None if the heading isn't found — the caller MUST treat None as a
    hard error and NEVER fall back to overwriting the whole doc (that's the section-write
    data-loss this guards against). Symmetric with extract_section: read returns the
    heading+body, so new_text is expected to include the (possibly edited) heading."""
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
    patched = lines[:start] + new_text.strip("\n").splitlines() + lines[end:]
    return "\n".join(patched).strip() + "\n"
