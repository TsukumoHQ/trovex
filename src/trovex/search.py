import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from . import usearch_index
from .config import RESERVED_SOURCE_ID, Settings
from .db import open_db
from .embedder import Embedder, embedder_from_settings
from .query_cache import embed_query_blob

log = logging.getLogger("trovex.search")

# vec0's hard API ceiling on a KNN `k` — sqlite-vec RAISES past this, it does not
# clamp. With the partitioned index (P2a) each source is its OWN bounded shard,
# so a query never needs a k anywhere near this for the small default window —
# the old SQLITE_VEC_MAX_K clamp + widen-to-4096 retry are retired. It survives
# as the k used to scan a whole partition for a tag-scoped query (tags are not a
# vec0 metadata column, so they're filtered after the KNN) — but that only
# actually covers the WHOLE partition while the partition's own vector count
# stays under this ceiling too (task 4c89b89a). A partition that outgrows it
# (flag it in Settings.usearch_partitions — see usearch_index.py) needs the HNSW
# escape hatch for a tag-scoped query to see every candidate again.
VEC0_MAX_K = 4096

# Reciprocal-rank-fusion constant (the standard k0=60), shared with the chunk
# store's hybrid retrieval (store.py) so both surfaces fuse identically.
RRF_K0 = 60

# BM25 recall caps (perf C, task 33ecdc9f): the keyword side was an unbounded OR of
# up to 24 terms with LIMIT 4096, scoring the whole corpus on common words. Cap the
# term count, drop stopwords (they match nearly everything and add no signal), and
# bound the result pool to 50.
BM25_MAX_TERMS = 8
BM25_RECALL_LIMIT = 50
_STOPWORDS = frozenset(
    (
        "the", "a", "an", "and", "or", "of", "to", "in", "is", "it", "for", "on",
        "with", "as", "at", "by", "be", "this", "that", "are", "was", "from", "but",
        "not", "you", "your", "we", "they", "he", "she", "his", "her", "its", "our",
        "their", "can", "will",
    )
)

