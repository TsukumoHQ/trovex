import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import sqlite_vec

from .config import Settings
from .db import open_db
from .embedder import Embedder, embedder_from_settings

# Ceiling for the widened-pool retry below: a scoped query that comes back short
# rescans the index, and this bounds that scan on a large store.
MAX_KNN_POOL = 20_000

# Hard ceiling sqlite-vec enforces on a vec0 KNN `k`: a MATCH with k > 4096
# raises OperationalError("k value in knn query too large"). Every knn site must
# clamp to this, or a store that crosses 4096 docs throws on the widen-retry and
# takes /api/boot (Active-Memory) down with a 500.
SQLITE_VEC_MAX_K = 4096

# Reciprocal-rank-fusion constant (the standard k0=60), shared with the chunk
# store's hybrid retrieval (store.py) so both surfaces fuse identically.
RRF_K0 = 60

STATUS_MARKER = {"canonical": "★", "plan": "◯", "stale": "✗", "duplicate": "⚠", "superseded": "⤺"}
STATUS_WEIGHT = {"canonical": 1.0, "plan": 0.85, "stale": 0.5, "duplicate": 0.6, "superseded": 0.3}


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
        hybrid: bool = True,
        include_archived: bool = False,
        include_duplicates: bool = False,
    ) -> list[SearchResult]:
        """Hybrid doc retrieval: dense vector KNN fused with BM25 (docs_fts) by
        reciprocal rank, then reweighted by freshness + status. Dense finds
        semantic matches; BM25 catches the exact tokens (error codes, fn/API
        names, paths, flags, versions) an embedding blurs. `hybrid=False` runs
        dense-only (the retrieval_eval baseline).

        Lifecycle-filtered: retrieval shows the active canon only —
        'pending_delete' docs are never surfaced and 'archived' docs only when
        include_archived=True. status='duplicate' docs are excluded from the
        default pool (opt-in via include_duplicates): they are a near-copy of a
        canonical doc and only diluted top-K / the rerank pool — down-weighting
        left them in the candidate set, so on a dup-heavy corpus they still
        crowded out canonical hits before scoring."""
        if not query.strip():
            return []
        filtered = bool(kind or tags or source_ids)
        pool = max(limit * 5, 50) if filtered else limit * 5

        # Dense side — full metadata rows, already scoped + widen-retried (the
        # proven path). row_by_id caches every row we touch, for both signals.
        vec_rows = self._vector_rows(
            query, pool, source_ids, kind, tags, limit, include_archived, include_duplicates
        )
        row_by_id = {r["id"]: r for r in vec_rows}
        vec_order = [r["id"] for r in vec_rows]
        # Only vector hits carry a cosine distance; a BM25-only hit gets the
        # max-distance sentinel (2.0) since it never entered the KNN.
        dist_by_id = {r["id"]: r["distance"] for r in vec_rows}

        now = time.time()
        half_life = self.settings.freshness_half_life_days

        if not hybrid:
            # Dense-only: cosine similarity x freshness x status, ranked by that.
            # This is the LEGACY scoring, kept intact because it preserves the
            # absolute-score SCALE (~0.6 for a good match) that boot_pointers
            # floors on — an RRF fusion score is ~an order of magnitude smaller
            # and would fail an absolute floor (empty Active-Memory boot recall).
            results = [
                self._make_result(r, dist_by_id.get(r["id"], 2.0), now, half_life) for r in vec_rows
            ]
            results.sort(key=lambda x: -x.score)
            return results[:limit]

        # Keyword side — BM25 over docs_fts, filtered post-hoc to match scope.
        bm_order: list[int] = []
        for did in self._bm25_ids(query, pool):
            r = row_by_id.get(did)
            if r is None:
                r = self._fetch_doc_row(did)
                if r is None or not self._passes_filters(
                    r, source_ids, kind, tags, include_archived, include_duplicates
                ):
                    continue
                row_by_id[did] = r
            bm_order.append(did)

        # Reciprocal rank fusion (k0=60, matching the chunk store).
        rrf: dict[int, float] = {}
        for order in (vec_order, bm_order):
            for rank, did in enumerate(order):
                rrf[did] = rrf.get(did, 0.0) + 1.0 / (RRF_K0 + rank)
        if not rrf:
            return []

        results = []
        for did, fusion in rrf.items():
            r = row_by_id[did]
            age_days = max(0.0, (now - r["mtime"]) / 86400)
            freshness = 0.5 + 0.5 * (1.0 / (1.0 + age_days / half_life))
            status_w = STATUS_WEIGHT.get(r["status"], 1.0)
            # Freshness/status weighting preserved — now multiplying the RRF
            # fusion score instead of the raw cosine similarity. This score is a
            # RANKING signal for the flagship surface, NOT an absolute-scale
            # gate; recall floors (boot) must use the dense path (hybrid=False).
            results.append(
                self._build_result(
                    r, dist_by_id.get(did, 2.0), fusion * freshness * status_w, age_days
                )
            )
        results.sort(key=lambda x: -x.score)
        return results[:limit]

    def _make_result(self, r, distance: float, now: float, half_life: float) -> SearchResult:
        """Legacy dense scoring: cosine similarity × freshness × status."""
        age_days = max(0.0, (now - r["mtime"]) / 86400)
        similarity = max(0.0, 1.0 - distance / 2)
        freshness = 0.5 + 0.5 * (1.0 / (1.0 + age_days / half_life))
        status_w = STATUS_WEIGHT.get(r["status"], 1.0)
        return self._build_result(r, distance, similarity * freshness * status_w, age_days)

    @staticmethod
    def _build_result(r, distance: float, score: float, age_days: float) -> SearchResult:
        return SearchResult(
            path=r["path"],
            title=r["title"] or r["path"],
            distance=distance,
            score=score,
            age_days=age_days,
            status=r["status"],
            size_bytes=r["size_bytes"],
            tokens_est=r["tokens_est"],
            absolute_path=r["absolute_path"],
            source_id=r["source_id"] or "code",
        )

    def _vector_rows(
        self,
        query: str,
        pool: int,
        source_ids: list[str] | None,
        kind: str | None,
        tags: list[str] | None,
        limit: int,
        include_archived: bool = False,
        include_duplicates: bool = False,
    ) -> list:
        query_emb = next(self.embedder.embed([query]))
        pool = min(pool, SQLITE_VEC_MAX_K)  # never hand sqlite-vec a k it rejects
        sql = """SELECT d.id, d.path, d.title, d.mtime, d.status, d.size_bytes,
                        d.tokens_est, d.absolute_path, d.source_id, v.distance
                 FROM vec_docs v
                 JOIN docs d ON d.id = v.rowid
                 WHERE v.embedding MATCH ? AND k = ?"""
        params: list = [sqlite_vec.serialize_float32(query_emb.tolist()), pool]
        # Lifecycle default: active canon only. pending_delete is always hidden;
        # archived is hidden unless explicitly requested.
        sql += (
            " AND d.lifecycle != 'pending_delete'"
            if include_archived
            else " AND d.lifecycle NOT IN ('archived', 'pending_delete')"
        )
        # status='duplicate' is a near-copy of a canonical doc — drop it from the
        # candidate pool (not just down-weight it), so a dup-heavy corpus doesn't
        # crowd canonical hits out of top-K / the rerank pool. Opt-in to see them.
        if not include_duplicates:
            sql += " AND d.status != 'duplicate'"
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

        # sqlite-vec applies `k` before these filters, so a scope that is a thin
        # slice of a skewed corpus gets squeezed out of the pool before it is
        # ever filtered — a 14-doc project inside a 2831-doc store returned zero
        # hits at pool=50 because the dominant source filled every slot. Retry
        # once over the whole index whenever the result comes back short: the
        # lifecycle exclusion (archived/pending_delete) is ALWAYS applied, so even
        # an otherwise-unfiltered query can be squeezed by an archived-heavy pool.
        # k is clamped to SQLITE_VEC_MAX_K: sqlite-vec throws once k > 4096, which
        # is exactly what took the fleet's Active-Memory boot down when the corpus
        # crossed 4096 docs — the widen scan is capped there, not at the doc count.
        if len(rows) < limit:
            total = self.db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
            if total > pool:
                params[1] = min(total, MAX_KNN_POOL, SQLITE_VEC_MAX_K)
                rows = self.db.execute(sql, params).fetchall()
        return rows

    def _bm25_ids(self, query: str, pool: int) -> list[int]:
        """BM25 doc ids from docs_fts, best rank first. An OR of the query terms —
        the same shape the chunk store uses — so any exact token can hit."""
        terms = re.findall(r"[a-z0-9]{2,}", query.lower())[:24]
        if not terms:
            return []
        try:
            return [
                r["doc_id"]
                for r in self.db.execute(
                    "SELECT doc_id FROM docs_fts WHERE docs_fts MATCH ? ORDER BY rank LIMIT ?",
                    (" OR ".join(terms), pool),
                )
            ]
        except sqlite3.OperationalError:
            # No docs_fts (pre-migration store) or a malformed MATCH → dense-only.
            return []

    def _fetch_doc_row(self, doc_id: int):
        return self.db.execute(
            """SELECT id, path, title, mtime, status, size_bytes, tokens_est,
                      absolute_path, source_id, kind, lifecycle FROM docs WHERE id = ?""",
            (doc_id,),
        ).fetchone()

    def _passes_filters(
        self,
        r,
        source_ids: list[str] | None,
        kind: str | None,
        tags: list[str] | None,
        include_archived: bool = False,
        include_duplicates: bool = False,
    ) -> bool:
        lc = r["lifecycle"]
        if lc == "pending_delete" or (lc == "archived" and not include_archived):
            return False
        if r["status"] == "duplicate" and not include_duplicates:
            return False
        if source_ids and r["source_id"] not in source_ids:
            return False
        if kind and r["kind"] != kind:
            return False
        if tags:
            dtags = {
                t["tag"]
                for t in self.db.execute("SELECT tag FROM doc_tags WHERE doc_id = ?", (r["id"],))
            }
            if not (set(tags) & dtags):
                return False
        return True

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
