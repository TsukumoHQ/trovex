"""Token savings model.

Without trovex, an agent typically does Glob/Grep then Read on 2-3 .md files
to triage. With trovex(), they get a ranked list with status markers and
read 1 canonical doc (or 0 if all results are marked stale/duplicate).

savings_per_query = would_have_read - (top_result_tokens + response_tokens)

`would_have_read_tokens` = sum of tokens_est for top-3 results
`top_result_tokens` = tokens_est of result[0]
`response_tokens_est` = the trovex() output size (~50-150 tokens)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SavingsRow:
    user: str
    queries: int
    would_have_read: int  # ∑ top-3 result tokens
    response_tokens: int  # ∑ trovex output tokens
    actual_read: int  # ∑ top-1 result tokens (what they likely Read after trovex)
    saved: int  # would_have_read - actual_read - response_tokens

    @property
    def ratio(self) -> float:
        return self.saved / self.would_have_read if self.would_have_read else 0.0


def per_user(db, since: float) -> list[SavingsRow]:
    rows = db.execute(
        """SELECT user,
                  COUNT(*) AS queries,
                  COALESCE(SUM(would_have_read_tokens), 0) AS whr,
                  COALESCE(SUM(response_tokens_est), 0) AS resp,
                  COALESCE(SUM(top_result_tokens), 0) AS topr
           FROM mcp_queries
           WHERE ts >= ?
           GROUP BY user
           ORDER BY whr DESC""",
        (since,),
    ).fetchall()
    out = []
    for r in rows:
        saved = max(0, r["whr"] - r["topr"] - r["resp"])
        out.append(
            SavingsRow(
                user=r["user"],
                queries=r["queries"],
                would_have_read=r["whr"],
                response_tokens=r["resp"],
                actual_read=r["topr"],
                saved=saved,
            )
        )
    return out


def totals(db, since: float) -> dict:
    r = db.execute(
        """SELECT COUNT(*) AS queries,
                  COALESCE(SUM(would_have_read_tokens), 0) AS whr,
                  COALESCE(SUM(response_tokens_est), 0) AS resp,
                  COALESCE(SUM(top_result_tokens), 0) AS topr
           FROM mcp_queries WHERE ts >= ?""",
        (since,),
    ).fetchone()
    saved = max(0, r["whr"] - r["topr"] - r["resp"])
    return {
        "queries": r["queries"],
        "would_have_read": r["whr"],
        "actual_read": r["topr"],
        "response_tokens": r["resp"],
        "saved": saved,
        "ratio": saved / r["whr"] if r["whr"] else 0.0,
    }


def daily_series(db, since: float, until: float) -> list[dict]:
    """Returns list of {day_label, saved, queries} bucketed by 24h."""
    import math
    from datetime import datetime, timezone

    n_days = max(1, math.ceil((until - since) / 86400))
    day_start = (
        datetime.fromtimestamp(since, tz=timezone.utc)
        .replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        .timestamp()
    )

    buckets = []
    for i in range(n_days):
        bucket_from = day_start + i * 86400
        bucket_to = bucket_from + 86400
        r = db.execute(
            """SELECT COUNT(*) AS q,
                      COALESCE(SUM(would_have_read_tokens), 0) AS whr,
                      COALESCE(SUM(top_result_tokens), 0) AS topr,
                      COALESCE(SUM(response_tokens_est), 0) AS resp
               FROM mcp_queries WHERE ts >= ? AND ts < ?""",
            (bucket_from, bucket_to),
        ).fetchone()
        saved = max(0, r["whr"] - r["topr"] - r["resp"])
        buckets.append(
            {
                "day": datetime.fromtimestamp(bucket_from, tz=timezone.utc).strftime("%a %d"),
                "ts": bucket_from,
                "saved": saved,
                "queries": r["q"],
            }
        )
    return buckets


def top_queries(db, since: float, limit: int = 10) -> list[dict]:
    """Queries that produced the highest savings."""
    rows = db.execute(
        """SELECT user, query, would_have_read_tokens AS whr,
                  top_result_tokens AS topr, response_tokens_est AS resp,
                  ts
           FROM mcp_queries WHERE ts >= ?
           ORDER BY (would_have_read_tokens - top_result_tokens - response_tokens_est) DESC
           LIMIT ?""",
        (since, limit),
    ).fetchall()
    return [{**dict(r), "saved": max(0, r["whr"] - r["topr"] - r["resp"])} for r in rows]