def _row_importance(r) -> float:
    """A row's importance, 0.0 if the column isn't present (older row shape)."""
    try:
        return float(r["importance"] or 0.0)
    except (IndexError, KeyError):
        return 0.0


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
        self.db = open_db(
            settings.data_dir / "trovex.db",
            settings.resolved_embed_dim(),
            settings.embed_model,
            static_embed_dim=settings.static_embed_dim,
            static_embed_enabled=settings.static_embed_enabled,
        )
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

        # Dense side — full metadata rows from the partitioned KNN (source_id
        # shard, tiny bounded k; the old widen-retry is retired, T3). row_by_id
        # caches every row we touch, for both signals.
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

        # Keyword side — BM25 over docs_fts, filtered post-hoc to match scope. An
        # owner-scoped query pushes the owner filter INTO the id set (perf C) so the
        # keyword side mirrors the dense side's owner pre-filter.
        bm_owner = tags[0] if (tags and len(tags) == 1 and tags[0].startswith("owner/")) else None
        bm_order: list[int] = []
        for did in self._bm25_ids(query, pool, owner_tag=bm_owner):
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

        w_imp = self.settings.importance_weight
        results = []
        for did, fusion in rrf.items():
            r = row_by_id[did]
            age_days = max(0.0, (now - r["mtime"]) / 86400)
            freshness = 0.5 + 0.5 * (1.0 / (1.0 + age_days / half_life))
            status_w = STATUS_WEIGHT.get(r["status"], 1.0)
            # Importance (P3): an old-but-critical doc (high status/pinned/access)
            # outranks recent trivia. Multiplicative BOOST — importance defaults to
            # 0 until a recompute runs, so imp_factor is 1.0 (no change) by default.
            # Applied to the FLAGSHIP hybrid score only; the boot floor uses the
            # dense path (hybrid=False), left on its absolute scale untouched.
            imp_factor = 1.0 + w_imp * _row_importance(r)
            # Freshness/status weighting preserved — now multiplying the RRF
            # fusion score instead of the raw cosine similarity. This score is a
            # RANKING signal for the flagship surface, NOT an absolute-scale
            # gate; recall floors (boot) must use the dense path (hybrid=False).
            results.append(
                self._build_result(
                    r, dist_by_id.get(did, 2.0), fusion * freshness * status_w * imp_factor, age_days
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
        pool: int,  # retained for signature compat; k is now partition-derived
        source_ids: list[str] | None,
        kind: str | None,
        tags: list[str] | None,
        limit: int,
        include_archived: bool = False,
        include_duplicates: bool = False,
    ) -> list:
        """Partitioned KNN (P2a). source_id is the vec0 PARTITION KEY, so the search
        is restricted to the target source's shard — k stays bounded per source and
        the 4096 ceiling (clamp + widen retry) is gone. kind/lifecycle/status are
        vec0 METADATA columns, pre-filtered INSIDE the KNN so no post-filter squeeze;
        tags are the one non-vec0 filter, so a tag-scoped query scans the whole
        (bounded) partition.

        source_ids scopes the shards. No source_ids = the all-sources contract
        (source='*' or an unpinned connection = "search the whole store"), so
        EVERY partition is scanned and merged by distance — NOT just the SSOT.
        Falling back to ['trovex'] here would silently drop all dense hits from
        file-backed sources. boot/flagship pass source_ids=['trovex'] explicitly."""
        qblob = embed_query_blob(self.embedder, query)
        targets = source_ids or [
            r["source_id"] for r in self.db.execute("SELECT DISTINCT source_id FROM docs")
        ] or [RESERVED_SOURCE_ID]
        # perf C (task 33ecdc9f): a single owner tag (the boot/record hot path) is now
        # a vec0 METADATA column, so it pushes INTO the KNN like kind/status — a small
        # bounded k, no 4096 over-fetch. Any OTHER tag filter (multi-tag, or a non-owner
        # tag) still has no vec0 column, so it post-filters and must scan the partition.
        owner_tag = (
            tags[0] if (tags and len(tags) == 1 and tags[0].startswith("owner/")) else None
        )
        post_filter_tags = bool(tags) and owner_tag is None
        k = VEC0_MAX_K if post_filter_tags else max(limit * 5, 50)
        # vec0 pushes '=', '!=' and 'IN' metadata constraints INTO the KNN, but NOT
        # 'NOT IN' — a NOT IN would post-filter the k-window instead, silently
        # squeezing recall on an archived-heavy partition. So exclude with chained
        # '!=' (each pushed), never NOT IN.
        lifecycle_clause = (
            "v.lifecycle != 'pending_delete'"
            if include_archived
            else "v.lifecycle != 'archived' AND v.lifecycle != 'pending_delete'"
        )
        sql = f"""SELECT d.id, d.path, d.title, d.mtime, d.status, d.size_bytes,
                         d.tokens_est, d.absolute_path, d.source_id, d.importance, v.distance
                  FROM vec_docs v JOIN docs d ON d.id = v.rowid
                  WHERE v.embedding MATCH ? AND k = ? AND v.source_id = ?
                    AND {lifecycle_clause}"""
        tail = ""
        tail_params: list = []
        # status='duplicate' is a near-copy of a canonical doc — pre-filtered out of
        # the KNN pool (not just down-weighted). Opt-in to include them.
        if not include_duplicates:
            tail += " AND v.status != 'duplicate'"
        if kind:
            tail += " AND v.kind = ?"
            tail_params.append(kind)
        if owner_tag is not None:
            # Pushed INTO the KNN (perf C): only single-owner docs carry this owner
            # in the vec0 column; multi-owner ('' ) docs are added by the fallback.
            tail += " AND v.owner = ?"
            tail_params.append(owner_tag)
        elif tags:
            placeholders = ",".join("?" * len(tags))
            tail += f" AND d.id IN (SELECT doc_id FROM doc_tags WHERE tag IN ({placeholders}))"
            tail_params.extend(tags)
        sql += tail + " ORDER BY v.distance"

        # task 4c89b89a: the usearch fallback below can't reuse `sql` — vec0
        # only populates `v.distance` inside a MATCH KNN, not for a plain
        # `rowid IN (...)` lookup — so it re-selects metadata straight off
        # `docs` (the lifecycle/kind/status source of truth, mirrored onto
        # vec_docs only for the KNN's own pre-filter) and attaches the
        # distance usearch already computed, in Python.
        meta_sql = f"""SELECT d.id, d.path, d.title, d.mtime, d.status, d.size_bytes,
                              d.tokens_est, d.absolute_path, d.source_id, d.importance
                       FROM docs d
                       WHERE d.id IN ({{ph}}) AND {lifecycle_clause.replace("v.", "d.")}"""
        meta_tail = ""
        meta_params_tail: list = []
        if not include_duplicates:
            meta_tail += " AND d.status != 'duplicate'"
        if kind:
            meta_tail += " AND d.kind = ?"
            meta_params_tail.append(kind)
        if tags:
            placeholders = ",".join("?" * len(tags))
            meta_tail += f" AND d.id IN (SELECT doc_id FROM doc_tags WHERE tag IN ({placeholders}))"
            meta_params_tail.extend(tags)

        rows: list = []
        for src in targets:
            # A flagged partition (Settings.usearch_partitions) has no
            # sqlite-vec 4096 k-ceiling — route it through the HNSW index
            # (built by rebuild_partition, table='vec_docs') when present,
            # falling back to sqlite-vec unchanged whenever it isn't (dep
            # absent, or a rebuild hasn't run yet for this partition).
            hnsw = (
                usearch_index.get_index("vec_docs", src)
                if src in self.settings.usearch_partitions
                else None
            )
            if hnsw is not None and len(hnsw):
                eff_k = len(hnsw) if tags else k
                dist_by_id = dict(hnsw.search(qblob, eff_k))
                if dist_by_id:
                    ids = list(dist_by_id)
                    ph = ",".join("?" * len(ids))
                    q = meta_sql.format(ph=ph) + meta_tail
                    for r in self.db.execute(q, [*ids, *meta_params_tail]).fetchall():
                        row = dict(r)
                        row["distance"] = dist_by_id[row["id"]]
                        rows.append(row)
                continue
            rows.extend(self.db.execute(sql, [qblob, k, src, *tail_params]).fetchall())
            if owner_tag is not None:
                rows.extend(
                    self._owner_multi_fallback(
                        qblob, src, owner_tag, kind, lifecycle_clause, include_duplicates, limit
                    )
                )
        # The owner fast path appends its (unsorted) multi-owner fallback rows, so a
        # single-partition owner query also needs the distance merge, not just the
        # multi-partition case.
        if len(targets) > 1 or owner_tag is not None:
            rows.sort(key=lambda r: r["distance"])  # merge by distance
        return rows

    def _owner_multi_fallback(
        self,
        qblob: bytes,
        src: str,
        owner_tag: str,
        kind: str | None,
        lifecycle_clause: str,
        include_duplicates: bool,
        limit: int,
    ) -> list:
        """Recall MULTI-owner docs for an owner-scoped query (perf C, task 33ecdc9f).

        A doc with >1 `owner/` tag stores owner='' in vec_docs, so the single-owner
        fast KNN (`v.owner = ?`) misses it. Recall it here WITHOUT re-introducing the
        4096 over-fetch: drive from doc_tags (indexed on tag → bounded to the few docs
        carrying this owner), join vec_docs by rowid, keep only the '' rows, and score
        with vec_distance_cosine so the distance matches the KNN metric. Empty (zero
        cost) in the common single-owner case — which is why the fast path never
        over-fetches. Best-effort: a vec0 access-pattern error degrades to no fallback
        rather than failing the whole recall."""
        extra = ""
        params: list = [qblob, owner_tag, src]
        if not include_duplicates:
            extra += " AND v.status != 'duplicate'"
        if kind:
            extra += " AND v.kind = ?"
            params.append(kind)
        sql = f"""SELECT d.id, d.path, d.title, d.mtime, d.status, d.size_bytes,
                         d.tokens_est, d.absolute_path, d.source_id, d.importance,
                         vec_distance_cosine(v.embedding, ?) AS distance
                  FROM doc_tags dt
                  JOIN docs d ON d.id = dt.doc_id
                  JOIN vec_docs v ON v.rowid = d.id
                  WHERE dt.tag = ? AND v.source_id = ? AND v.owner = ''
                    AND {lifecycle_clause}{extra}
                  ORDER BY distance LIMIT ?"""
        params.append(limit)
        try:
            return self.db.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return []

    def _bm25_ids(self, query: str, pool: int, owner_tag: str | None = None) -> list[int]:
        """BM25 doc ids from docs_fts, best rank first.

        perf C (task 33ecdc9f) caps this recall query: stopwords dropped and terms
        capped to BM25_MAX_TERMS (an unbounded 24-term OR scored every matching row),
        LIMIT 50, and — when the query is owner-scoped — the owner filter is ANDed
        into the id set via a doc_tags join, so the keyword side is pre-filtered to
        the owner instead of scoring the whole corpus and trimming later."""
        terms = [t for t in re.findall(r"[a-z0-9]{2,}", query.lower()) if t not in _STOPWORDS]
        terms = terms[:BM25_MAX_TERMS]
        if not terms:
            return []
        cap = min(pool, BM25_RECALL_LIMIT)
        sql = "SELECT doc_id FROM docs_fts WHERE docs_fts MATCH ?"
        params: list = [" OR ".join(terms)]
        if owner_tag is not None:
            sql += " AND doc_id IN (SELECT doc_id FROM doc_tags WHERE tag = ?)"
            params.append(owner_tag)
        sql += " ORDER BY rank LIMIT ?"
        params.append(cap)
        try:
            return [r["doc_id"] for r in self.db.execute(sql, params)]
        except sqlite3.OperationalError:
            # No docs_fts (pre-migration store) or a malformed MATCH → dense-only.
            return []

    def _fetch_doc_row(self, doc_id: int):
        return self.db.execute(
            """SELECT id, path, title, mtime, status, size_bytes, tokens_est,
                      absolute_path, source_id, importance, kind, lifecycle FROM docs WHERE id = ?""",
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
            base += self._link_hint(r)
            lines.append(base)
        return "\n".join(lines)

    def _link_hint(self, r: SearchResult) -> str:
        """` ⇄<in>/<out>` graph-edge counts for a result, only when the doc has
        any (task b9687dfb) — an UNLINKED doc's line stays byte-identical, so no
        token cost is added where there's nothing to point at."""
        try:
            from .links_parse import link_counts

            row = self.db.execute(
                "SELECT id FROM docs WHERE source_id = ? AND path = ? AND workspace_id = 'default'",
                (r.source_id, r.path),
            ).fetchone()
            if row is None:
                return ""
            inc, out = link_counts(self.db, row["id"])
            return f"  ⇄{inc}/{out}" if (inc or out) else ""
        except Exception:  # noqa: BLE001 — a count hint must never break formatting
            log.debug("link hint failed for %s:%s", r.source_id, r.path, exc_info=True)
            return ""

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
