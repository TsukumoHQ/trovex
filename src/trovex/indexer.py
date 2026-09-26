import fnmatch
import functools
import hashlib
import json
import os
import re
import time
from collections.abc import Iterator
from pathlib import Path

from . import capacity, usearch_index
from .chunking_code import CHUNKER_VERSION, CODE_EXTENSIONS, EXTENSION_LANGUAGES, chunk_code
from .config import RESERVED_SOURCE_ID, Settings, Source
from .db import (
    DOC_EMBED_NS,
    checkpoint_if_wal_large,
    delete_doc_cascade,
    open_db,
    resolve_embedding_blobs,
    sync_doc_chunks,
    upsert_docs_fts,
    vec_chunks_put,
    vec_docs_put,
)
from .embedder import Embedder, embedder_from_settings

MARKDOWN_EXTENSIONS = ("md", "mdx", "markdown")

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
TITLE_RE = re.compile(r"^\s*#\s+(.+)$", re.MULTILINE)
AGENT_FRONTMATTER_KEYS = ("agent", "author", "generator", "created_by")

TROVEXIGNORE = ".trovexignore"

# reindex() used to hold ONE write transaction open for the entire corpus scan,
# committing only at the very end — so the WAL grew unbounded for the whole run
# (observed on prod: 5.8M -> 10M during a full re-embed) and a concurrent reader
# had to wait out the whole thing. Commit + checkpoint every N processed docs
# instead, so the WAL stays bounded and any reader on the same connection-pool
# sees regular checkpoint opportunities. Tradeoff: a failure mid-reindex now only
# rolls back work since the last checkpoint, not the entire run — accepted for a
# long-running admin operation (085f1d69).
REINDEX_COMMIT_BATCH = 200

# CHANGE-count batching alone (above) has a gap: it only advances on an actual
# add/update, so a run with many unchanged docs and few real changes (task
# 3771564e, prod: 25 added against 11160 unchanged) can scan the ENTIRE
# corpus — stat() + read_text() + sha256 per doc, still real per-doc work even
# on the fast mtime path's early exit — between two commits, without ever
# reaching REINDEX_COMMIT_BATCH. That leaves one open transaction for the
# whole 200-600s+ pass, holding the shared db file's single-writer lock the
# entire time (confirmed live: trovex_write timed out at 30s against a lone
# in-progress reindex, no other writer). Time-based flushing closes that gap
# regardless of the change/unchanged ratio — checked every path, so it also
# fires while walking a long unchanged run, not only after a write.
REINDEX_COMMIT_INTERVAL_SEC = 1.0


def _load_ignore_patterns(root: Path) -> list[str]:
    """Read glob patterns from <root>/.trovexignore (gitignore-ish: one per line,
    `#` comments and blanks skipped). Returns [] if the file is absent/unreadable."""
    f = root / TROVEXIGNORE
    try:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [s.strip() for s in lines if s.strip() and not s.strip().startswith("#")]


def _safe_resolve(p: Path) -> Path:
    """`p.resolve()` that never raises — a removed file still yields its absolute,
    symlink-normalised path (macOS FSEvents reports /private/var, a Source.root may
    be the /var symlink form; both must compare equal)."""
    try:
        return p.resolve()
    except OSError:
        return p


def _is_ignored(rel_posix: str, patterns: list[str]) -> bool:
    """Match a source-relative POSIX path against .trovexignore globs. We match the
    full relative path, every parent prefix, and the basename — so `docs/*`,
    `**/blog/**`, and bare `SECURITY.md` all behave as a user expects."""
    name = rel_posix.rsplit("/", 1)[-1]
    parts = rel_posix.split("/")
    candidates = {rel_posix, name}
    # every directory prefix, so a dir pattern like `growth/social/**` or `docs/*`
    # matches files nested under it.
    for i in range(1, len(parts)):
        candidates.add("/".join(parts[:i]) + "/")
        candidates.add("/".join(parts[: i + 1]))
    for pat in patterns:
        p = pat.rstrip("/")
        if any(fnmatch.fnmatch(c, pat) or fnmatch.fnmatch(c, p) for c in candidates):
            return True
    return False


