import re
import time
from dataclasses import dataclass
from pathlib import Path

import sqlite_vec

from .config import Settings
from .db import open_db
from .embedder import Embedder, embedder_from_settings

STATUS_MARKER = {"canonical": "★", "plan": "◯", "stale": "✗", "duplicate": "⚠"}
STATUS_WEIGHT = {"canonical": 1.0, "plan": 0.85, "stale": 0.5, "duplicate": 0.6}


@dataclass
class SearchResult:
    path: str
    title: str
    distance: float
    score: float
    age_days: float
    status: str
    size_bytes: int
    tokens_est: int
    absolute_path: str
    source_id: str = "code"

    def fresh_label(self) -> str:
        d = self.age_days
        if d < 1:
            return "fresh"
        if d < 7:
            return f"fresh {int(d)}d"
        if d < 30:
            return f"{int(d)}d"
        if d < 365:
            return f"{max(1, int(d / 7))}w"
        return f"{max(1, int(d / 365))}y"

    @property
    def marker(self) -> str:
        return STATUS_MARKER.get(self.status, "★")


class Searcher:
    def __init__(self, settings: Settings, embedder: Embedder | None = None):
        self.settings = settings
        self.db = open_db(settings.data_dir / "trovex.db", settings.resolved_embed_dim())
        self.embedder = embedder or embedder_from_settings(settings)

    def search(
        self,
        query: str,
        limit: int = 5,
        source_ids: list[str] | None = None,
        kind: str | None = None,
        tags: list[str] | None = None,
    ) -> list[SearchResult]:
        if not query.strip():
            return []
        query_emb = next(self.embedder.embed([query]))
        # Widen the knn pool when metadata filters are on, so post-filtering
        # doesn't starve a tightly-scoped query (e.g. owner/<agent> + kind=record).
        pool = max(limit * 5, 50) if (kind or tags) else limit * 5
        sql = """SELECT d.path, d.title, d.mtime, d.status, d.size_bytes,
                        d.tokens_est, d.absolute_path, d.source_id, v.distance
                 FROM vec_docs v
                 JOIN docs d ON d.id = v.rowid
                 WHERE v.embedding MATCH ? AND k = ?"""
        params: list = [sqlite_vec.serialize_float32(query_emb.tolist()), pool]
        if source_ids:
            placeholders = ",".join("?" * len(source_ids))
            sql += f" AND d.source_id IN ({placeholders})"
            params.extend(source_ids)
        if kind:
            sql += " AND d.kind = ?"
            params.append(kind)
        if tags:
            placeholders = ",".join("?" * len(tags))
            sql += f" AND d.id IN (SELECT doc_id FROM doc_tags WHERE tag IN ({placeholders}))"
            params.extend(tags)
        sql += " ORDER BY v.distance"
        rows = self.db.execute(sql, params).fetchall()

        now = time.time()
        half_life = self.settings.freshness_half_life_days
        results: list[SearchResult] = []
        for r in rows:
            age_days = max(0.0, (now - r["mtime"]) / 86400)
            similarity = max(0.0, 1.0 - r["distance"] / 2)
            freshness = 0.5 + 0.5 * (1.0 / (1.0 + age_days / half_life))
            status_w = STATUS_WEIGHT.get(r["status"], 1.0)
            score = similarity * freshness * status_w
            results.append(
                SearchResult(
                    path=r["path"],
                    title=r["title"] or r["path"],
                    distance=r["distance"],
                    score=score,
                    age_days=age_days,
                    status=r["status"],
                    size_bytes=r["size_bytes"],
                    tokens_est=r["tokens_est"],
                    absolute_path=r["absolute_path"],
                    source_id=r["source_id"] or "code",
                )
            )
        results.sort(key=lambda x: -x.score)
        return results[:limit]

    def savings_estimate(self, results: list[SearchResult]) -> dict | None:
        """Per-query token-savings estimate, same model as the savings dashboard.

        Without trovex an agent reads the top ~3 candidate docs to triage; with
        trovex it reads the 1 canonical doc. saved = top-3 tokens - top-1 tokens
        - the pointer response. Returns None when there's nothing to compare.
        """
        if not results:
            return None
        top = results[:3]
        would_have_read = sum(r.tokens_est for r in top)
        actual_read = top[0].tokens_est
        response = max(1, len(self.format_minimal(results)) // 4)
        saved = max(0, would_have_read - actual_read - response)
        return {
            "would_have_read": would_have_read,
            "actual_read": actual_read,
            "response": response,
            "saved": saved,
            "ratio": saved / would_have_read if would_have_read else 0.0,
            "compared": len(top),
        }

    def format_minimal(self, results: list[SearchResult]) -> str:
        if not results:
            return "(no results)"
        # Show source suffix when results span multiple sources (saves tokens
        # when single-source; gives the agent the disambiguator otherwise).
        sources_seen = {r.source_id for r in results}
        multi = len(sources_seen) > 1
        max_path = max(len(r.path) for r in results)
        lines = []
        for r in results:
            base = f"{r.path.ljust(max_path)}  {r.marker} {r.fresh_label()}"
            if multi:
                base += f"  @{r.source_id}"
            lines.append(base)
        return "\n".join(lines)

    def format_with_summary(self, results: list[SearchResult]) -> str:
        if not results:
            return "(no results)"
        lines = []
        for r in results:
            lines.append(f"{r.path}  {r.marker} {r.fresh_label()}  ~{r.tokens_est}tok")
            summary = self._extract_summary(r.absolute_path)
            if summary:
                lines.append(f"  {summary}")
        return "\n".join(lines)

    @staticmethod
    def _extract_summary(absolute_path: str, words: int = 50) -> str:
        try:
            content = Path(absolute_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        # Strip frontmatter
        if content.startswith("---"):
            end = content.find("\n---", 4)
            if end > 0:
                content = content[end + 4 :]
        # Strip heading markers, code blocks, collapse whitespace
        text = re.sub(r"```[\s\S]*?```", "", content)
        text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s+", " ", text).strip()
        words_list = text.split()[:words]
        return " ".join(words_list)
