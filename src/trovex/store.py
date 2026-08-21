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

import hashlib
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
from .config import RESERVED_SOURCE_ID, Settings
from .db import (
    canonical_topic_slug,
    delete_doc_cascade,
    like_escape,
    open_db,
    reconcile_vec_meta,
    sync_doc_chunks,
    upsert_docs_fts,
    vec_chunks_put,
    vec_docs_put,
    vec_sync_meta,
)
from . import retention
from .query_cache import embed_query_blob
from .embedder import Embedder, embedder_from_settings

TROVEX_SOURCE_ID = RESERVED_SOURCE_ID


class TopicCollisionError(Exception):
    """A CREATE would fork a SECOND live canonical for a topic that already has
    one, and force was not set. Carries the existing canon so the caller can
    block-and-point (update it, or force=true to supersede it)."""

    def __init__(self, ext_id: str, title: str | None):
        self.ext_id = ext_id
        self.title = title
        super().__init__(f"topic already has a live canonical: {ext_id}")

# Curation lifecycle (see docs.lifecycle). Distinct from `status` (a ranking
# weight): lifecycle FILTERS visibility. 'active' is the default + only state
# retrieval shows unless asked; 'archived' is reversibly hidden (reachable
# explicitly); 'pending_delete' is queued for removal (a grace window, never
# surfaced by retrieval); 'stale' mirrors the content-status axis for callers
# that want to park a doc without archiving it.
LIFECYCLE_STATES = ("active", "archived", "pending_delete", "stale")

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
        self.embedder = embedder or embedder_from_settings(settings)
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
        force: bool = False,
    ) -> str:
        """Create or replace a trovex-owned doc; return its opaque ext_id.

        SSOT: a CREATE (no ext_id) of a non-ephemeral doc whose topic already has a
        live canonical raises TopicCollisionError unless force=True, which atomically
        SUPERSEDES the existing canon (status='superseded' + lifecycle='archived')
        so exactly one live canonical per topic survives. Ephemeral kinds
        (record/checkpoint/resume) carry no topic and are exempt."""
        ext_id = ext_id or uuid.uuid4().hex
        title = title or _extract_title(content)
        topic = None if self.settings.is_ephemeral_kind(kind) else canonical_topic_slug(title)
        now = time.time()
        tokens_est = len(content) // 4
        size = len(content.encode("utf-8"))
        content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()

        with self._lock:
            existing = self.db.execute(
                "SELECT id, content_hash, title, status FROM docs WHERE ext_id = ?", (ext_id,)
            ).fetchone()

            if existing:
                doc_id = existing["id"]
                # SSOT on the UPDATE path too: renaming a live canonical's title so
                # its slug lands on ANOTHER live canonical's topic would trip the
                # partial unique index with a raw IntegrityError the agent can't act
                # on. Mirror the CREATE guard: block-and-point, or supersede on force.
                if topic is not None and existing["status"] == "canonical":
                    prior = self.db.execute(
                        """SELECT id, ext_id, title FROM docs
                           WHERE workspace_id = 'default' AND canonical_topic = ?
                             AND status = 'canonical' AND id != ?
                           LIMIT 1""",
                        (topic, doc_id),
                    ).fetchone()
                    if prior is not None:
                        if not force:
                            raise TopicCollisionError(prior["ext_id"], prior["title"])
                        self.db.execute(
                            "UPDATE docs SET status = 'superseded', lifecycle = 'archived' "
                            "WHERE id = ?",
                            (prior["id"],),
                        )
                        vec_sync_meta(self.db, prior["id"])  # vec0 metadata follows the swap
                # Incremental: an overwrite whose content AND title are both
                # byte-identical is a no-op for the expensive + snapshot-polluting
                # work — skip the version snapshot, the doc re-embed, the re-chunk,
                # and dup-detection. Title is part of the check because embed_text
                # (doc + chunk) fuses the title in, so a title change MUST re-embed
                # or the vectors keep the stale title.
                content_unchanged = (
                    bool(existing["content_hash"])
                    and existing["content_hash"] == content_hash
                    and existing["title"] == title
                )
                if not content_unchanged:
                    # Non-clobber: snapshot the current content before overwriting
                    # it, so a bad save is always recoverable (the vague2 loss class).
                    self._snapshot_version_locked(doc_id, now)
                # A write is a "this doc is live" signal: reset lifecycle to active
                # so re-writing (e.g. an Active-Memory capture to a stable
                # owner-current-state ext_id) an archived doc resurrects it into
                # retrieval instead of silently vanishing. Re-archive via
                # trovex_archive after, if that's really intended.
                self.db.execute(
                    """UPDATE docs SET content=?, content_hash=?, title=?, kind=?, tokens_est=?,
                           size_bytes=?, mtime=?, last_indexed=?, author_agent=?,
                           canonical_topic=?, lifecycle='active'
                       WHERE id=?""",
                    (
                        content,
                        content_hash,
                        title,
                        kind,
                        tokens_est,
                        size,
                        now,
                        now,
                        author,
                        topic,
                        doc_id,
                    ),
                )
                if content_unchanged:
                    upsert_docs_fts(self.db, doc_id, title, content)  # title may have moved
                    self._set_tags(doc_id, list(tags or []) + ([f"kind/{kind}"] if kind else []))
                    if self.settings.is_store_only_kind(kind):
                        # Flipped into the store-only lane on an otherwise no-op
                        # rewrite: purge any existing vectors so the zero-KNN
                        # guarantee holds. The fast-path used to return here with
                        # the old vectors intact (review-af03da67 leak). Also clear
                        # content_hash so a later flip BACK to a searchable kind with
                        # IDENTICAL content is seen as changed and RE-EMBEDS, instead
                        # of hitting this fast-path and staying BM25-only forever
                        # (review-6c02c654 leak).
                        self.db.execute("DELETE FROM vec_docs WHERE rowid = ?", (doc_id,))
                        self.db.execute(
                            "DELETE FROM vec_chunks WHERE rowid IN "
                            "(SELECT id FROM chunks WHERE doc_id = ?)",
                            (doc_id,),
                        )
                        self.db.execute(
                            "UPDATE docs SET content_hash = '' WHERE id = ?", (doc_id,)
                        )
                    else:
                        # No re-embed on an identical rewrite, but lifecycle just reset
                        # to 'active' (and kind may have changed) — sync vec0 metadata.
                        vec_sync_meta(self.db, doc_id)
                    self.db.commit()
                    return ext_id
            else:
                # SSOT enforcement on CREATE: if this topic already has a live
                # canonical, either supersede it (force) or refuse (block-and-point).
                if topic is not None:
                    prior = self.db.execute(
                        """SELECT id, ext_id, title FROM docs
                           WHERE workspace_id = 'default' AND canonical_topic = ?
                             AND status = 'canonical'
                           LIMIT 1""",
                        (topic,),
                    ).fetchone()
                    if prior is not None:
                        if not force:
                            raise TopicCollisionError(prior["ext_id"], prior["title"])
                        # Atomic swap: the old canon steps down (superseded +
                        # archived) in the SAME transaction as the new insert.
                        self.db.execute(
                            "UPDATE docs SET status = 'superseded', lifecycle = 'archived' "
                            "WHERE id = ?",
                            (prior["id"],),
                        )
                        vec_sync_meta(self.db, prior["id"])  # vec0 metadata follows the swap
                cur = self.db.execute(
                    """INSERT INTO docs
                           (source_id, path, absolute_path, content_hash, size_bytes,
                            tokens_est, mtime, first_indexed, last_indexed, title,
                            author_agent, content, ext_id, kind, canonical_topic)
                       VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        TROVEX_SOURCE_ID,
                        ext_id,
                        content_hash,
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
                        topic,
                    ),
                )
                doc_id = cur.lastrowid

            upsert_docs_fts(self.db, doc_id, title, content)
            # Store-only lane (P2c): chunk + FTS-index for BM25, but SKIP both vec
            # inserts so the doc adds zero KNN pressure. chunks_fts is still
            # populated (chunk-level BM25 works); only vec_docs/vec_chunks are
            # withheld. Everything else embeds as before.
            store_only = self.settings.is_store_only_kind(kind)
            chunks_to_embed = self._insert_chunks(doc_id, content, title)
            if not store_only:
                self._embed(doc_id, content, title)
                self._embed_chunks(chunks_to_embed)
            else:
                # Authoritative: a store-only write guarantees NO vectors for this
                # doc, even if it previously embedded under a different kind. Clear
                # content_hash too, so a later identical-content flip BACK to a
                # searchable kind re-embeds instead of being swallowed by the
                # content_unchanged fast-path (review-6c02c654 leak).
                self.db.execute("DELETE FROM vec_docs WHERE rowid = ?", (doc_id,))
                self.db.execute(
                    "DELETE FROM vec_chunks WHERE rowid IN "
                    "(SELECT id FROM chunks WHERE doc_id = ?)",
                    (doc_id,),
                )
                self.db.execute("UPDATE docs SET content_hash = '' WHERE id = ?", (doc_id,))
            self._set_tags(doc_id, list(tags or []) + ([f"kind/{kind}"] if kind else []))
            self.db.commit()
            # Flag near-duplicates on the live write path too (the batch pass in
            # compute_status still runs on reindex/fs-watch, but a trovex_write must
            # not wait for one). Best-effort — never let it block a write. Skipped
            # for store-only docs: with no embedding there's no vector to compare,
            # and they're deliberately outside the dedup/recall pool.
            if not store_only:
                try:
                    from .status import detect_duplicate_for

                    detect_duplicate_for(self.db, self.settings, doc_id)
                except Exception:
                    pass
        return ext_id

    def set_lifecycle(self, ext_id: str, state: str) -> bool:
        """Move a doc to a curation lifecycle state (reversible). Returns True if
        the doc exists, False if no doc has that ext_id. Raises ValueError on an
        unknown state so a typo fails loud rather than silently hiding a doc."""
        if state not in LIFECYCLE_STATES:
            raise ValueError(
                f"unknown lifecycle state {state!r}; valid: {', '.join(LIFECYCLE_STATES)}"
            )
        with self._lock:
            # Stamp lifecycle_changed_at so the TTL sweep measures time-in-state
            # from this manual transition too (P3 retention).
            cur = self.db.execute(
                "UPDATE docs SET lifecycle = ?, lifecycle_changed_at = ? WHERE ext_id = ?",
                (state, time.time(), ext_id),
            )
            row = self.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext_id,)).fetchone()
            if row is not None:
                vec_sync_meta(self.db, row["id"])  # keep vec0 lifecycle metadata in step
            self.db.commit()
        return cur.rowcount > 0

    def check_duplicate(
        self,
        content: str,
        title: str | None = None,
        kind: str | None = None,
        source_id: str = "trovex",
    ) -> dict | None:
        """Pre-insert near-duplicate check for the interactive write path.

        Embeds `title` + `content` TRANSIENTLY (no insert) — title-fused, so the
        probe vector matches how docs are stored — and returns the nearest existing
        CANONICAL/plan doc IN THE SAME (source_id, kind) CLASS within the cosine
        threshold, so trovex_write can block-and-point ('this duplicates <id> —
        update it or pass force') instead of creating another near-copy (43% of the
        store was such bloat). Returns {ext_id, title, similarity} or None.

        Compares LIKE-WITH-LIKE: only same-source, same-kind, non-ephemeral
        neighbours are candidates, so a governance audit is never blocked against a
        stale checkpoint. Ephemeral kinds (record/checkpoint/resume) are their own
        events — an ephemeral driver is never blocked at all. Never raises into the
        caller: a guard failure must not block a legit write.
        """
        if self.settings.is_ephemeral_kind(kind):
            return None  # ephemeral kinds are not deduped (driver-side exclusion)
        try:
            text = f"{title or ''}\n\n{FRONTMATTER_RE.sub('', content)}"[:8000]
            emb = next(iter(self.embedder.embed([text])))
            qv = sqlite_vec.serialize_float32(emb.tolist())
            threshold = self.settings.dup_threshold_for(kind)
            # k is applied by sqlite-vec BEFORE the WHERE class filter, so a pool of
            # 3 could be all wrong-kind neighbours and miss a real same-kind dup.
            # Widen the probe, then keep the nearest same-(source,kind) canonical.
            kind_clause = "d.kind IS NULL" if kind is None else "d.kind = :kind"
            with self._lock:
                neighbours = self.db.execute(
                    f"""SELECT v.distance, d.ext_id, d.title, d.status
                        FROM vec_docs v JOIN docs d ON d.id = v.rowid
                        WHERE v.embedding MATCH :qv AND k = 20
                          AND d.source_id = :source_id
                          AND {kind_clause}
                          AND d.status IN ('canonical', 'plan')
                        ORDER BY v.distance""",
                    {"qv": qv, "source_id": source_id, "kind": kind},
                ).fetchall()
            for nb in neighbours:
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
        """Remove a trovex-owned doc (row + its embedding) by ext_id. True if it existed.

        Non-destructive: an owned doc's body is tombstoned first, so a delete is
        recoverable (restore_deleted / trovex_undelete)."""
        with self._lock:
            row = self.db.execute("SELECT id FROM docs WHERE ext_id = ?", (ext_id,)).fetchone()
            if not row:
                return False
            self._tombstone_locked(row["id"])
            self._delete_cascade_locked(row["id"])
            self.db.commit()
            return True

    def delete_by_id(self, doc_id: int) -> bool:
        """Remove a doc by its internal id (handles rows with a NULL ext_id, e.g.
        agent/MCP-written docs). Same cascade + tombstone as delete(). True if it existed."""
        with self._lock:
            row = self.db.execute("SELECT id FROM docs WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                return False
            self._tombstone_locked(doc_id)
            self._delete_cascade_locked(doc_id)
            self.db.commit()
            return True

    def _delete_cascade_locked(self, doc_id: int) -> None:
        """Proper cascade delete by internal id — no orphan rows. Caller holds _lock
        and commits. See db.delete_doc_cascade for what gets removed."""
        delete_doc_cascade(self.db, doc_id)

    def _tombstone_locked(self, doc_id: int) -> None:
        """Snapshot an OWNED doc into doc_tombstones before it is deleted, then
        prune to the cap. Caller holds ``_lock``; does NOT commit.

        Only owned docs (content stored in-DB) are tombstoned — a file-backed doc
        keeps its bytes on disk, so removing it from the index is not data loss.
        The tombstone has no FK to docs, so it survives the cascade that follows.
        """
        row = self.db.execute(
            "SELECT ext_id, title, content, kind, source_id FROM docs WHERE id = ?",
            (doc_id,),
        ).fetchone()
        if not row or row["content"] is None:
            return
        tags = [
            t["tag"]
            for t in self.db.execute(
                "SELECT tag FROM doc_tags WHERE doc_id = ?", (doc_id,)
            ).fetchall()
        ]
        self.db.execute(
            """INSERT INTO doc_tombstones
                   (ext_id, title, content, kind, tags_json, source_id, deleted_ts)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                row["ext_id"],
                row["title"],
                row["content"],
                row["kind"],
                json.dumps(tags),
                row["source_id"],
                time.time(),
            ),
        )
        cap = getattr(self.settings, "doc_tombstone_cap", 0)
        if cap and cap > 0:
            self.db.execute(
                """DELETE FROM doc_tombstones
                   WHERE id NOT IN (
                       SELECT id FROM doc_tombstones ORDER BY deleted_ts DESC, id DESC LIMIT ?
                   )""",
                (cap,),
            )

    def set_pinned(self, ext_id: str, pinned: bool) -> bool:
        """Pin/unpin a doc. A pinned doc is high-importance and EXEMPT from TTL
        eviction. Returns True if the doc exists."""
        with self._lock:
            cur = self.db.execute(
                "UPDATE docs SET pinned = ? WHERE ext_id = ?", (1 if pinned else 0, ext_id)
            )
            self.db.commit()
        return cur.rowcount > 0

    def recompute_importance(self) -> int:
        """Recompute docs.importance (status + pinned + access frequency) across
        the corpus. Deterministic + idempotent. Returns rows updated."""
        with self._lock:
            n = retention.recompute_importance(self.db)
            self.db.commit()
        return n

    def sweep_retention(self) -> dict:
        """Deterministic, idempotent TTL eviction (P3). OPT-IN
        (settings.retention_sweep_enabled) — a no-op returning zeros when off, so
        the default build has NO eviction behavior.

        Ages LOW-VALUE OWNED docs by time-IN-STATE (lifecycle_changed_at):
        active(stale/duplicate/superseded, old) → archived → pending_delete, then
        (only if settings.retention_hard_delete) tombstone + hard-delete after the
        grace window. Owned records and pinned docs are ALWAYS exempt, and a live
        active canonical is never touched (only low-value statuses archive).
        Recomputes importance first so ranking reflects the latest access counts.

        Idempotent: a second run finds nothing newly past each age boundary (each
        transition stamps lifecycle_changed_at, so time-in-state resets per stage)."""
        stats = {"archived": 0, "queued_delete": 0, "hard_deleted": 0, "importance_updated": 0}
        if not self.settings.retention_sweep_enabled:
            return stats
        now = time.time()
        exempt = "kind = 'record' OR pinned = 1"  # never evict records or pinned
        # Only LOW-VALUE docs walk the eviction chain. Gated at EVERY stage (not
        # just step 1), so a MANUALLY-archived owned canonical (set_lifecycle) can
        # never drift into pending_delete/hard-delete — a deliberate archive is a
        # keep-hidden, not a delete-queue (least-surprise; task 281fac86).
        low_value = "status IN ('stale', 'duplicate', 'superseded')"
        with self._lock:
            stats["importance_updated"] = retention.recompute_importance(self.db)
            # 1. active + low-value + old-by-content-age → archived.
            archive_cut = now - self.settings.archive_after_days * 86400
            r1 = self.db.execute(
                f"""UPDATE docs SET lifecycle = 'archived', lifecycle_changed_at = ?
                    WHERE source_id = ? AND lifecycle = 'active'
                      AND {low_value}
                      AND mtime < ? AND NOT ({exempt})""",
                (now, TROVEX_SOURCE_ID, archive_cut),
            )
            stats["archived"] = r1.rowcount
            # 2. archived long enough (time-IN-STATE) + still low-value → pending_delete.
            pend_cut = now - self.settings.pending_delete_after_days * 86400
            r2 = self.db.execute(
                f"""UPDATE docs SET lifecycle = 'pending_delete', lifecycle_changed_at = ?
                    WHERE source_id = ? AND lifecycle = 'archived'
                      AND {low_value}
                      AND lifecycle_changed_at > 0 AND lifecycle_changed_at < ?
                      AND NOT ({exempt})""",
                (now, TROVEX_SOURCE_ID, pend_cut),
            )
            stats["queued_delete"] = r2.rowcount
            # 3. pending_delete past the grace window + still low-value → tombstone +
            #    hard delete (opt-in; recoverable via doc_tombstones).
            if self.settings.retention_hard_delete:
                grace_cut = now - self.settings.hard_delete_grace_days * 86400
                doomed = [
                    row["id"]
                    for row in self.db.execute(
                        f"""SELECT id FROM docs
                            WHERE source_id = ? AND lifecycle = 'pending_delete'
                              AND {low_value}
                              AND lifecycle_changed_at > 0 AND lifecycle_changed_at < ?
                              AND NOT ({exempt})""",
                        (TROVEX_SOURCE_ID, grace_cut),
                    ).fetchall()
                ]
                for doc_id in doomed:
                    self._tombstone_locked(doc_id)
                    self._delete_cascade_locked(doc_id)
                stats["hard_deleted"] = len(doomed)
            reconcile_vec_meta(self.db)  # sync vec0 lifecycle for the transitioned docs
            self.db.commit()
        return stats

    def sweep_bloat(self) -> dict:
        """Deterministic, idempotent bloat sweep — corpus hygiene a reindex doesn't do.

          • Superseded forks: a doc superseded by a newer canonical (SSOT) is dead
            weight in the KNN candidate corpus. Tombstone-delete it (recoverable via
            the doc_tombstones snapshot), which removes its vec_docs row so the corpus
            actually SHRINKS — a lifecycle flag alone would leave the row counting
            toward the sqlite-vec KNN ceiling.
          • Age-stale owned docs: an owned (source='trovex') non-record canonical
            older than stale_age_days is re-marked 'stale'. This is a safety net for
            the STANDALONE `trovex sweep` path — on a reindex compute_status already
            applies the same age rule to every doc (it ignores file existence), so
            the UPDATE is a redundant no-op there. Records are event-anchored — never aged.
          • Ephemeral-owner forks: a respawned/numbered agent leaves owner records
            tagged owner/<name>-<N>. Collapse them (see _collapse_ephemeral_owners).

        Idempotent: a second run finds no superseded docs, re-marks nothing new, and
        collapses no owners. Returns {"superseded_deleted", "stale_marked",
        "ephemeral_owners_collapsed"}.
        """
        with self._lock:
            superseded = [
                r["id"]
                for r in self.db.execute(
                    "SELECT id FROM docs WHERE status = 'superseded'"
                ).fetchall()
            ]
            for doc_id in superseded:
                self._tombstone_locked(doc_id)
                self._delete_cascade_locked(doc_id)
            cutoff = time.time() - self.settings.stale_age_days * 86400
            stale = self.db.execute(
                """UPDATE docs SET status = 'stale'
                   WHERE source_id = ? AND status = 'canonical'
                     AND (kind IS NULL OR kind != 'record')
                     AND mtime < ?""",
                (TROVEX_SOURCE_ID, cutoff),
            )
            collapsed = self._collapse_ephemeral_owners_locked()
            reconcile_vec_meta(self.db)  # sync vec0 status for the age-stale'd docs
            self.db.commit()
        return {
            "superseded_deleted": len(superseded),
            "stale_marked": stale.rowcount,
            "ephemeral_owners_collapsed": collapsed,
        }

    _OWNER_SUFFIX_RE = re.compile(r"^owner/(?P<base>.+)-(?P<n>\d+)$")

    def _collapse_ephemeral_owners_locked(self) -> int:
        """Tombstone the numeric-suffix owner-record forks a respawned agent leaves.

        A respawn tags its records owner/<name>-<N> (e.g. owner/dev-60, owner/dev-61)
        instead of the canonical owner/<name>. Per group <name>:
          • if a NON-suffixed owner/<name> record exists → tombstone every
            owner/<name>-<N> (the unsuffixed one is the canonical owner);
          • else → keep the HIGHEST N (the most recent respawn) and tombstone the
            lower ones.
        Tombstone = the store's reversible delete (doc_tombstones snapshot + cascade),
        so it stays recoverable and consistent with the superseded pass; deleting the
        row also drops it from the KNN corpus. Idempotent: once collapsed, a re-run
        finds each group with ≤1 member and does nothing. Caller holds ``_lock`` and
        commits.
        """
        # One owner tag per record is the norm, but a record could carry several;
        # map each owner tag → the doc ids that wear it.
        rows = self.db.execute(
            """SELECT d.id, dt.tag
               FROM docs d JOIN doc_tags dt ON dt.doc_id = d.id
               WHERE d.kind = 'record' AND dt.tag LIKE 'owner/%'"""
        ).fetchall()
        # base -> {"unsuffixed": set(ids), "suffixed": {n: set(ids)}}
        groups: dict[str, dict] = {}
        for r in rows:
            m = self._OWNER_SUFFIX_RE.match(r["tag"])
            if m:
                g = groups.setdefault(m["base"], {"unsuffixed": set(), "suffixed": {}})
                g["suffixed"].setdefault(int(m["n"]), set()).add(r["id"])
            else:
                base = r["tag"][len("owner/") :]
                groups.setdefault(base, {"unsuffixed": set(), "suffixed": {}})["unsuffixed"].add(
                    r["id"]
                )

        victims: set[int] = set()
        for g in groups.values():
            if not g["suffixed"]:
                continue
            if g["unsuffixed"]:
                keep_ns: set[int] = set()  # keep the unsuffixed canonical, drop all forks
            else:
                keep_ns = g["suffixed"][max(g["suffixed"])]  # keep the highest-N respawn
            for ids in g["suffixed"].values():
                victims |= ids - keep_ns
        # Never tombstone a doc that also wears a keeper tag (a record shared across
        # owners): only collapse docs that are PURELY suffixed-fork owners.
        keepers = {i for g in groups.values() for i in g["unsuffixed"]}
        for g in groups.values():
            if g["unsuffixed"]:
                continue
            if g["suffixed"]:
                keepers |= g["suffixed"][max(g["suffixed"])]
        victims -= keepers

        for doc_id in sorted(victims):
            self._tombstone_locked(doc_id)
            self._delete_cascade_locked(doc_id)
        return len(victims)

    def list_tombstones(self, limit: int = 100) -> list[dict]:
        """Deleted owned docs still recoverable (newest first)."""
        return [
            dict(r)
            for r in self.db.execute(
                """SELECT id, ext_id, title, kind, deleted_ts, LENGTH(content) AS size
                   FROM doc_tombstones ORDER BY deleted_ts DESC, id DESC LIMIT ?""",
                (limit,),
            )
        ]

    def restore_deleted(self, *, ext_id: str | None = None, tombstone_id: int | None = None) -> str | None:
        """Recreate a deleted doc from its tombstone; return the restored ext_id.

        Pass a tombstone_id (from list_tombstones) for an exact pick, or an ext_id
        to restore that doc's most recent tombstone. Returns None if no matching
        tombstone. The restore recreates the doc via put() (so it re-embeds +
        re-chunks + is versioned), preserving the original kind + tags, and clears
        the consumed tombstone."""
        if tombstone_id is not None:
            row = self.db.execute(
                "SELECT * FROM doc_tombstones WHERE id = ?", (tombstone_id,)
            ).fetchone()
        elif ext_id:
            row = self.db.execute(
                """SELECT * FROM doc_tombstones WHERE ext_id = ?
                   ORDER BY deleted_ts DESC, id DESC LIMIT 1""",
                (ext_id,),
            ).fetchone()
        else:
            return None
        if not row:
            return None
        tags = json.loads(row["tags_json"] or "[]")
        tags = [t for t in tags if not t.startswith("kind/")]  # put re-adds the kind/ facet
        restored = self.put(
            row["content"], ext_id=row["ext_id"], kind=row["kind"], tags=tags or None
        )
        with self._lock:
            self.db.execute("DELETE FROM doc_tombstones WHERE id = ?", (row["id"],))
            self.db.commit()
        return restored

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
                content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
                existing = self.db.execute(
                    "SELECT id FROM docs WHERE ext_id = ?", (ext_id,)
                ).fetchone()
                if existing:
                    doc_id = existing["id"]
                    # Non-clobber: bulk import over an existing doc must not
                    # silently lose the prior body either (parity with put()).
                    self._snapshot_version_locked(doc_id, now)
                    self.db.execute(
                        """UPDATE docs SET content=?, content_hash=?, title=?, kind=?, tokens_est=?,
                               size_bytes=?, mtime=?, last_indexed=? WHERE id=?""",
                        (content, content_hash, title, kind, tok, size, mtime, now, doc_id),
                    )
                else:
                    cur = self.db.execute(
                        """INSERT INTO docs
                               (source_id, path, absolute_path, content_hash,
                                size_bytes, tokens_est, mtime, first_indexed,
                                last_indexed, title, content, ext_id, kind)
                           VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            TROVEX_SOURCE_ID,
                            ext_id,
                            content_hash,
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
                upsert_docs_fts(self.db, doc_id, title, content)
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
                vec_docs_put(self.db, doc_id, sqlite_vec.serialize_float32(emb.tolist()))
            for doc_id, tags in tag_jobs:
                self._set_tags(doc_id, tags)
            self._embed_chunks(chunk_pairs)
            self.db.commit()
        return ext_ids

    def _insert_chunks(self, doc_id: int, content: str, title: str) -> list[tuple[int, str]]:
        """(Re)chunk a trovex-owned doc with the markdown chunker. Thin wrapper
        over db.sync_doc_chunks (the chunker-agnostic Merkle sync shared with
        Indexer's code-chunking path) — see that docstring for the incremental
        contract."""
        return sync_doc_chunks(self.db, doc_id, content, title, chunk_markdown)

    def _embed_chunks(self, pairs: list[tuple[int, str]]) -> None:
        """Batch-embed chunk texts (prefix-fused) into vec_chunks."""
        if not pairs:
            return
        embs = list(self.embedder.embed([t for _, t in pairs]))
        for (cid, _), emb in zip(pairs, embs, strict=True):
            vec_chunks_put(self.db, cid, sqlite_vec.serialize_float32(emb.tolist()))

    def search_chunks(
        self,
        query: str,
        limit: int = 5,
        *,
        kind: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
        include_archived: bool = False,
    ) -> list[dict]:
        """Hybrid chunk retrieval: vector + BM25 fused by reciprocal rank, then
        metadata-filtered. Vector finds semantic matches; BM25 catches exact terms
        (error codes, function names, ids) the embedding blurs.

        Lifecycle-filtered: 'pending_delete' docs are never surfaced and
        'archived' docs only when include_archived=True — retrieval defaults to
        the active canon."""
        if not query.strip():
            return []
        # Partitioned chunk KNN (P2a): scan the target source's shard, pre-filtering
        # lifecycle/status/kind on the vec0 metadata columns. No source = the
        # all-sources contract → scan EVERY partition (not just the SSOT, which
        # would silently drop dense hits from file-backed sources). Tags are
        # post-filtered (not a vec0 column), so a tag-scoped query scans the whole
        # bounded partition; else a small k. k tops out at vec0's hard limit (4096)
        # — no clamp/widen, partitions are bounded.
        qblob = embed_query_blob(self.embedder, query)
        targets = [source] if source else (
            [r["source_id"] for r in self.db.execute("SELECT DISTINCT source_id FROM docs")]
            or [TROVEX_SOURCE_ID]
        )
        k = 4096 if tags else max(limit * 6, 50)
        pool = k  # BM25 side reuses this candidate budget
        # vec0 pushes '=', '!=' and 'IN' into the KNN, but NOT 'NOT IN' (it would
        # post-filter the k-window and squeeze recall on an archived-heavy shard) —
        # so exclude with chained '!=', each pushed into the KNN.
        lifecycle_clause = (
            "v.lifecycle != 'pending_delete'"
            if include_archived
            else "v.lifecycle != 'archived' AND v.lifecycle != 'pending_delete'"
        )
        vsql = (
            f"SELECT v.rowid FROM vec_chunks v "
            f"WHERE v.embedding MATCH ? AND k = ? AND v.source_id = ? "
            f"AND {lifecycle_clause} AND v.status != 'duplicate'"
        )
        if kind:
            vsql += " AND v.kind = ?"
        vsql += " ORDER BY v.distance"
        vec_ids: list[int] = []
        for src in targets:
            vparams = [qblob, k, src] + ([kind] if kind else [])
            vec_ids.extend(r["rowid"] for r in self.db.execute(vsql, vparams))

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
        if not ranked:
            return []

        # T6: fetch every candidate chunk + its doc in ONE batched query (was N+1:
        # a SELECT per ranked chunk). Batch the IN() to stay under sqlite's bound-
        # variable cap.
        _BATCH = 900
        rows_by_cid: dict[int, sqlite3.Row] = {}
        for i in range(0, len(ranked), _BATCH):
            batch = ranked[i : i + _BATCH]
            ph = ",".join("?" * len(batch))
            for r in self.db.execute(
                f"""SELECT c.id AS cid, c.doc_id, c.heading_path, c.content, c.tokens_est,
                          d.ext_id, d.title, d.kind, d.source_id, d.lifecycle,
                          d.tokens_est AS doc_tokens
                   FROM chunks c JOIN docs d ON d.id = c.doc_id WHERE c.id IN ({ph})""",
                batch,
            ):
                rows_by_cid[r["cid"]] = r

        # T6: fetch tags for all candidate docs in ONE batched query (was a per-hit
        # SELECT inside the loop).
        tagset = set(tags or [])
        tags_by_doc: dict[int, set[str]] = {}
        if tagset:
            doc_ids = list({r["doc_id"] for r in rows_by_cid.values()})
            for i in range(0, len(doc_ids), _BATCH):
                batch = doc_ids[i : i + _BATCH]
                ph = ",".join("?" * len(batch))
                for t in self.db.execute(
                    f"SELECT doc_id, tag FROM doc_tags WHERE doc_id IN ({ph})", batch
                ):
                    tags_by_doc.setdefault(t["doc_id"], set()).add(t["tag"])

        out: list[dict] = []
        for cid in ranked:
            r = rows_by_cid.get(cid)
            if not r:
                continue
            lc = r["lifecycle"]
            if lc == "pending_delete" or (lc == "archived" and not include_archived):
                continue
            if kind and r["kind"] != kind:
                continue
            if source and r["source_id"] != source:
                continue
            if tagset and not (tagset & tags_by_doc.get(r["doc_id"], set())):
                continue
            hit = dict(r)
            hit.pop("cid", None)  # internal join key — keep the output shape identical
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

    def _snapshot_version_locked(self, doc_id: int, ts: float) -> None:
        """Snapshot a doc's CURRENT content into doc_versions, then prune to the
        configured cap. Caller holds ``_lock``; does NOT commit. A doc with no
        stored content (never happens for owned docs) is a no-op."""
        old = self.db.execute(
            "SELECT content, title FROM docs WHERE id = ?", (doc_id,)
        ).fetchone()
        if not old or old["content"] is None:
            return
        self.db.execute(
            "INSERT INTO doc_versions(doc_id, content, title, ts) VALUES (?, ?, ?, ?)",
            (doc_id, old["content"], old["title"], ts),
        )
        cap = getattr(self.settings, "doc_version_cap", 0)
        if cap and cap > 0:
            # Keep the newest `cap` snapshots; drop the rest. Bounds unbounded
            # growth for a doc saved thousands of times.
            self.db.execute(
                """DELETE FROM doc_versions
                   WHERE doc_id = ? AND id NOT IN (
                       SELECT id FROM doc_versions WHERE doc_id = ?
                       ORDER BY ts DESC, id DESC LIMIT ?
                   )""",
                (doc_id, doc_id, cap),
            )

    def list_versions(self, ext_id: str) -> list[dict]:
        """Previous content snapshots of a doc (newest first)."""
        return [
            dict(r)
            for r in self.db.execute(
                """SELECT v.id, v.title, v.ts, LENGTH(v.content) AS size
               FROM doc_versions v JOIN docs d ON d.id = v.doc_id
               WHERE d.ext_id = ? ORDER BY v.ts DESC, v.id DESC""",
                (ext_id,),
            )
        ]

    def get_version(self, ext_id: str, version_id: int) -> str | None:
        """The stored content of one prior version, or None if absent."""
        row = self.db.execute(
            """SELECT v.content FROM doc_versions v JOIN docs d ON d.id = v.doc_id
               WHERE d.ext_id = ? AND v.id = ?""",
            (ext_id, version_id),
        ).fetchone()
        return row["content"] if row else None

    def restore_version(self, ext_id: str, version_id: int) -> bool:
        """Roll a doc back to a prior version's content.

        put() snapshots the CURRENT content first, so a restore is itself
        undo-able. The doc's identity (kind + tags) is preserved — restoring old
        CONTENT must not silently wipe the doc's kind/owner tags (the bare-put
        bug); only the body reverts.
        """
        content = self.get_version(ext_id, version_id)
        if content is None:
            return False
        cur = self.get(ext_id)
        kind = cur.kind if cur else None
        # Reuse the live tags minus the kind/ facet (put re-adds it from `kind`).
        tags = [t for t in cur.tags if not t.startswith("kind/")] if cur else None
        self.put(content, ext_id=ext_id, kind=kind, tags=tags)
        return True

    def _embed(self, doc_id: int, content: str, title: str) -> None:
        text = f"{title}\n\n{FRONTMATTER_RE.sub('', content)}"[:8000]
        emb = next(iter(self.embedder.embed([text])))
        vec_docs_put(self.db, doc_id, sqlite_vec.serialize_float32(emb.tolist()))


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