def _rollback_on_error(fn):
    """A reindex pass builds up a large multi-statement write, committed only at
    the very end — any exception along the way (e.g. compute_status's
    IntegrityError on a canonical_topic collision) otherwise leaves that
    transaction open on the shared connection with nothing to ever commit or
    roll it back: the next write silently piles onto it instead of starting
    clean, and the WAL can't checkpoint past it. Same wedge class as an
    unhandled request exception in Store's write methods (store._retry_on_locked)."""

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            result = fn(self, *args, **kwargs)
        except BaseException:
            self.db.rollback()
            raise
        checkpoint_if_wal_large(self.db, self.settings.data_dir / "trovex.db")
        return result

    return wrapper


def _walk_files(root: Path, ignore_dirs: set[str]) -> Iterator[Path]:
    """Single recursive descent that PRUNES an ignore_dirs-listed directory name
    before ever entering it — unlike the old `for ext in EXTS: root.rglob(...)`
    scan, which called rglob once per extension (one full independent tree walk
    each) and had no way to skip a directory during any of those walks, only to
    filter its already-yielded matches afterward in _accept(). On a source with
    a large ignored subtree (task 3771564e, prod: 49 agent .worktrees / ~58k
    files across 3 repos) that meant every reindex still paid the FULL
    directory-syscall cost of walking all of it, over and over per extension,
    even though ignore_dirs correctly excluded the resulting files — the WAL/
    write-wedge fix (the .worktrees ignore_dirs entry) only closes the loop
    together with this pruning; either alone leaves the slow walk in place.

    follow_symlinks=False on the directory check matches Path.rglob's existing
    behavior on this codebase's Python (verified: it does not descend into a
    symlinked subdirectory either) — not a behavior change, just not walking
    ignored directories AT ALL instead of filtering their contents after."""
    try:
        entries = list(os.scandir(root))
    except OSError:
        return
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            if entry.name in ignore_dirs:
                continue
            yield from _walk_files(Path(entry.path), ignore_dirs)
        elif entry.is_file(follow_symlinks=True):
            yield Path(entry.path)


