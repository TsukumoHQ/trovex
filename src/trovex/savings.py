"""Token savings model — the honest receipt.

Without trovex, an agent typically Globs/Greps then Reads 2-3 candidate .md
files to triage. With trovex() it gets a ranked pointer list and reads 1
canonical doc (or 0 when all results are marked stale/duplicate).

    saved = would_have_read − actual_read − response_tokens

  would_have_read = ∑ real tokens of the top-3 candidate docs (the triage read)
  actual_read     = real tokens of result[0] (the one doc read after trovex)
  response_tokens = real tokens of the trovex() pointer output

Every count comes from a real tokenizer (see tokens.py), never chars/4, and the
payload STATES which tokenizer produced it. Two honesty rails on top:

- Under-claim: the counterfactual reads only 3 candidates and gives trovex the
  full cost of its own output — a conservative floor, not a marketing ceiling.
- Precision gate: the raw number assumes the router returned the *right* doc.
  We multiply by the latest measured retrieval hit@1 to report savings AT
  MEASURED PRECISION. With no eval on record we DON'T fabricate an adjusted
  number — `precision` is null and the caveat says routing is unverified.
"""

from __future__ import annotations

from dataclasses import dataclass

# Shipped in every payload so a savings number is never context-free (CTO ask).
ASSUMPTION = (
    "saved = would_have_read (∑ tokens of the top-3 candidate docs the agent "
    "would have Read) − actual_read (the 1 canonical doc it Reads after trovex) "
    "− the trovex response. Conservative: only 3 candidates, trovex charged its "
    "full output."
)
_CAVEAT_UNVERIFIED = (
    "routing precision unmeasured — run `trovex eval` to gate this on hit@1; "
    "raw figure assumes the router returned the right doc"
)


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


def _saved(whr: int, topr: int, resp: int) -> int:
    return max(0, whr - topr - resp)


