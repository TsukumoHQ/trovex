"""Knowledge-graph projection for the /graph SPA ("the codebase's brain").

Pure, read-only projection of the live index into a node/edge graph:
  - nodes  = docs (lifecycle='active'): docs, code files, tickets, decisions
  - edges  = typed doc_links (supersedes / verdict-of / decided-in / resume-of)
  - status = the doc provenance status (canonical/plan/stale/superseded/duplicate)
  - heat   = real agent reads (mcp_query_results.used) over 7d / 30d windows
  - drift  = L5 docs.drift when that column exists; 0 otherwise (not yet on dev)

Everything here is a function of the sqlite connection so it is trivially tested
against a seeded TestClient store. No network, no modelling.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from sqlite3 import Connection
from typing import Any

# A node's KIND drives its shape in the SPA; it is stable, never a lens colour.
# Priority: an explicit decision/ticket `kind` wins; then a code file by its
# path extension; everything else is a doc.
_DECISION_KINDS = {"decision", "decisions", "adr"}
_TICKET_KINDS = {"ticket", "tickets", "task", "issue"}
_CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".rs", ".go", ".java",
    ".rb", ".c", ".h", ".cpp", ".hpp", ".cc", ".cs", ".sh", ".sql", ".css",
    ".scss", ".vue", ".svelte", ".kt", ".swift", ".php", ".lua", ".toml", ".yaml", ".yml",
}

_KNOWN_STATUS = {"canonical", "plan", "stale", "superseded", "duplicate"}

# doc_links.rel enum (db.py DOC_LINK_RELS). supersedes points NEWER -> OLDER and
# is drawn as the lineage arrow.
_KNOWN_RELS = {"supersedes", "verdict-of", "decided-in", "resume-of"}


def classify_kind(kind: str | None, path: str | None) -> str:
    k = (kind or "").strip().lower()
    if k in _DECISION_KINDS:
        return "decision"
    if k in _TICKET_KINDS:
        return "ticket"
    p = (path or "").lower()
    dot = p.rfind(".")
    if dot != -1 and p[dot:] in _CODE_EXTS:
        return "code"
    return "doc"


def _has_column(db: Connection, table: str, column: str) -> bool:
    # sql-safe: `table` is a trusted internal literal (only ever "docs"); PRAGMA
    # cannot bind identifiers as parameters.
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()  # sql-safe: literal table, PRAGMA can't bind
    return any(r["name"] == column for r in rows)


def _table_exists(db: Connection, table: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _reads_by_path(db: Connection, since: float) -> dict[str, int]:
    """Count real agent reads per doc path since `since`.

    A read == a result the retriever actually surfaced into an agent's context
    (a row in mcp_query_results), which is the signal that drives the heat lens.
    We deliberately do NOT gate on `used=1`: that flag is the sparser "same
    session read it back" label and is empty on most stores, so gating on it
    would leave the heat lens uniformly dead. Served-to-an-agent is the honest
    measure of what the fleet actually leans on.
    """
    if not (_table_exists(db, "mcp_query_results") and _table_exists(db, "mcp_queries")):
        return {}
    rows = db.execute(
        """
        SELECT r.path AS path, COUNT(*) AS c
        FROM mcp_query_results r
        JOIN mcp_queries q ON q.id = r.query_id
        WHERE q.ts >= ?
        GROUP BY r.path
        """,
        (since,),
    ).fetchall()
    return {r["path"]: r["c"] for r in rows}


# Co-read tuning. Keep it bounded so the projection stays snappy and the budget
# (≤20k edges) is respected: only the top results of each query count, a pair
# must co-occur at least twice to earn an edge, and we keep the heaviest pairs.
_COREAD_TOP_K = 8
_COREAD_MIN_WEIGHT = 2
_COREAD_MAX_EDGES = 16000


def _coread_pairs(
    db: Connection, path_to_id: dict[str, int], since: float
) -> dict[tuple[int, int], int]:
    """Weighted co-retrieval edges: pairs of docs returned together in the same
    agent query, counted across queries. Keys are ordered (lo, hi) node-id pairs.
    """
    if not (_table_exists(db, "mcp_query_results") and _table_exists(db, "mcp_queries")):
        return {}
    rows = db.execute(
        """
        SELECT r.query_id AS qid, r.path AS path
        FROM mcp_query_results r
        JOIN mcp_queries q ON q.id = r.query_id
        WHERE q.ts >= ?
        ORDER BY r.query_id, r.rank
        """,
        (since,),
    ).fetchall()

    counts: dict[tuple[int, int], int] = defaultdict(int)
    current_qid: Any = object()
    bucket: list[int] = []

    def flush(ids: list[int]) -> None:
        uniq = list(dict.fromkeys(ids))[:_COREAD_TOP_K]
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                counts[(a, b) if a < b else (b, a)] += 1

    for r in rows:
        if r["qid"] != current_qid:
            flush(bucket)
            bucket = []
            current_qid = r["qid"]
        nid = path_to_id.get(r["path"])
        if nid is not None:
            bucket.append(nid)
    flush(bucket)

    kept = {pair: w for pair, w in counts.items() if w >= _COREAD_MIN_WEIGHT}
    if len(kept) > _COREAD_MAX_EDGES:
        top = sorted(kept.items(), key=lambda kv: kv[1], reverse=True)[:_COREAD_MAX_EDGES]
        kept = dict(top)
    return kept


def build_graph(
    db: Connection,
    *,
    source: str | None = None,
    focus: str | None = None,
    depth: int = 2,
) -> dict[str, Any]:
    """Project the index into {nodes, edges, meta}.

    `focus` (a node id — the doc row id, or its ext_id) limits the result to the
    k-hop neighbourhood (`depth` hops) around that node over the undirected
    link graph. `source` limits to one source_id partition.
    """
    now = time.time()
    reads7 = _reads_by_path(db, now - 7 * 86400)
    reads30 = _reads_by_path(db, now - 30 * 86400)
    drift_sel = "d.drift AS drift" if _has_column(db, "docs", "drift") else "0 AS drift"

    where = ["d.lifecycle = 'active'"]
    params: list[Any] = []
    if source:
        where.append("d.source_id = ?")
        params.append(source)

    rows = db.execute(
        f"""
        SELECT d.id AS id, d.ext_id AS ext_id, d.path AS path, d.title AS title,
               d.status AS status, d.kind AS kind, d.source_id AS source_id, {drift_sel}
        FROM docs d
        WHERE {" AND ".join(where)}
        """,
        params,
    ).fetchall()

    nodes: dict[int, dict[str, Any]] = {}
    ext_to_id: dict[str, int] = {}
    path_to_id: dict[str, int] = {}
    for r in rows:
        did = int(r["id"])
        path = r["path"] or ""
        if path:
            path_to_id[path] = did
        status = r["status"] if r["status"] in _KNOWN_STATUS else "unknown"
        nodes[did] = {
            "id": str(did),
            "title": r["title"] or path.rsplit("/", 1)[-1] or f"doc {did}",
            "path": path,
            "kind": classify_kind(r["kind"], path),
            "status": status,
            "reads_7d": int(reads7.get(path, 0)),
            "reads_30d": int(reads30.get(path, 0)),
            "drift": float(r["drift"] or 0),
        }
        if r["ext_id"]:
            ext_to_id[str(r["ext_id"])] = did

    # Edges: typed doc_links whose BOTH endpoints are in the node set.
    adj: dict[int, set[int]] = defaultdict(set)
    edges: list[dict[str, Any]] = []
    for e in db.execute(
        "SELECT src_doc_id, rel, dst_doc_id FROM doc_links"
    ).fetchall():
        s, d, rel = int(e["src_doc_id"]), int(e["dst_doc_id"]), e["rel"]
        if s not in nodes or d not in nodes:
            continue
        edges.append(
            {
                "src": str(s),
                "dst": str(d),
                "kind": rel if rel in _KNOWN_RELS else "link",
                "weight": 1,
            }
        )
        adj[s].add(d)
        adj[d].add(s)

    # Co-read backbone: docs the fleet pulls into the SAME agent query are
    # related in practice, even when no one has drawn an explicit doc_link. This
    # is the agent-usage signal the brain is really about — it turns a sparse
    # link cloud into meaningful, labelled communities. Faint by design; the
    # typed doc_links above stay the loud lineage overlay on top.
    for (a, b), w in _coread_pairs(db, path_to_id, now - 30 * 86400).items():
        edges.append({"src": str(a), "dst": str(b), "kind": "co-read", "weight": w})
        adj[a].add(b)
        adj[b].add(a)

    # Focus: restrict to the k-hop neighbourhood of the focused node.
    if focus:
        root: int | None = None
        if focus.isdigit() and int(focus) in nodes:
            root = int(focus)
        elif focus in ext_to_id:
            root = ext_to_id[focus]
        if root is None:
            return {"nodes": [], "edges": [], "meta": {"source": source, "focus": focus, "depth": depth}}
        keep: set[int] = {root}
        frontier = deque([(root, 0)])
        while frontier:
            cur, dist = frontier.popleft()
            if dist >= depth:
                continue
            for nb in adj[cur]:
                if nb not in keep:
                    keep.add(nb)
                    frontier.append((nb, dist + 1))
        node_list = [nodes[i] for i in keep]
        edge_list = [e for e in edges if int(e["src"]) in keep and int(e["dst"]) in keep]
    else:
        node_list = list(nodes.values())
        edge_list = edges

    return {
        "nodes": node_list,
        "edges": edge_list,
        "meta": {"source": source, "focus": focus, "depth": depth},
    }


def node_detail(db: Connection, node_id: str) -> dict[str, Any] | None:
    """Full detail for the SPA side panel: the doc + its in/out links w/ context."""
    row = None
    if node_id.isdigit():
        row = db.execute(
            "SELECT * FROM docs WHERE id = ?", (int(node_id),)
        ).fetchone()
    if row is None:
        row = db.execute("SELECT * FROM docs WHERE ext_id = ?", (node_id,)).fetchone()
    if row is None:
        return None

    did = int(row["id"])
    path = row["path"] or ""
    has_drift = _has_column(db, "docs", "drift")
    has_drift_reason = _has_column(db, "docs", "drift_reason")

    def links(sql: str) -> list[dict[str, Any]]:
        out = []
        for r in db.execute(sql, (did,)).fetchall():
            out.append(
                {
                    "id": str(r["other_id"]),
                    "ext_id": r["ext_id"],
                    "title": r["title"] or (r["path"] or "").rsplit("/", 1)[-1],
                    "path": r["path"] or "",
                    "kind": classify_kind(r["kind"], r["path"]),
                    "rel": r["rel"],
                }
            )
        return out

    out_links = links(
        """
        SELECT l.rel AS rel, d.id AS other_id, d.ext_id AS ext_id,
               d.title AS title, d.path AS path, d.kind AS kind
        FROM doc_links l JOIN docs d ON d.id = l.dst_doc_id
        WHERE l.src_doc_id = ?
        """
    )
    in_links = links(
        """
        SELECT l.rel AS rel, d.id AS other_id, d.ext_id AS ext_id,
               d.title AS title, d.path AS path, d.kind AS kind
        FROM doc_links l JOIN docs d ON d.id = l.src_doc_id
        WHERE l.dst_doc_id = ?
        """
    )

    return {
        "id": str(did),
        "ext_id": row["ext_id"],
        "title": row["title"] or path.rsplit("/", 1)[-1] or f"doc {did}",
        "path": path,
        "kind": classify_kind(row["kind"], path),
        "status": row["status"] if row["status"] in _KNOWN_STATUS else "unknown",
        "content": row["content"] or "",
        "drift": float(row["drift"]) if has_drift and row["drift"] is not None else 0.0,
        "drift_reason": row["drift_reason"] if has_drift_reason else None,
        "out_links": out_links,
        "in_links": in_links,
    }
