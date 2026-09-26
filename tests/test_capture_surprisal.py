"""Surprisal gate on capture (steal #13): embed the incoming capture, compare it
to the agent's own owner/<agent> records, and pick skip | verbatim | distil
BEFORE any LLM call. Deterministic, keyless.

Hermetic: an angle-controlled fake embedder (`angle=<cos>` in the text sets the
cosine to the reference direction), a counting stub for the distiller.
"""

from __future__ import annotations

import math
import re

import numpy as np
import pytest

from trovex import capture
from trovex.capture import capture_state
from trovex.config import Settings
from trovex.store import SqliteStore

DIM = 384
LONG = " ".join(f"detail{i}" for i in range(400))  # > 1500 chars
SHORT = "short state update"


class AngleEmbedder:
    """`angle=<c>` anywhere in the text → unit vector at cosine c to e0 (c=1.0 is e0);
    no marker → orthogonal to every marked vector."""

    name = "angle"
    dim = DIM

    def embed(self, texts):
        for t in texts:
            v = np.zeros(DIM, dtype=np.float32)
            m = re.search(r"angle=([0-9.]+)", t)
            if m:
                c = float(m.group(1))
                v[0] = c
                v[1] = math.sqrt(max(0.0, 1.0 - c * c))
            else:
                v[2] = 1.0
            yield v


def _store(tmp_path, **cfg):
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
        **cfg,
    )
    return SqliteStore(settings, embedder=AngleEmbedder())


@pytest.fixture
def store(tmp_path):
    return _store(tmp_path)


@pytest.fixture
def distil_calls(monkeypatch):
    calls: list[dict] = []

    def fake(text, *, prior=""):
        calls.append({"text": text, "prior": prior})
        return "### Done this session\ndistilled state " + "x" * 40

    monkeypatch.setattr(capture, "distil_summary", fake)
    return calls


def _seed(store, agent="alpha"):
    out = capture_state(store, agent, f"angle=1.0 {SHORT}")
    assert out["captured"] is True
    return out


def test_near_duplicate_capture_is_skipped_and_recorded(store, distil_calls):
    _seed(store)
    before = store.get("owner-alpha-current-state").content
    out = capture_state(store, "alpha", f"angle=0.97 {SHORT}")
    assert out["captured"] is False
    assert out["decision"] == "skip"
    assert out["reason"] == "near-duplicate"
    assert out["nearest_doc_id"] == "owner-alpha-current-state"
    assert out["max_cos"] == pytest.approx(0.97, abs=0.01)
    assert store.get("owner-alpha-current-state").content == before  # no churn
    assert distil_calls == []
    row = store.db.execute(
        "SELECT agent, decision, max_cos, nearest_doc_id FROM capture_decisions "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert (row["agent"], row["decision"], row["nearest_doc_id"]) == (
        "alpha",
        "skip",
        "owner-alpha-current-state",
    )
    assert row["max_cos"] == pytest.approx(0.97, abs=0.01)


def test_middle_band_is_written_verbatim_without_the_distiller(store, distil_calls):
    _seed(store)
    summary = f"angle=0.9 {LONG}"
    out = capture_state(store, "alpha", summary)
    assert out["captured"] is True
    assert out["decision"] == "verbatim"
    assert distil_calls == []
    assert summary in store.get("owner-alpha-current-state").content


def test_novel_long_capture_calls_the_distiller_once(store, distil_calls):
    _seed(store)
    out = capture_state(store, "alpha", f"angle=0.5 {LONG}")
    assert out["decision"] == "distil"
    assert len(distil_calls) == 1
    assert "detail399" in distil_calls[0]["text"]
    assert "distilled state" in store.get("owner-alpha-current-state").content


def test_novel_but_short_capture_is_verbatim(store, distil_calls):
    _seed(store)
    out = capture_state(store, "alpha", f"angle=0.5 {SHORT}")
    assert out["decision"] == "verbatim"
    assert distil_calls == []


def test_first_capture_with_no_owner_records_is_novel(store, distil_calls):
    out = capture_state(store, "beta", f"angle=1.0 {LONG}")
    assert out["decision"] == "distil"
    assert out["max_cos"] is None
    assert len(distil_calls) == 1


def test_gate_only_compares_against_the_agents_own_records(store, distil_calls):
    _seed(store, "alpha")
    out = capture_state(store, "beta", f"angle=1.0 {SHORT}")  # identical, other owner
    assert out["captured"] is True
    assert out["decision"] == "verbatim"


def test_skip_threshold_of_one_disables_the_gate(tmp_path, distil_calls):
    store = _store(tmp_path, capture_skip_cosine=1.0)
    _seed(store)
    out = capture_state(store, "alpha", f"angle=1.0 {SHORT} again")
    assert out["captured"] is True
    assert out["decision"] == "verbatim"


def test_thresholds_and_min_length_are_config_keys(tmp_path, distil_calls):
    s = Settings(data_dir=tmp_path)
    assert (s.capture_skip_cosine, s.capture_verbatim_cosine, s.capture_distil_min_chars) == (
        0.95,
        0.80,
        1500,
    )
    store = _store(tmp_path / "x", capture_distil_min_chars=20)
    _seed(store)
    out = capture_state(store, "alpha", f"angle=0.5 {SHORT} but longer than twenty")
    assert out["decision"] == "distil"


def test_transcript_capture_is_gated_before_the_distiller(store, distil_calls):
    _seed(store)
    dup = capture_state(store, "alpha", transcript=f"angle=0.99 {LONG}")
    assert dup["decision"] == "skip"
    assert distil_calls == []
    novel = capture_state(store, "alpha", transcript=f"angle=0.3 {LONG}")
    assert novel["decision"] == "distil"
    assert len(distil_calls) == 1
    assert distil_calls[0]["prior"]  # merged with the prior state


def test_capture_response_exposes_run_counts(store, distil_calls):
    _seed(store)  # verbatim
    capture_state(store, "alpha", f"angle=0.97 {SHORT}")  # skip
    out = capture_state(store, "alpha", f"angle=0.5 {LONG}")  # distil
    assert out["counts"] == {"skip": 1, "verbatim": 1, "distil": 1}