def latest_precision(db) -> tuple[float | None, float | None]:
    """(hit@1, ts) of the newest persisted retrieval eval, or (None, None).

    None means no eval has ever run — the receipt must then refuse to show a
    precision-adjusted number rather than assume perfect routing."""
    try:
        r = db.execute(
            "SELECT hit_at_1, ts FROM retrieval_eval_runs ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    except Exception:  # noqa: BLE001 — table may not exist on a very old store
        return (None, None)
    if not r:
        return (None, None)
    return (float(r["hit_at_1"]), float(r["ts"]))


def record_eval_run(db, stats) -> None:
    """Persist a retrieval_eval.RetrievalStats so the receipt can gate on it."""
    import time

    db.execute(
        """INSERT INTO retrieval_eval_runs (ts, n, k, hit_at_1, hit_at_k, mrr, recall_at_k)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            time.time(),
            int(stats.n),
            int(stats.k),
            float(stats.hit_at_1),
            float(stats.hit_at_k),
            float(stats.mrr),
            float(stats.recall_at_k),
        ),
    )
    db.commit()


def _at_precision(saved: int, precision: float | None) -> int | None:
    """saved × measured hit@1, or None when precision is unmeasured (no inflation)."""
    if precision is None:
        return None
    return round(saved * precision)


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
        out.append(
            SavingsRow(
                user=r["user"],
                queries=r["queries"],
                would_have_read=r["whr"],
                response_tokens=r["resp"],
                actual_read=r["topr"],
                saved=_saved(r["whr"], r["topr"], r["resp"]),
            )
        )
    return out


def _base_totals(db, since: float) -> dict:
    r = db.execute(
        """SELECT COUNT(*) AS queries,
                  COALESCE(SUM(would_have_read_tokens), 0) AS whr,
                  COALESCE(SUM(response_tokens_est), 0) AS resp,
                  COALESCE(SUM(top_result_tokens), 0) AS topr
           FROM mcp_queries WHERE ts >= ?""",
        (since,),
    ).fetchone()
    saved = _saved(r["whr"], r["topr"], r["resp"])
    return {
        "queries": r["queries"],
        "would_have_read": r["whr"],
        "actual_read": r["topr"],
        "response_tokens": r["resp"],
        "saved": saved,
        "ratio": saved / r["whr"] if r["whr"] else 0.0,
    }


def totals(db, since: float) -> dict:
    """The full savings receipt for a window: base numbers + tokenizer + the
    precision gate + the assumption/caveat copy. Used by /api/savings and the
    /savings HTML page; lifetime = totals(db, 0)."""
    from .tokens import tokenizer_name

    base = _base_totals(db, since)
    precision, measured_at = latest_precision(db)
    base.update(
        {
            "tokenizer": tokenizer_name(),
            "precision": precision,
            "precision_measured_at": measured_at,
            "saved_at_precision": _at_precision(base["saved"], precision),
            "assumption": ASSUMPTION,
            "caveat": None if precision is not None else _CAVEAT_UNVERIFIED,
        }
    )
    return base


def per_agent(db, since: float) -> list[dict]:
    """Per-agent (X-TROVEX-User) rows with session counts + precision-gated saved."""
    precision, _ = latest_precision(db)
    rows = db.execute(
        """SELECT user AS agent,
                  COUNT(*) AS queries,
                  COUNT(DISTINCT session_id) AS sessions,
                  COALESCE(SUM(would_have_read_tokens), 0) AS whr,
                  COALESCE(SUM(response_tokens_est), 0) AS resp,
                  COALESCE(SUM(top_result_tokens), 0) AS topr,
                  MAX(ts) AS last_seen
           FROM mcp_queries WHERE ts >= ?
           GROUP BY user ORDER BY whr DESC""",
        (since,),
    ).fetchall()
    out = []
    for r in rows:
        saved = _saved(r["whr"], r["topr"], r["resp"])
        out.append(
            {
                "agent": r["agent"],
                "sessions": r["sessions"],
                "queries": r["queries"],
                "would_have_read": r["whr"],
                "saved": saved,
                "saved_at_precision": _at_precision(saved, precision),
                "ratio": saved / r["whr"] if r["whr"] else 0.0,
                "last_seen": r["last_seen"],
            }
        )
    return out


def per_session(db, since: float) -> list[dict]:
    """Per-session rows (session_id + the agent that owns it)."""
    precision, _ = latest_precision(db)
    rows = db.execute(
        """SELECT session_id AS session,
                  MAX(user) AS agent,
                  COUNT(*) AS queries,
                  COALESCE(SUM(would_have_read_tokens), 0) AS whr,
                  COALESCE(SUM(response_tokens_est), 0) AS resp,
                  COALESCE(SUM(top_result_tokens), 0) AS topr,
                  MAX(ts) AS last_seen
           FROM mcp_queries WHERE ts >= ?
           GROUP BY session_id ORDER BY whr DESC""",
        (since,),
    ).fetchall()
    out = []
    for r in rows:
        saved = _saved(r["whr"], r["topr"], r["resp"])
        out.append(
            {
                "session": r["session"],
                "agent": r["agent"],
                "queries": r["queries"],
                "would_have_read": r["whr"],
                "saved": saved,
                "saved_at_precision": _at_precision(saved, precision),
                "last_seen": r["last_seen"],
            }
        )
    return out


def session_totals(db, session: str, since: float = 0.0) -> dict:
    """The receipt for one session (defaults to lifetime)."""
    from .tokens import tokenizer_name

    r = db.execute(
        """SELECT COUNT(*) AS queries,
                  MAX(user) AS agent,
                  COALESCE(SUM(would_have_read_tokens), 0) AS whr,
                  COALESCE(SUM(response_tokens_est), 0) AS resp,
                  COALESCE(SUM(top_result_tokens), 0) AS topr,
                  MAX(ts) AS last_seen
           FROM mcp_queries WHERE session_id = ? AND ts >= ?""",
        (session, since),
    ).fetchone()
    saved = _saved(r["whr"], r["topr"], r["resp"])
    precision, measured_at = latest_precision(db)
    return {
        "session": session,
        "agent": r["agent"],
        "queries": r["queries"],
        "would_have_read": r["whr"],
        "actual_read": r["topr"],
        "response_tokens": r["resp"],
        "saved": saved,
        "ratio": saved / r["whr"] if r["whr"] else 0.0,
        "tokenizer": tokenizer_name(),
        "precision": precision,
        "precision_measured_at": measured_at,
        "saved_at_precision": _at_precision(saved, precision),
        "assumption": ASSUMPTION,
        "caveat": None if precision is not None else _CAVEAT_UNVERIFIED,
    }


def session_saved(db, session: str) -> int:
    """Lifetime RAW tokens saved for one session — the inline counter's running
    total. Cheap: one indexed aggregate."""
    r = db.execute(
        """SELECT COALESCE(SUM(would_have_read_tokens), 0) AS whr,
                  COALESCE(SUM(response_tokens_est), 0) AS resp,
                  COALESCE(SUM(top_result_tokens), 0) AS topr
           FROM mcp_queries WHERE session_id = ?""",
        (session,),
    ).fetchone()
    return _saved(r["whr"], r["topr"], r["resp"])


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
        buckets.append(
            {
                "day": datetime.fromtimestamp(bucket_from, tz=timezone.utc).strftime("%a %d"),
                "ts": bucket_from,
                "saved": _saved(r["whr"], r["topr"], r["resp"]),
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
    return [{**dict(r), "saved": _saved(r["whr"], r["topr"], r["resp"])} for r in rows]


# --- Human-readable receipts for the MCP resources -------------------------


def _fmt_tok(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def _precision_line(rec: dict) -> str:
    if rec["precision"] is None:
        return f"- ⚠ {_CAVEAT_UNVERIFIED}"
    saved_p = rec["saved_at_precision"]
    return (
        f"- at measured routing precision hit@1={rec['precision']:.2f}: "
        f"**~{_fmt_tok(saved_p)} tokens saved**"
    )


def render_receipt_md(db) -> str:
    """`trovex://savings` — lifetime + last-7d savings, tokenizer, precision."""
    import time

    life = totals(db, 0.0)
    week = totals(db, time.time() - 7 * 86400)
    lines = [
        "# trovex savings receipt",
        "",
        f"**Lifetime: ~{_fmt_tok(life['saved'])} tokens saved** across "
        f"{life['queries']} queries "
        f"(would have read ~{_fmt_tok(life['would_have_read'])}).",
        _precision_line(life),
        f"- last 7 days: ~{_fmt_tok(week['saved'])} saved over {week['queries']} queries",
        f"- counted with `{life['tokenizer']}`",
        "",
        f"_Assumption: {ASSUMPTION}_",
        "",
        "Per-session receipts: `trovex://savings/{session}`.",
    ]
    return "\n".join(lines)


def render_session_md(db, session: str) -> str:
    """`trovex://savings/{session}` — one session's receipt."""
    rec = session_totals(db, session)
    if not rec["queries"]:
        return f"# trovex savings — session {session}\n\n(no queries recorded for this session)"
    lines = [
        f"# trovex savings — session {session}",
        "",
        f"**~{_fmt_tok(rec['saved'])} tokens saved** across {rec['queries']} queries "
        f"(agent: {rec['agent']}).",
        _precision_line(rec),
        f"- would have read ~{_fmt_tok(rec['would_have_read'])}, "
        f"actually read ~{_fmt_tok(rec['actual_read'])}",
        f"- counted with `{rec['tokenizer']}`",
        "",
        f"_Assumption: {ASSUMPTION}_",
    ]
    return "\n".join(lines)


def inline_counter(this_call_saved: int, session_saved_total: int, precision: float | None) -> str:
    """The one-line cumulative counter appended to a tool's output.

    Precision-honest: shows the raw figure with an 'unverified routing' tag when
    no eval has gated it, the measured hit@1 when one has."""
    tail = " (routing unverified)" if precision is None else f" (at hit@1={precision:.2f})"
    return (
        f"— ~{_fmt_tok(max(0, this_call_saved))} tok saved this call · "
        f"~{_fmt_tok(session_saved_total)} this session{tail}"
    )
