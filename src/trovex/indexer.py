import fnmatch
import hashlib
import re
import time
from collections.abc import Iterator
from pathlib import Path

import sqlite_vec

from .config import RESERVED_SOURCE_ID, Settings, Source
from .db import delete_doc_cascade, open_db
from .embedder import Embedder, embedder_from_settings

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
TITLE_RE = re.compile(r"^\s*#\s+(.+)$", re.MULTILINE)
AGENT_FRONTMATTER_KEYS = ("agent", "author", "generator", "created_by")

TROVEXIGNORE = ".trovexignore"


def _load_ignore_patterns(root: Path) -> list[str]:
    """Read glob patterns from <root>/.trovexignore (gitignore-ish: one per line,
    `#` comments and blanks skipped). Returns [] if the file is absent/unreadable."""
    f = root / TROVEXIGNORE
    try:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [s.strip() for s in lines if s.strip() and not s.strip().startswith("#")]


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


class Indexer:
    def __init__(self, settings: Settings, embedder: Embedder | None = None):
        self.settings = settings
        self.db = open_db(settings.data_dir / "trovex.db", settings.resolved_embed_dim())
        self.embedder = embedder or embedder_from_settings(settings)

    def scan(self, root: Path) -> Iterator[Path]:
        ignore = set(self.settings.ignore_dirs)
        max_size = self.settings.max_file_size_bytes
        root_resolved = root.resolve()
        ignore_patterns = _load_ignore_patterns(root)
        for ext in ("md", "mdx", "markdown"):
            for p in root.rglob(f"*.{ext}"):
                rel = p.relative_to(root)
                if any(part in ignore for part in rel.parts):
                    continue
                # Path-traversal / symlink guard: a .md that is a symlink (or sits
                # under a symlinked dir) pointing outside the source root — e.g.
                # /etc/passwd — must NOT be indexed. Canonicalize and require the
                # real target to stay inside the root.
                try:
                    real = p.resolve()
                except OSError:
                    continue
                if real != root_resolved and not real.is_relative_to(root_resolved):
                    continue
                if ignore_patterns and _is_ignored(rel.as_posix(), ignore_patterns):
                    continue
                try:
                    if p.stat().st_size > max_size:
                        continue
                except OSError:
                    continue
                yield p

    def reindex(self, root: Path | None = None, sources: list[Source] | None = None) -> dict:
        """Index all configured sources, or a single root for back-compat."""
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
        agg = {"added": 0, "updated": 0, "unchanged": 0, "removed": 0, "by_source": []}
        embed_batch: list[tuple[int, str]] = []

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
                if existing is not None and existing["mtime"] == stat.st_mtime:
                    s_unchanged += 1
                    continue

                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()

                if existing is not None and existing["content_hash"] == content_hash:
                    # mtime moved but content is identical (e.g. `git checkout`,
                    # a rebuild). Refresh the stored mtime so the fast-path hits
                    # next run — no re-embed.
                    self.db.execute(
                        "UPDATE docs SET mtime=?, last_indexed=? WHERE id=?",
                        (stat.st_mtime, time.time(), existing["id"]),
                    )
                    s_unchanged += 1
                    continue

                title = self._extract_title(content, path.name)
                author = self._extract_author(content)
                tokens_est = len(content) // 4
                now = time.time()

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
                    s_updated += 1
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
                    s_added += 1

                embed_batch.append((doc_id, self._embed_text(content, title)))

                if len(embed_batch) >= 32:
                    self._flush_embeddings(embed_batch)
                    embed_batch.clear()

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
        added = agg["added"]
        updated = agg["updated"]
        unchanged = agg["unchanged"]
        removed = agg["removed"]

        # Recompute status (plan / stale / duplicate / canonical) after indexing
        from .status import compute_status

        status_stats = compute_status(self.db, self.settings)

        elapsed = time.time() - start
        self.db.execute(
            """INSERT INTO index_runs (ts, duration_sec, added, updated, unchanged, removed)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (time.time(), elapsed, added, updated, unchanged, removed),
        )
        self.db.commit()
        return {
            "added": added,
            "updated": updated,
            "unchanged": unchanged,
            "removed": removed,
            "duration_sec": elapsed,
            "status": status_stats,
            "by_source": agg["by_source"],
        }

    def _flush_embeddings(self, batch: list[tuple[int, str]]) -> None:
        ids = [doc_id for doc_id, _ in batch]
        texts = [text for _, text in batch]
        embeddings = list(self.embedder.embed(texts))
        for doc_id, emb in zip(ids, embeddings, strict=True):
            self.db.execute("DELETE FROM vec_docs WHERE rowid = ?", (doc_id,))
            self.db.execute(
                "INSERT INTO vec_docs(rowid, embedding) VALUES (?, ?)",
                (doc_id, sqlite_vec.serialize_float32(emb.tolist())),
            )

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
