"""Replay eval (task b47301eb) — hermetic: bag-of-words embedder, a tiny corpus, and
mcp_queries/mcp_query_results rows inserted directly (standing in for real traffic)."""

from __future__ import annotations

import hashlib
import re
import time

import numpy as np
import pytest

from trovex.config import Settings
from trovex.eval_replay import (
    ReplayReport,
    format_replay_report,
    gate_replay,
    replay_eval,
    sample_queries,
)
from trovex.search import Searcher
from trovex.store import SqliteStore

DIM = 384


class BagEmbedder:
    name = "bag"
    dim = DIM

    def embed(self, texts):
        for t in texts:
            v = np.zeros(DIM, dtype=np.float32)
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                idx = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                v[idx % DIM] += 1.0
            norm = float(np.linalg.norm(v)) or 1.0
            yield v / norm


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


@pytest.fixture
def corpus(settings):
    store = SqliteStore(settings, embedder=BagEmbedder())
    ids = {
        "auth": store.put("# Auth\n\njwt token signature validation rotate keys", kind="reference"),
        "deploy": store.put("# Deploy\n\nkubernetes pod rollout rollback crash loop", kind="reference"),
    }
    return Searcher(settings, embedder=BagEmbedder()), ids


def _log_query(db, *, query: str, session_id: str, ts: float, served: list[tuple[str, int]]) -> int:
    """Insert one mcp_queries row + its served mcp_query_results rows.
    `served` is [(path, used), ...] in rank order."""
    cur = db.execute(
        """INSERT INTO mcp_queries (ts, user, session_id, query, n_results, top_result_tokens)
           VALUES (?, 'test', ?, ?, ?, 40)""",
        (ts, session_id, query, len(served)),
    )
    query_id = cur.lastrowid
    for rank, (path, used) in enumerate(served):
        db.execute(
            """INSERT INTO mcp_query_results (query_id, rank, path, status, tokens_est, score, used)
               VALUES (?, ?, ?, 'canonical', 40, 0.9, ?)""",
            (query_id, rank, path, used),
        )
    db.commit()
    return query_id


def test_sample_queries_respects_window_and_limit(corpus):
    searcher, ids = corpus
    now = time.time()
    _log_query(searcher.db, query="a", session_id="s1", ts=now - 3600, served=[(ids["auth"], 0)])
    _log_query(searcher.db, query="b", session_id="s1", ts=now - 10 * 86400, served=[(ids["auth"], 0)])

    sampled = sample_queries(searcher.db, since_seconds=86400, limit=10)
    assert [s["query"] for s in sampled] == ["a"]

    sampled_limited = sample_queries(searcher.db, since_seconds=86400 * 30, limit=1)
    assert len(sampled_limited) == 1


def test_replay_scores_hit_at_1_only_on_used_labelled(corpus):
    """A query whose served rank-1 was later marked `used` scores hit@1 against the
    FRESH ranking; a served-but-never-read query is sampled (counts toward n and
    tokens_served_median) but excluded from hit@1/MRR — unlabelled, not a miss."""
    searcher, ids = corpus
    now = time.time()
    _log_query(
        searcher.db,
        query="jwt token signature validation",
        session_id="s1",
        ts=now - 60,
        served=[(ids["auth"], 1)],  # used=1: this session read it back
    )
    _log_query(
        searcher.db,
        query="kubernetes pod rollout rollback",
        session_id="s2",
        ts=now - 60,
        served=[(ids["deploy"], 0)],  # served, never read back
    )

    report = replay_eval(searcher.db, searcher, since_seconds=3600, limit=10, k=3)
    assert report.n == 2
    assert report.n_used_labeled == 1
    assert report.hit_at_1_used == 1.0  # auth's fresh top-1 is still auth
    assert report.tokens_served_median == 40.0


def test_replay_rank_drift_when_served_top1_no_longer_ranks_first(corpus):
    searcher, ids = corpus
    now = time.time()
    # Served path is deploy, but the query text now matches auth best (drift).
    _log_query(
        searcher.db,
        query="jwt token signature validation",
        session_id="s1",
        ts=now - 60,
        served=[(ids["deploy"], 0)],
    )
    report = replay_eval(searcher.db, searcher, since_seconds=3600, limit=10, k=3)
    assert report.rank_drift_mean is not None
    assert report.rank_drift_mean > 0  # deploy is no longer rank 1 for this query


def test_gate_replay_fails_closed_with_no_labels(corpus):
    searcher, ids = corpus
    now = time.time()
    _log_query(searcher.db, query="x", session_id="s1", ts=now - 60, served=[(ids["auth"], 0)])
    report = replay_eval(searcher.db, searcher, since_seconds=3600, limit=10, k=3)
    ok, reason = gate_replay(report, {"min_hit_at_1": 0.5})
    assert ok is False
    assert "nothing to gate on" in reason


def test_gate_replay_pass_and_fail_thresholds():
    passing = ReplayReport(
        n=4, n_used_labeled=4, hit_at_1_used=0.9, hit_at_k_used=1.0, mrr_used=0.95,
        tokens_served_median=120.0, rank_drift_mean=0.0, k=5,
    )
    ok, reason = gate_replay(passing, {"min_hit_at_1": 0.8, "max_tokens_served_median": 200})
    assert ok is True and reason == "ok"

    failing_hit = ReplayReport(
        n=4, n_used_labeled=4, hit_at_1_used=0.5, hit_at_k_used=0.5, mrr_used=0.5,
        tokens_served_median=120.0, rank_drift_mean=0.0, k=5,
    )
    ok, reason = gate_replay(failing_hit, {"min_hit_at_1": 0.8})
    assert ok is False and "hit@1" in reason

    failing_tokens = ReplayReport(
        n=4, n_used_labeled=4, hit_at_1_used=0.9, hit_at_k_used=1.0, mrr_used=0.95,
        tokens_served_median=500.0, rank_drift_mean=0.0, k=5,
    )
    ok, reason = gate_replay(failing_tokens, {"min_hit_at_1": 0.5, "max_tokens_served_median": 200})
    assert ok is False and "tokens-served" in reason


def test_format_replay_report_includes_metrics():
    report = ReplayReport(
        n=3, n_used_labeled=2, hit_at_1_used=0.5, hit_at_k_used=1.0, mrr_used=0.75,
        tokens_served_median=88.0, rank_drift_mean=1.5, k=5,
    )
    out = format_replay_report(report)
    assert "n=3" in out and "used-labelled=2" in out
    assert "hit@1(used)=0.50" in out
    assert "rank drift" in out
