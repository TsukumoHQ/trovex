"""Graduated-access ladder on trovex_read — card → passage → full.

Steal #3: a deliberate escalation ladder proves token-discipline. tier 1 (card)
is a breadcrumb + ~50-word extract; tier 2 (passage, the default) is the best
section; tier 3 (full) is the whole doc. Each rung must cost strictly more than
the one below, the default must stay passage, and `full=true` must still mean
the full rung (back-compat).

Hermetic: deterministic BagEmbedder, no model download / network.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from trovex import mcp_app
from trovex import state as state_mod
from trovex.config import Settings
from trovex.indexer import Indexer
from trovex.search import Searcher
from trovex.state import AppState
from trovex.store import SqliteStore
from trovex.tokens import count_tokens

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


# A doc with TWO long sections: the card extract truncates one section, the
# passage returns that whole section, and full returns BOTH — so the three rungs
# are strictly increasing in size (card < passage < full).
_SECTION_A = " ".join(f"deployment reverse proxy word{i}" for i in range(120))
_SECTION_B = " ".join(f"backups restore snapshot note{i}" for i in range(120))
_DOC = (
    f"# Deploying the service\n\n## Reverse proxy\n\n{_SECTION_A}\n\n## Backups\n\n{_SECTION_B}\n"
)
_QUERY = "how do I deploy behind a reverse proxy"


@pytest.fixture
def wired(tmp_path, monkeypatch):
    monkeypatch.setenv("TROVEX_ALLOW_UNAUTH_WRITES", "1")
    settings = Settings(
        data_dir=tmp_path,
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )
    store = SqliteStore(settings, embedder=BagEmbedder())
    store.put(_DOC, kind="record")
    state_mod._state = AppState(
        settings=settings,
        embedder=BagEmbedder(),
        searcher=Searcher(settings, embedder=BagEmbedder()),
        indexer=Indexer(settings, embedder=BagEmbedder()),
        store=store,
    )
    try:
        yield state_mod._state
    finally:
        state_mod.reset_state()


def _tokens_of(text: str) -> int:
    # strip the inline savings counter line so we compare payloads, not the tail
    return count_tokens(text.split("—", 1)[0])


def test_card_is_breadcrumb_plus_extract(wired):
    out = mcp_app.trovex_read(q=_QUERY, tier="card")
    assert "Deploying the service > Reverse proxy" in out
    assert "· card" in out
    assert 'tier="passage"' in out and 'tier="full"' in out  # escalation hint
    assert out.strip().split("\n\n")[1].endswith("…")  # truncated extract


def test_default_is_passage(wired):
    default = mcp_app.trovex_read(q=_QUERY)
    passage = mcp_app.trovex_read(q=_QUERY, tier="passage")
    assert default.split("— trovex")[0] == passage.split("— trovex")[0]
    # passage carries the full section, not just the card extract
    assert "word119" in passage


def test_full_returns_whole_doc(wired):
    out = mcp_app.trovex_read(q=_QUERY, tier="full")
    assert out.startswith("# Deploying the service")
    assert "word119" in out


def test_full_true_still_aliases_full(wired):
    via_flag = mcp_app.trovex_read(q=_QUERY, full=True)
    via_tier = mcp_app.trovex_read(q=_QUERY, tier="full")
    assert via_flag == via_tier
    assert via_flag.startswith("# Deploying the service")


def test_rungs_cost_strictly_more_going_up(wired):
    card = _tokens_of(mcp_app.trovex_read(q=_QUERY, tier="card"))
    passage = _tokens_of(mcp_app.trovex_read(q=_QUERY, tier="passage"))
    full = _tokens_of(mcp_app.trovex_read(q=_QUERY, tier="full"))
    assert card < passage < full


def test_unknown_tier_is_typed_error(wired):
    out = mcp_app.trovex_read(q=_QUERY, tier="everything")
    assert "unknown_tier" in out


def test_tier_is_case_insensitive(wired):
    assert "· card" in mcp_app.trovex_read(q=_QUERY, tier="CARD")


def test_passage_returns_matched_section_not_the_other(wired):
    """The passage rung returns the section the query matched (reverse proxy),
    not the whole doc — full is the rung that carries both sections."""
    passage = mcp_app.trovex_read(q=_QUERY, tier="passage")
    assert "word119" in passage  # the matched section
    assert "note119" not in passage  # the OTHER section only shows up at full
    assert "note119" in mcp_app.trovex_read(q=_QUERY, tier="full")
