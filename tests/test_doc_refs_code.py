"""Docs ↔ code edges + drift (task ef1c4106, trovex/links L5): cites-code
(path + symbol), sha/path safety, drift from git, and the no-git-per-doc cache.
Hermetic: bag-of-words embedder (no model download) + a real local git repo.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess

import numpy as np
import pytest

from trovex import code_refs
from trovex import sources as sources_mod
from trovex.code_refs import extract_code_refs
from trovex.config import Settings
from trovex.indexer import Indexer

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


def _git(args, cwd, when=None):
    env = os.environ.copy()
    env.update(
        GIT_AUTHOR_NAME="t", GIT_COMMITTER_NAME="t",
        GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_EMAIL="t@t",
    )
    if when:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path / "data",
        embed_model="BAAI/bge-small-en-v1.5",
        sources_config_path=tmp_path / "no-such-sources.yaml",
    )


def _indexer(settings, root):
    idx = Indexer(settings, embedder=BagEmbedder())
    sources_mod.add_source(idx.db, id="code", root=root)
    return idx


def _reindex(idx):
    return idx.reindex(sources=idx.settings.load_sources())


def _refs(idx, src_path):
    return idx.db.execute(
        """SELECT r.kind, r.dst_id, r.dst_raw, r.anchor FROM doc_refs r JOIN docs d ON d.id = r.src_id
           WHERE d.source_id = 'code' AND d.path = ?""",
        (src_path,),
    ).fetchall()


def _doc_id(idx, path):
    r = idx.db.execute("SELECT id FROM docs WHERE source_id='code' AND path=?", (path,)).fetchone()
    return r["id"] if r else None


# --- AC1: parser + cites-code to a file (path) and a symbol (file + anchor) --


def test_extract_code_refs_forms():
    content = (
        "Uses `src/a.py` and `agentd/src/qa.rs:52` and symbol `Indexer._upsert_doc`.\n"
        "Commit `deadbeef1` and PR #123.\n\n"
        "```\n`src/ignored.py` inside a fence is not a citation\n```\n"
    )
    refs = {(r.kind, r.target): r for r in extract_code_refs(content)}
    assert ("cites-code", "src/a.py") in refs
    assert refs[("cites-code", "agentd/src/qa.rs")].anchor == "52"
    assert refs[("cites-code", "Indexer._upsert_doc")].is_symbol is True
    assert ("cites-commit", "deadbeef1") in refs
    assert ("cites-ticket", "#123") in refs
    assert not any(t == "src/ignored.py" for _k, t in refs)  # fenced span ignored


def test_cites_code_resolves_path_and_symbol(settings, tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "mod.py").write_text(
        "def func():\n    return 1\n\n\ndef other():\n    return 2\n", encoding="utf-8"
    )
    (root / "doc.md").write_text(
        "# Doc\n\nDescribes `src/mod.py`, specifically `pkg.mod.func`.\n", encoding="utf-8"
    )
    idx = _indexer(settings, root)
    _reindex(idx)

    mod_id = _doc_id(idx, "src/mod.py")
    cc = [r for r in _refs(idx, "doc.md") if r["kind"] == "cites-code"]
    by_raw = {r["dst_raw"]: r for r in cc}
    assert by_raw["src/mod.py"]["dst_id"] == mod_id
    sym = by_raw["pkg.mod.func"]
    assert sym["dst_id"] == mod_id  # symbol resolved to its file
    assert sym["anchor"]  # with the defining chunk's anchor


# --- AC3: unknown sha / nonexistent path → no edge, no crash -----------------


def test_unknown_sha_and_missing_path_make_no_edge(settings, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(["init", "-q"], root)
    (root / "doc.md").write_text(
        "# Doc\n\nCites missing `src/nope.py` and bogus `deadbeefdeadbeefdeadbeefdeadbeefdeadbeef`.\n",
        encoding="utf-8",
    )
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "init"], root)
    idx = _indexer(settings, root)
    _reindex(idx)  # must not raise

    rows = _refs(idx, "doc.md")
    assert all(r["dst_raw"] != "src/nope.py" for r in rows)  # nonexistent path → no edge
    assert all(r["kind"] != "cites-commit" for r in rows)  # unknown 40-hex → no edge


# --- AC2: drift from git; clears when the doc is rewritten after the code ----


def test_drift_sets_and_clears(settings, tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / "doc.md").write_text("# Doc\n\nDocuments `src/a.py`.\n", encoding="utf-8")
    _git(["init", "-q"], root)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "t1"], root, when="2021-01-01T00:00:00")

    idx = _indexer(settings, root)
    _reindex(idx)
    assert idx.db.execute("SELECT drift FROM docs WHERE path='doc.md'").fetchone()["drift"] == 0

    # a.py gets a commit AFTER the doc → doc drifts.
    (root / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
    _git(["commit", "-aqm", "t2"], root, when="2021-02-01T00:00:00")
    _reindex(idx)
    row = idx.db.execute("SELECT drift, drift_reason FROM docs WHERE path='doc.md'").fetchone()
    assert row["drift"] == 1
    assert "src/a.py" in row["drift_reason"] and "commit" in row["drift_reason"]

    # Doc rewritten + committed after the code → drift clears.
    (root / "doc.md").write_text("# Doc\n\nDocuments `src/a.py` (updated).\n", encoding="utf-8")
    _git(["commit", "-aqm", "t3"], root, when="2021-03-01T00:00:00")
    _reindex(idx)
    assert idx.db.execute("SELECT drift FROM docs WHERE path='doc.md'").fetchone()["drift"] == 0


# --- AC4: an unchanged-repo reindex calls git zero times (cached) ------------


def test_unchanged_reindex_calls_no_git(settings, tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / "doc.md").write_text("# Doc\n\nDocuments `src/a.py`.\n", encoding="utf-8")
    _git(["init", "-q"], root)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "t1"], root, when="2021-01-01T00:00:00")

    idx = _indexer(settings, root)
    _reindex(idx)  # first run does touch git

    calls = {"n": 0}
    real_git = code_refs._git

    def counting(*a, **k):
        calls["n"] += 1
        return real_git(*a, **k)

    monkeypatch.setattr(code_refs, "_git", counting)
    _reindex(idx)  # nothing changed → no doc touched → no git
    assert calls["n"] == 0
