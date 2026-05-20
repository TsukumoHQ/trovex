"""Analytics for piloting ctx adoption + corpus quality."""

from __future__ import annotations


def top_queries(db, since: float, limit: int = 10) -> list[dict]:
    """Most-asked queries (case-insensitive grouping)."""
    rows = db.execute(
        """SELECT LOWER(query) AS q,
                  COUNT(*) AS n,
                  COUNT(DISTINCT user) AS users,
                  MAX(ts) AS last_ts,
                  AVG(n_results) AS avg_results
           FROM mcp_queries
           WHERE ts >= ?
           GROUP BY LOWER(query)
           ORDER BY n DESC, last_ts DESC
           LIMIT ?""",
        (since, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def failed_queries(db, since: float, limit: int = 10) -> list[dict]:
    """Queries that returned nothing or had no result above the relevance floor.

    "Failed" criterion: n_results == 0 OR (best score < 0.30 across all returned
    docs — meaning no real match).
    """
    rows = db.execute(
        """SELECT q.id, q.ts, q.user, q.query, q.n_results,
                  COALESCE(MAX(r.score), 0) AS best_score
           FROM mcp_queries q
           LEFT JOIN mcp_query_results r ON r.query_id = q.id
           WHERE q.ts >= ?
           GROUP BY q.id
           HAVING q.n_results = 0 OR best_score < 0.30
           ORDER BY q.ts DESC
           LIMIT ?""",
        (since, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def repeated_queries(db, since: float, limit: int = 10) -> list[dict]:
    """Same user asking ~same query >2× within window — signal of unsatisfied
    retrieval."""
    rows = db.execute(
        """SELECT user, LOWER(query) AS q,
                  COUNT(*) AS times,
                  MIN(ts) AS first_ts,
                  MAX(ts) AS last_ts
           FROM mcp_queries
           WHERE ts >= ?
           GROUP BY user, LOWER(query)
           HAVING times >= 2
           ORDER BY times DESC, last_ts DESC
           LIMIT ?""",
        (since, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def most_returned_paths(db, since: float, limit: int = 15) -> list[dict]:
    """Docs most often surfaced in top-5 (any rank). High signal = canonical."""
    rows = db.execute(
        """SELECT r.path,
                  COUNT(*) AS appearances,
                  SUM(CASE WHEN r.rank = 0 THEN 1 ELSE 0 END) AS top1,
                  AVG(r.score) AS avg_score
           FROM mcp_query_results r
           JOIN mcp_queries q ON q.id = r.query_id
           WHERE q.ts >= ?
           GROUP BY r.path
           ORDER BY appearances DESC, top1 DESC
           LIMIT ?""",
        (since, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def dead_docs(db, since: float, limit: int = 20) -> list[dict]:
    """Indexed docs that were never returned in any query during the window.
    Candidates for archival or cleanup."""
    rows = db.execute(
        """SELECT d.path, d.title, d.status, d.tokens_est, d.mtime
           FROM docs d
           WHERE d.workspace_id = 'default'
             AND d.path NOT IN (
                SELECT r.path FROM mcp_query_results r
                JOIN mcp_queries q ON q.id = r.query_id
                WHERE q.ts >= ?
             )
           ORDER BY d.mtime DESC
           LIMIT ?""",
        (since, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def hour_heatmap(db, since: float) -> dict:
    """Returns 7×24 matrix of query counts.
    matrix[day_of_week][hour] — day 0 = Monday."""
    rows = db.execute(
        """SELECT strftime('%w', ts, 'unixepoch') AS dow,
                  CAST(strftime('%H', ts, 'unixepoch') AS INTEGER) AS hour,
                  COUNT(*) AS n
           FROM mcp_queries WHERE ts >= ?
           GROUP BY dow, hour""",
        (since,),
    ).fetchall()
    # strftime('%w') returns 0=Sunday, 1=Monday, ..., 6=Saturday.
    # Remap to 0=Monday, 6=Sunday for European convention.
    remap = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
    matrix = [[0] * 24 for _ in range(7)]
    for r in rows:
        day = remap[int(r["dow"])]
        matrix[day][r["hour"]] = r["n"]
    return {
        "matrix": matrix,
        "max": max((max(row) for row in matrix), default=0),
        "total": sum(sum(row) for row in matrix),
    }


def rerank_stats(db, since: float) -> dict:
    """Counters + cost estimates for LLM reranking in the window.

    Pricing (per 1M tokens, OpenAI 2026):
      gpt-5.5        $5.00 / $30.00
      gpt-5.4        $2.50 / $15.00
      gpt-5.4-mini   $0.75 / $4.50
      gpt-4.1-nano   $0.10 / $0.40

    Anything else → $0 (we don't guess on unknown models).
    """
    PRICING = {
        "gpt-5.5":       (5.00, 30.00),
        "gpt-5.4":       (2.50, 15.00),
        "gpt-5.4-mini":  (0.75,  4.50),
        "gpt-4.1-nano":  (0.10,  0.40),
        "gpt-4o":        (2.50, 10.00),
        "gpt-4o-mini":   (0.15,  0.60),
    }

    rows = db.execute(
        """SELECT llm_model,
                  COUNT(*) AS n,
                  COALESCE(SUM(llm_tokens_in), 0) AS tin,
                  COALESCE(SUM(llm_tokens_out), 0) AS tout,
                  COALESCE(AVG(llm_elapsed_ms), 0) AS avg_ms
           FROM mcp_queries
           WHERE ts >= ? AND reranked = 1 AND llm_model IS NOT NULL
           GROUP BY llm_model""",
        (since,),
    ).fetchall()

    total = db.execute(
        "SELECT COUNT(*) AS c FROM mcp_queries WHERE ts >= ?",
        (since,),
    ).fetchone()["c"]
    reranked = db.execute(
        "SELECT COUNT(*) AS c FROM mcp_queries WHERE ts >= ? AND reranked = 1",
        (since,),
    ).fetchone()["c"]

    by_model = []
    total_cost = 0.0
    for r in rows:
        price_in, price_out = PRICING.get(r["llm_model"], (0.0, 0.0))
        cost = (r["tin"] / 1_000_000) * price_in + (r["tout"] / 1_000_000) * price_out
        total_cost += cost
        by_model.append({
            "model": r["llm_model"],
            "queries": r["n"],
            "tokens_in": r["tin"],
            "tokens_out": r["tout"],
            "avg_ms": int(r["avg_ms"]),
            "cost_usd": cost,
        })

    return {
        "total_queries": total,
        "reranked_queries": reranked,
        "coverage_pct": (reranked / total * 100) if total else 0,
        "by_model": by_model,
        "total_cost_usd": total_cost,
    }


def suggest_queries(db, prefix: str, limit: int = 6) -> list[dict]:
    """Autocomplete: past queries that begin with the prefix (case-insensitive),
    grouped + ranked by count."""
    if not prefix.strip():
        return []
    rows = db.execute(
        """SELECT LOWER(query) AS q, COUNT(*) AS n, MAX(ts) AS last_ts
           FROM mcp_queries
           WHERE LOWER(query) LIKE ? || '%'
           GROUP BY LOWER(query)
           ORDER BY n DESC, last_ts DESC
           LIMIT ?""",
        (prefix.lower(), limit),
    ).fetchall()
    return [dict(r) for r in rows]