class Indexer:
    def __init__(self, settings: Settings, embedder: Embedder | None = None):
        self.settings = settings
        self.db = open_db(settings.data_dir / "trovex.db", settings.resolved_embed_dim(), settings.embed_model)
        self.embedder = embedder or embedder_from_settings(settings)
        # Per-run phase/cache counters (task cbb8e8fb). Reset at the top of
        # reindex()/reindex_paths() — _upsert_doc and _flush_*embeddings, called
        # from inside those, accumulate into them. The single index_jobs applier
        # thread (index_jobs.py) already rules out two runs on one Indexer
        # overlapping — it is structurally the only caller of reindex()/
        # reindex_paths() once the server owns this Indexer.
        self._phase_ms: dict[str, float] = {"chunk": 0.0, "embed": 0.0, "write": 0.0, "status": 0.0}
        self._embed_cache_hits = 0
        self._embed_cache_misses = 0
        self._touched_ids: list[int] = []

    def _accept(
        self,
        root: Path,
        root_resolved: Path,
        path: Path,
        ignore_dirs: set[str],
        ignore_patterns: list[str],
        max_size: int,
    ) -> bool:
        """Whether `path` is an indexable doc under `root`. The single predicate
        behind both the full scan() and the fs-watch path re-index, so a watched
        file is accepted/rejected on EXACTLY the same rules a full index uses."""
        ext = path.suffix.lower().lstrip(".")
        if ext not in MARKDOWN_EXTENSIONS and ext not in CODE_EXTENSIONS:
            return False
        try:
            rel = path.relative_to(root)
        except ValueError:
            return False
        if any(part in ignore_dirs for part in rel.parts):
            return False
        # Path-traversal / symlink guard: a .md that is a symlink (or sits under a
        # symlinked dir) pointing outside the source root — e.g. /etc/passwd — must
        # NOT be indexed. Canonicalize and require the real target to stay inside.
        try:
            real = path.resolve()
        except OSError:
            return False
        if real != root_resolved and not real.is_relative_to(root_resolved):
            return False
        if ignore_patterns and _is_ignored(rel.as_posix(), ignore_patterns):
            return False
        try:
            if path.stat().st_size > max_size:
                return False
        except OSError:
            return False
        return True

    def scan(self, root: Path) -> Iterator[Path]:
        ignore = set(self.settings.ignore_dirs)
        max_size = self.settings.max_file_size_bytes
        root_resolved = root.resolve()
        # Per-repo .trovexignore PLUS the built-in agent-artifact globs (enforced in
        # code, so a repo without a .trovexignore still keeps resume/checkpoint/
        # lessons scratch out of the store).
        ignore_patterns = _load_ignore_patterns(root) + self.settings.default_ignore_globs
        for p in _walk_files(root, ignore):
            if self._accept(root, root_resolved, p, ignore, ignore_patterns, max_size):
                yield p

    @_rollback_on_error
    def reindex(
        self,
        root: Path | None = None,
        sources: list[Source] | None = None,
        full: bool = False,
        job_id: int | None = None,
    ) -> dict:
        """Index all configured sources, or a single root for back-compat.

        full=True bypasses both fast paths (mtime match, then content-hash
        match) and re-embeds every doc unconditionally — an explicit full
        rebuild. Default (False) is incremental: only a doc whose content hash
        changed since the last run is re-embedded. job_id: the index_jobs row
        (if any — see index_jobs.py) this run was driven by, stamped onto the
        index_runs row so a run's cost is traceable back to what enqueued it."""
        if sources is None:
            if root is not None:
                sources = [Source(id="code", label=root.name, root=root.resolve())]
            else:
                sources = self.settings.load_sources()
        # Defense in depth (load_sources already filters): scanning a source
        # whose id equals the owned store's virtual id would purge every
        # owned doc as a "vanished file" of that source.
        sources = [s for s in sources if s.id != RESERVED_SOURCE_ID]

        start = time.time()
        self._phase_ms = {"chunk": 0.0, "embed": 0.0, "write": 0.0, "status": 0.0}
        self._embed_cache_hits = 0
        self._embed_cache_misses = 0
        self._touched_ids = []
        agg = {"added": 0, "updated": 0, "unchanged": 0, "removed": 0, "by_source": []}
        embed_batch: list[tuple[int, str]] = []
        chunk_embed_batch: list[tuple[int, str]] = []
        since_commit = 0
        last_commit_at = time.monotonic()

        for source in sources:
            sr = source.root
            if not sr.exists():
                continue
            seen_paths: set[str] = set()
            s_added = s_updated = s_unchanged = 0

            # Bulk-load this source's known docs ONCE (one query, not one SELECT
            # per file) so the scan loop is a dict lookup. Also serves the
            # removal pass below — the row ids are already here.
            existing_by_path = {
                r["path"]: r
                for r in self.db.execute(
                    """SELECT id, path, mtime, content_hash FROM docs
                       WHERE source_id = ? AND workspace_id = 'default'""",
                    (source.id,),
                ).fetchall()
            }

            for path in self.scan(sr):
                # Time-based flush, checked on EVERY path (including ones about
                # to hit the unchanged fast-path continue below) — the gap
                # REINDEX_COMMIT_BATCH alone leaves. Only fires if a write is
                # actually pending (since_commit > 0); scanning with nothing
                # committed yet has no open transaction to release.
                if since_commit > 0 and (
                    time.monotonic() - last_commit_at >= REINDEX_COMMIT_INTERVAL_SEC
                ):
                    self._commit_progress(embed_batch, chunk_embed_batch)
                    since_commit = 0
                    last_commit_at = time.monotonic()
                try:
                    stat = path.stat()
                except OSError:
                    continue
                rel_path = str(path.relative_to(sr))
                seen_paths.add(rel_path)
                existing = existing_by_path.get(rel_path)

                # mtime fast-path: an unchanged file skips read()+sha256 entirely
                # (1 stat, not a full read+hash of the whole corpus every run).
                # The hash stays the authority — mtime is only trusted to prove
                # NON-change. Documented tradeoff: a content edit that PRESERVES
                # mtime (same-second overwrite, mtime restore/`touch -r`) is
                # missed until the file's mtime moves again. Same bar make/rsync
                # accept; a conscious choice, not a silent gap.
                if not full and existing is not None and existing["mtime"] == stat.st_mtime:
                    s_unchanged += 1
                    continue

                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()

                if not full and existing is not None and existing["content_hash"] == content_hash:
                    # mtime moved but content is identical (e.g. `git checkout`,
                    # a rebuild). Refresh the stored mtime so the fast-path hits
                    # next run — no re-embed.
                    self.db.execute(
                        "UPDATE docs SET mtime=?, last_indexed=? WHERE id=?",
                        (stat.st_mtime, time.time(), existing["id"]),
                    )
                    # A real write (opens/extends the transaction) even though
                    # nothing needs re-embedding — must count toward the
                    # time-based flush guard above, or a run with many of
                    # these and no _upsert_doc call never trips it.
                    since_commit += 1
                    s_unchanged += 1
                    continue

                if (
                    self._upsert_doc(
                        source,
                        path,
                        rel_path,
                        stat,
                        content,
                        content_hash,
                        existing,
                        embed_batch,
                        chunk_embed_batch,
                    )
                    == "updated"
                ):
                    s_updated += 1
                else:
                    s_added += 1

                since_commit += 1
                if since_commit >= REINDEX_COMMIT_BATCH:
                    self._commit_progress(embed_batch, chunk_embed_batch)
                    since_commit = 0
                    last_commit_at = time.monotonic()

            # Cleanup this source's removed docs. The bulk map already holds the
            # row ids, so a vanished file is a dict-key diff — no re-query.
            s_removed = 0
            for old_path, row in existing_by_path.items():
                if old_path not in seen_paths:
                    # Full cascade, not just vec_docs+docs: the bare delete
                    # left this doc's tags and versions behind on every
                    # reindex that saw a file disappear.
                    delete_doc_cascade(self.db, row["id"])
                    s_removed += 1
                    since_commit += 1
                    if since_commit >= REINDEX_COMMIT_BATCH or (
                        time.monotonic() - last_commit_at >= REINDEX_COMMIT_INTERVAL_SEC
                    ):
                        self._commit_progress(embed_batch, chunk_embed_batch)
                        since_commit = 0
                        last_commit_at = time.monotonic()

            agg["added"] += s_added
            agg["updated"] += s_updated
            agg["unchanged"] += s_unchanged
            agg["removed"] += s_removed
            agg["by_source"].append(
                {
                    "id": source.id,
                    "label": source.label,
                    "added": s_added,
                    "updated": s_updated,
                    "unchanged": s_unchanged,
                    "removed": s_removed,
                }
            )

        if embed_batch:
            self._flush_embeddings(embed_batch)
        if chunk_embed_batch:
            self._flush_chunk_embeddings(chunk_embed_batch)
        added = agg["added"]
        updated = agg["updated"]
        unchanged = agg["unchanged"]
        removed = agg["removed"]

        # Recompute status (plan / stale / duplicate / canonical) after indexing.
        # task 7595a3ee: compute_status was 88.9% of a full reindex's wall time
        # on the prod store (profiled: 5321/5987ms of a full recompute) because
        # it unconditionally re-derived every non-superseded doc, every run.
        #   - removed > 0: a removed doc's canonical_topic may now have no live
        #     canonical, or a promotable stale/duplicate sibling — the
        #     incremental path can't prove either way, so fall back to a full
        #     recompute (touched_doc_ids=None).
        #   - nothing added/updated and nothing removed: status can't have
        #     changed for anyone either — skip the call entirely (status_ms 0).
        #   - otherwise: incremental, scoped to this run's touched doc ids.
        from .status import compute_status

        if not self._touched_ids and removed == 0:
            status_stats = {"plan": 0, "stale": 0, "duplicate": 0, "canonical": 0}
        else:
            _status_t0 = time.monotonic()
            if removed > 0:
                status_stats = compute_status(self.db, self.settings)
            else:
                status_stats = compute_status(self.db, self.settings, touched_doc_ids=self._touched_ids)
            self._phase_ms["status"] += (time.monotonic() - _status_t0) * 1000

        elapsed = time.time() - start
        wall_ms = elapsed * 1000
        # docs_total: every doc this run accounted for (added+updated+unchanged;
        # removed docs no longer exist). docs_changed: every doc whose row was
        # actually written (added+updated+removed) — the measurable "how much
        # work did this run do" the incremental fast paths are meant to shrink.
        docs_total = added + updated + unchanged
        docs_changed = added + updated + removed
        # "scan" isn't separately timed (stat/read/hash is interleaved with
        # writes inside the same per-path loop) — it's the residual: whatever
        # of the run's wall time isn't chunk/embed/write/status.
        phase_ms = dict(self._phase_ms)
        phase_ms["scan"] = max(0.0, wall_ms - sum(self._phase_ms.values()))
        self.db.execute(
            """INSERT INTO index_runs
               (ts, duration_sec, added, updated, unchanged, removed,
                docs_changed, docs_total, wall_ms, phase_ms,
                embed_cache_hits, embed_cache_misses, job_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                time.time(),
                elapsed,
                added,
                updated,
                unchanged,
                removed,
                docs_changed,
                docs_total,
                wall_ms,
                json.dumps(phase_ms),
                self._embed_cache_hits,
                self._embed_cache_misses,
                job_id,
            ),
        )
        self.db.commit()
        # P3 headroom: warn if any partition is nearing the brute-force ceiling,
        # so the usearch upgrade is prompted before it bites. Observability only —
        # never changes indexing behavior. Report the count for callers/tests.
        # A partition already covered by usearch (task 4c89b89a) is excluded from
        # the chunk-ceiling warning — that specific risk is what the index resolves.
        capacity_warnings = capacity.log_capacity_warnings(
            self.db, usearch_partitions=self.settings.usearch_partitions
        )
        self._rebuild_usearch_indexes()
        return {
            "added": added,
            "updated": updated,
            "unchanged": unchanged,
            "removed": removed,
            "duration_sec": elapsed,
            "wall_ms": wall_ms,
            "phase_ms": phase_ms,
            "embed_cache_hits": self._embed_cache_hits,
            "embed_cache_misses": self._embed_cache_misses,
            "docs_total": docs_total,
            "docs_changed": docs_changed,
            "status": status_stats,
            "by_source": agg["by_source"],
            "capacity_warnings": capacity_warnings,
            "job_id": job_id,
        }

    def _upsert_doc(
        self,
        source: Source,
        path: Path,
        rel_path: str,
        stat,
        content: str,
        content_hash: str,
        existing,
        embed_batch: list[tuple[int, str]],
        chunk_embed_batch: list[tuple[int, str]],
    ) -> str:
        """Insert-or-update one doc row and queue its embedding. Returns "added"
        or "updated". Shared by the full reindex() and the fs-watch reindex_paths()
        so both write a doc identically.

        Code files (CODE_EXTENSIONS) additionally get chunk-level indexing via
        the cAST chunker (chunk_code), through the same Merkle sync markdown
        uses (db.sync_doc_chunks) — so an unchanged symbol never re-embeds.
        Markdown files are NOT retroactively chunked here (scope containment:
        this wiring is new only for the code path; turning it on for the
        existing markdown corpus is a separate, explicitly-costed decision)."""
        ext = path.suffix.lower().lstrip(".")
        # Code files have no markdown H1/frontmatter — extracting via TITLE_RE
        # would false-positive on a leading "# comment" line, so title is
        # always the filename for a code extension.
        title = path.name if ext in CODE_EXTENSIONS else self._extract_title(content, path.name)
        author = self._extract_author(content) if ext not in CODE_EXTENSIONS else None
        from .tokens import count_tokens

        tokens_est = count_tokens(content)
        now = time.time()
        _write_t0 = time.monotonic()
        if existing:
            self.db.execute(
                """UPDATE docs SET content_hash=?, size_bytes=?, tokens_est=?,
                   mtime=?, last_indexed=?, title=?, absolute_path=?, author_agent=?
                   WHERE id=?""",
                (
                    content_hash,
                    stat.st_size,
                    tokens_est,
                    stat.st_mtime,
                    now,
                    title,
                    str(path),
                    author,
                    existing["id"],
                ),
            )
            doc_id = existing["id"]
            action = "updated"
        else:
            cur = self.db.execute(
                """INSERT INTO docs (source_id, path, absolute_path, content_hash,
                   size_bytes, tokens_est, mtime, first_indexed, last_indexed,
                   title, author_agent)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source.id,
                    rel_path,
                    str(path),
                    content_hash,
                    stat.st_size,
                    tokens_est,
                    stat.st_mtime,
                    now,
                    now,
                    title,
                    author,
                ),
            )
            doc_id = cur.lastrowid
            action = "added"

        # Feeds compute_status's incremental path (task 7595a3ee): only docs
        # actually added/updated this run need their plan/stale/duplicate
        # status re-derived.
        self._touched_ids.append(doc_id)

        # Doc-level BM25 side of the hybrid doc-router search.
        upsert_docs_fts(self.db, doc_id, title, content)
        self._phase_ms["write"] += (time.monotonic() - _write_t0) * 1000
        embed_batch.append((doc_id, self._embed_text(content, title)))
        if len(embed_batch) >= 32:
            self._flush_embeddings(embed_batch)
            embed_batch.clear()

        if ext in CODE_EXTENSIONS:
            lang = EXTENSION_LANGUAGES[ext]
            _chunk_t0 = time.monotonic()
            new_chunks = sync_doc_chunks(
                self.db,
                doc_id,
                content,
                title,
                lambda c, lang=lang: chunk_code(c, lang),
                chunker_version=CHUNKER_VERSION,
            )
            self._phase_ms["chunk"] += (time.monotonic() - _chunk_t0) * 1000
            chunk_embed_batch.extend(new_chunks)
            if len(chunk_embed_batch) >= 32:
                self._flush_chunk_embeddings(chunk_embed_batch)
                chunk_embed_batch.clear()
        return action

    @_rollback_on_error
    def reindex_paths(
        self, paths, sources: list[Source] | None = None, job_id: int | None = None
    ) -> dict:
        """Re-index a KNOWN set of changed/added/removed paths (from fs-watch events),
        touching only those docs — the rest of the store is left untouched.

        Unlike reindex(), there is NO mtime fast-path here: a real filesystem event
        proves the file changed even when its mtime is preserved (same-second
        overwrite, `touch -r`), so every event path is read+hashed. The content
        hash still gates re-embedding — an event that didn't actually change bytes
        refreshes mtime only. Vectors stay 1:1 (delete_doc_cascade on removal)."""
        if sources is None:
            sources = self.settings.load_sources()
        sources = [s for s in sources if s.id != RESERVED_SOURCE_ID and s.root.exists()]

        start = time.time()
        self._phase_ms = {"chunk": 0.0, "embed": 0.0, "write": 0.0, "status": 0.0}
        self._embed_cache_hits = 0
        self._embed_cache_misses = 0
        self._touched_ids = []
        counts = {"added": 0, "updated": 0, "unchanged": 0, "removed": 0}
        embed_batch: list[tuple[int, str]] = []
        chunk_embed_batch: list[tuple[int, str]] = []
        max_size = self.settings.max_file_size_bytes
        ignore_dirs = set(self.settings.ignore_dirs)
        # Per-source context, all in RESOLVED-path space so a macOS /private/var
        # event path matches a /var Source.root (and vice-versa).
        resolved_root = {s.id: _safe_resolve(s.root) for s in sources}
        ctx = {
            s.id: (
                resolved_root[s.id],
                _load_ignore_patterns(s.root) + self.settings.default_ignore_globs,
            )
            for s in sources
        }
        seen: set[tuple[str, str]] = set()

        for raw in paths:
            p_real = _safe_resolve(Path(raw))
            owner = None
            rel_path = ""
            for s in sources:
                try:
                    rel_path = str(p_real.relative_to(resolved_root[s.id]))
                    owner = s
                    break
                except ValueError:
                    continue
            if owner is None:
                continue  # event outside every watched source root
            key = (owner.id, rel_path)
            if key in seen:
                continue  # a burst can name the same path repeatedly — do it once
            seen.add(key)

            existing = self.db.execute(
                """SELECT id, content_hash FROM docs
                   WHERE source_id = ? AND path = ? AND workspace_id = 'default'""",
                (owner.id, rel_path),
            ).fetchone()

            root_resolved, ignore_patterns = ctx[owner.id]
            # Removed, or no longer indexable (deleted / became ignored / oversized):
            # prune its doc + vectors if we had it.
            if not p_real.exists() or not self._accept(
                root_resolved, root_resolved, p_real, ignore_dirs, ignore_patterns, max_size
            ):
                if existing:
                    delete_doc_cascade(self.db, existing["id"])
                    counts["removed"] += 1
                continue

            try:
                content = p_real.read_text(encoding="utf-8", errors="replace")
                stat = p_real.stat()
            except OSError:
                continue
            content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()

            if existing and existing["content_hash"] == content_hash:
                # Event fired but bytes are identical → refresh mtime, no re-embed.
                self.db.execute(
                    "UPDATE docs SET mtime=?, last_indexed=? WHERE id=?",
                    (stat.st_mtime, time.time(), existing["id"]),
                )
                counts["unchanged"] += 1
                continue

            counts[
                self._upsert_doc(
                    owner,
                    p_real,
                    rel_path,
                    stat,
                    content,
                    content_hash,
                    existing,
                    embed_batch,
                    chunk_embed_batch,
                )
            ] += 1

        if embed_batch:
            self._flush_embeddings(embed_batch)
        if chunk_embed_batch:
            self._flush_chunk_embeddings(chunk_embed_batch)

        from .status import compute_status

        if counts["removed"] > 0:
            _status_t0 = time.monotonic()
            compute_status(self.db, self.settings)
            self._phase_ms["status"] += (time.monotonic() - _status_t0) * 1000
        elif self._touched_ids:
            _status_t0 = time.monotonic()
            compute_status(self.db, self.settings, touched_doc_ids=self._touched_ids)
            self._phase_ms["status"] += (time.monotonic() - _status_t0) * 1000
        # else: nothing added/updated/removed — skip entirely, phase_ms['status'] stays 0.
        elapsed = time.time() - start
        wall_ms = elapsed * 1000
        docs_total = counts["added"] + counts["updated"] + counts["unchanged"]
        docs_changed = counts["added"] + counts["updated"] + counts["removed"]
        phase_ms = dict(self._phase_ms)
        phase_ms["scan"] = max(0.0, wall_ms - sum(self._phase_ms.values()))
        self.db.execute(
            """INSERT INTO index_runs
               (ts, duration_sec, added, updated, unchanged, removed,
                docs_changed, docs_total, wall_ms, phase_ms,
                embed_cache_hits, embed_cache_misses, job_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                time.time(),
                elapsed,
                counts["added"],
                counts["updated"],
                counts["unchanged"],
                counts["removed"],
                docs_changed,
                docs_total,
                wall_ms,
                json.dumps(phase_ms),
                self._embed_cache_hits,
                self._embed_cache_misses,
                job_id,
            ),
        )
        self.db.commit()
        counts["duration_sec"] = elapsed
        counts["wall_ms"] = wall_ms
        counts["docs_total"] = docs_total
        counts["docs_changed"] = docs_changed
        counts["phase_ms"] = phase_ms
        counts["embed_cache_hits"] = self._embed_cache_hits
        counts["embed_cache_misses"] = self._embed_cache_misses
        counts["job_id"] = job_id
        self._rebuild_usearch_indexes()
        return counts

    def _rebuild_usearch_indexes(self) -> None:
        """task 4c89b89a: rebuild the in-memory HNSW index for every flagged
        partition (Settings.usearch_partitions) after each index run — cheap
        next to the reindex itself (a few hundred ms for tens of thousands of
        vectors) and keeps the index from ever serving stale results. A no-op
        when usearch isn't installed or nothing is flagged (the default)."""
        if not self.settings.usearch_partitions or not usearch_index.available():
            return
        dim = self.settings.resolved_embed_dim()
        for src in self.settings.usearch_partitions:
            usearch_index.rebuild_partition(self.db, "vec_docs", src, dim)
            usearch_index.rebuild_partition(self.db, "vec_chunks", src, dim)

    def _commit_progress(
        self, embed_batch: list[tuple[int, str]], chunk_embed_batch: list[tuple[int, str]]
    ) -> None:
        """Flush pending embeddings + commit + checkpoint mid-reindex (see
        REINDEX_COMMIT_BATCH). Embeddings flush first so a doc row committed here
        is never left un-embedded."""
        if embed_batch:
            self._flush_embeddings(embed_batch)
            embed_batch.clear()
        if chunk_embed_batch:
            self._flush_chunk_embeddings(chunk_embed_batch)
            chunk_embed_batch.clear()
        self.db.commit()
        checkpoint_if_wal_large(self.db, self.settings.data_dir / "trovex.db")

    def _embed_texts_cached(self, texts: list[str], chunker_version: str) -> list[bytes]:
        """Resolve `texts` to serialized sqlite-vec blobs via the shared
        embed_cache path (db.resolve_embedding_blobs) — commits any pending
        transaction before calling the embedder on a miss, so no transaction
        is open while the (CPU-bound, can run seconds to minutes) model runs.
        Tracks this run's embed-phase wall time and cache hit/miss counts."""
        t0 = time.monotonic()
        blobs, hits, misses = resolve_embedding_blobs(
            self.db, self.embedder, texts, self.embedder.name, chunker_version
        )
        self._phase_ms["embed"] += (time.monotonic() - t0) * 1000
        self._embed_cache_hits += hits
        self._embed_cache_misses += misses
        return blobs

    def _flush_embeddings(self, batch: list[tuple[int, str]]) -> None:
        if not batch:
            return
        ids = [doc_id for doc_id, _ in batch]
        texts = [text for _, text in batch]
        blobs = self._embed_texts_cached(texts, DOC_EMBED_NS)
        t0 = time.monotonic()
        for doc_id, blob in zip(ids, blobs, strict=True):
            vec_docs_put(self.db, doc_id, blob, self.embedder.name)
        self._phase_ms["write"] += (time.monotonic() - t0) * 1000

    def _flush_chunk_embeddings(self, batch: list[tuple[int, str]]) -> None:
        if not batch:
            return
        ids = [chunk_id for chunk_id, _ in batch]
        texts = [text for _, text in batch]
        blobs = self._embed_texts_cached(texts, CHUNKER_VERSION)
        t0 = time.monotonic()
        for chunk_id, blob in zip(ids, blobs, strict=True):
            vec_chunks_put(self.db, chunk_id, blob, self.embedder.name)
        self._phase_ms["write"] += (time.monotonic() - t0) * 1000

    @staticmethod
    def _embed_text(content: str, title: str) -> str:
        # Strip frontmatter and truncate for embedding (most models cap at 512 tokens)
        stripped = FRONTMATTER_RE.sub("", content)
        # Prefix with title to bias the embedding
        prefixed = f"{title}\n\n{stripped}"
        return prefixed[:8000]

    @staticmethod
    def _extract_title(content: str, fallback: str) -> str:
        stripped = FRONTMATTER_RE.sub("", content)
        m = TITLE_RE.search(stripped[:2000])
        if m:
            return m.group(1).strip()
        return (
            fallback.removesuffix(".md")
            .removesuffix(".mdx")
            .replace("_", " ")
            .replace("-", " ")
            .title()
        )

    @staticmethod
    def _extract_author(content: str) -> str | None:
        m = FRONTMATTER_RE.match(content)
        if not m:
            return None
        block = m.group(1)
        for key in AGENT_FRONTMATTER_KEYS:
            for line in block.splitlines():
                stripped = line.strip()
                if stripped.startswith(f"{key}:"):
                    return stripped.split(":", 1)[1].strip().strip("\"'")
        return None
