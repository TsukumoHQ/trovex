"""Docs ↔ code: the software-engineering graph (task ef1c4106, trovex/links L5).

What differentiates trovex from a generalist note linker: a doc that cites a
source file, a symbol, a ticket id or a commit sha gets a typed edge to the
thing it describes, and trovex tells an agent when a doc has gone *stale* —
the code it documents was committed AFTER the doc last changed (drift).

Edges land in the L1 `doc_refs` table under new kinds (`cites-code`,
`cites-ticket`, `cites-commit`); the kind column was left open for exactly
this. Drift is a per-doc flag (`docs.drift` + `docs.drift_reason`) computed at
index time from git — never shelled out per query. Citations are pulled from
INLINE code spans and markdown links (the opposite of L1, which ignores code
spans): `src/x.py`, `agentd/src/qa.rs:5251`, `Indexer._upsert_doc`, a 7–40 hex
sha, an 8-hex task id, a `#123` PR.
"""

from __future__ import annotations

import re
import sqlite3
import subprocess
from dataclasses import dataclass

from .chunking_code import CODE_EXTENSIONS
from .links_parse import _FENCE_RE, _INLINE_CODE_RE

__all__ = [
    "CodeRef",
    "clear_code_refs",
    "extract_code_refs",
    "git_commit_exists",
    "git_last_commit_ts",
    "recompute_drift_for_code_docs",
    "sync_code_refs",
]

CITE_CODE = "cites-code"
CITE_TICKET = "cites-ticket"
CITE_COMMIT = "cites-commit"
_CITE_KINDS = (CITE_CODE, CITE_TICKET, CITE_COMMIT)

_CODE_EXT_ALT = "|".join(sorted(CODE_EXTENSIONS))
# A repo path: path-ish, ends in a known code extension, optional :line suffix.
_PATH_RE = re.compile(rf"^[\w][\w./\-]*\.(?:{_CODE_EXT_ALT})(?::(\d+))?$")
# A dotted symbol: Class.method / pkg.mod.func — has a dot, no slash, no ext.
_SYMBOL_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")
# A commit sha candidate (validated against the repo before it becomes an edge).
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
_TASK_RE = re.compile(r"^[0-9a-f]{8}$")  # relay task id
# A PR/issue reference in prose: #123.
_PR_RE = re.compile(r"(?<![\w#])#(\d{1,7})\b")


@dataclass(frozen=True)
class CodeRef:
    """One code citation. kind ∈ cites-code|cites-ticket|cites-commit.
    raw: the citation as written. target: the resolution key (path / symbol /
    sha / ticket). anchor: a line number for a `path:line` cite, else None.
    is_symbol: a cites-code that is a dotted symbol rather than a path."""

    kind: str
    raw: str
    target: str
    anchor: str | None
    is_symbol: bool


def _candidates(content: str) -> list[str]:
    """Tokens that live inside INLINE code spans (not fenced blocks). Fenced
    blocks are examples, not citations, so they're blanked first."""
    masked = _FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), content)
    out: list[str] = []
    for m in _INLINE_CODE_RE.finditer(masked):
        span = m.group(0).strip("`").strip()
        # A span can hold several tokens ("see src/a.py and b.py").
        out.extend(tok for tok in re.split(r"[\s,;]+", span) if tok)
    return out


def extract_code_refs(content: str) -> list[CodeRef]:
    """Extract code/symbol/sha citations from inline spans + `#123` from prose.

    Deduped by (kind, target, anchor), first occurrence wins. Sha validation
    and path/symbol resolution happen later (resolve needs the store + repo)."""
    seen: set[tuple[str, str, str | None]] = set()
    out: list[CodeRef] = []

    def add(kind: str, raw: str, target: str, anchor: str | None, is_symbol: bool) -> None:
        key = (kind, target, anchor)
        if key in seen:
            return
        seen.add(key)
        out.append(CodeRef(kind, raw, target, anchor, is_symbol))

    for tok in _candidates(content):
        mp = _PATH_RE.match(tok)
        if mp:
            path = tok.split(":", 1)[0]
            add(CITE_CODE, tok, path, mp.group(1), is_symbol=False)
        elif _SYMBOL_RE.match(tok):
            add(CITE_CODE, tok, tok, None, is_symbol=True)
        elif _SHA_RE.match(tok):
            # Ambiguous sha-or-task — resolved later (a real commit wins; an
            # 8-hex non-commit falls back to a task-id edge).
            add(CITE_COMMIT, tok, tok, None, is_symbol=False)

    for m in _PR_RE.finditer(content):
        add(CITE_TICKET, m.group(0), m.group(0), None, is_symbol=False)

    return out


# --- git (cached; never per-query) -----------------------------------------


def _git(args: list[str], cwd) -> subprocess.CompletedProcess | None:
    """Run git in `cwd`; None if git isn't on PATH / the dir isn't a repo /
    it times out. Callers degrade gracefully — a doc never fails to index
    because of git."""
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None


def git_commit_exists(root, sha: str) -> bool:
    r = _git(["cat-file", "-e", f"{sha}^{{commit}}"], root)
    return r is not None and r.returncode == 0


def git_last_commit_ts(root, relpath: str) -> float | None:
    r = _git(["log", "-1", "--format=%ct", "--", relpath], root)
    if r is None or r.returncode != 0:
        return None
    s = r.stdout.strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _git_commits_since(root, relpath: str, since_ts: float) -> int:
    r = _git(["rev-list", "--count", f"--since={int(since_ts) + 1}", "HEAD", "--", relpath], root)
    if r is None or r.returncode != 0:
        return 0
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def _cached_last_commit_ts(conn, root, source_id: str, path: str, content_hash: str, memo: dict):
    """Last-commit ts of a code file, cached in code_commit_cache keyed by the
    file's content_hash — so an unchanged repo reindex reuses the row and never
    shells out to git. `memo` dedupes within one reindex run."""
    mk = (source_id, path)
    if mk in memo:
        return memo[mk]
    row = conn.execute(
        "SELECT content_hash, last_commit_ts FROM code_commit_cache WHERE source_id = ? AND path = ?",
        (source_id, path),
    ).fetchone()
    if row is not None and row["content_hash"] == content_hash:
        memo[mk] = row["last_commit_ts"]
        return row["last_commit_ts"]
    ts = git_last_commit_ts(root, path)
    conn.execute(
        """INSERT INTO code_commit_cache (source_id, path, content_hash, last_commit_ts)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(source_id, path) DO UPDATE SET content_hash = excluded.content_hash,
               last_commit_ts = excluded.last_commit_ts""",
        (source_id, path, content_hash, ts),
    )
    memo[mk] = ts
    return ts


# --- resolution + edge write ------------------------------------------------


def _resolve_code(conn, source_id: str, ref: CodeRef) -> tuple[int | None, str | None]:
    """Resolve a cites-code ref to an indexed code doc id (+ anchor). A path
    matches a doc in the same source by path; a symbol matches a code chunk
    whose breadcrumb leaf is that symbol (→ its doc + chunk anchor). None if
    nothing indexed matches (no edge is written — AC: nonexistent path)."""
    if not ref.is_symbol:
        row = conn.execute(
            """SELECT id FROM docs
               WHERE source_id = ? AND lower(path) = lower(?) AND workspace_id = 'default'""",
            (source_id, ref.target),
        ).fetchone()
        if row is not None:
            return row["id"], (f"L{ref.anchor}" if ref.anchor else None)
        return None, None
    # Symbol a.b.c: the leaf is the symbol name, the segments before it name its
    # module/class. Resolve in two ways, precise first:
    segs = ref.target.split(".")
    leaf = segs[-1]
    # (A) a code chunk whose breadcrumb leaf IS this symbol (gives an exact
    #     anchor; only works when the file was split per-symbol).
    rows = conn.execute(
        """SELECT c.doc_id, c.anchor, c.heading_path FROM chunks c JOIN docs d ON d.id = c.doc_id
           WHERE d.source_id = ? AND d.workspace_id = 'default'
             AND (c.heading_path LIKE ? OR c.heading_path LIKE ?)""",
        (source_id, f"%{leaf}", f"%{leaf} %"),
    ).fetchall()
    hits = {(r["doc_id"], r["anchor"]) for r in rows if _leaf_matches(r["heading_path"], leaf)}
    docs = {d for d, _a in hits}
    if len(docs) == 1:
        doc_id = next(iter(docs))
        return doc_id, next((a for d, a in hits if d == doc_id), None)
    # (B) fallback: a module/class segment names a code file (basename), and the
    #     file actually contains the leaf. Closest segment to the leaf wins; a
    #     tiny file is one line-labelled chunk, so (A) can't fire there.
    for seg in reversed(segs[:-1]):
        doc_id = _code_doc_by_basename(conn, source_id, seg.lower())
        if doc_id is None:
            continue
        hit = conn.execute(
            "SELECT anchor FROM chunks WHERE doc_id = ? AND content LIKE ? LIMIT 1",
            (doc_id, f"%{leaf}%"),
        ).fetchone()
        if hit is not None:
            return doc_id, hit["anchor"]
    return None, None


def _code_doc_by_basename(conn, source_id: str, name: str) -> int | None:
    """A unique code doc in `source_id` whose filename (minus extension) is
    `name` (case-insensitive). None if absent or ambiguous."""
    from .chunking_code import CODE_EXTENSIONS

    rows = conn.execute(
        """SELECT id, path FROM docs
           WHERE source_id = ? AND workspace_id = 'default'
             AND (lower(path) = ? OR lower(path) LIKE ?)""",
        (source_id, name, "%/" + name + ".%"),
    ).fetchall()
    hits = {
        r["id"]
        for r in rows
        if "." in r["path"]
        and r["path"].rsplit("/", 1)[-1].rsplit(".", 1)[0].lower() == name
        and r["path"].rsplit(".", 1)[-1].lower() in CODE_EXTENSIONS
    }
    return next(iter(hits)) if len(hits) == 1 else None


def _leaf_matches(heading_path: str | None, leaf: str) -> bool:
    """True if a chunk breadcrumb's last segment names `leaf` (ignoring a
    `class `/`def `/`fn ` kind prefix)."""
    if not heading_path:
        return False
    last = heading_path.replace(">", " ").split()[-1] if heading_path.strip() else ""
    return last == leaf


def clear_code_refs(conn, src_id: int) -> None:
    conn.execute(
        f"DELETE FROM doc_refs WHERE src_id = ? AND kind IN ({','.join('?' * len(_CITE_KINDS))})",
        (src_id, *_CITE_KINDS),
    )


def sync_code_refs(
    conn: sqlite3.Connection,
    *,
    src_id: int,
    source_id: str,
    path: str,
    content: str,
    git_root,
    doc_mtime: float,
    memo: dict | None = None,
) -> None:
    """Refresh doc `src_id`'s code citations and recompute its drift flag.

    git_root is the source's repo root (None = not a git-backed source: paths
    still resolve by indexed path, but sha validation and drift are skipped).
    Does NOT commit — the caller owns the transaction."""
    memo = {} if memo is None else memo
    clear_code_refs(conn, src_id)
    for ref in extract_code_refs(content):
        dst_id: int | None = None
        anchor = ref.anchor
        kind = ref.kind
        if ref.kind == CITE_CODE:
            dst_id, anchor = _resolve_code(conn, source_id, ref)
            if dst_id is None:
                continue  # nonexistent path/symbol → no edge
        elif ref.kind == CITE_COMMIT:
            if git_root is not None and git_commit_exists(git_root, ref.target):
                pass  # real commit
            elif _TASK_RE.match(ref.target):
                kind = CITE_TICKET  # 8-hex non-commit → a task id
            else:
                continue  # unknown sha → no edge
        conn.execute(
            """INSERT OR IGNORE INTO doc_refs
                   (src_id, dst_id, dst_raw, dst_norm, anchor, alias, context, kind)
               VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)""",
            (src_id, dst_id, ref.target, ref.target.rsplit("/", 1)[-1].lower(), anchor, kind),
        )
    _compute_drift(conn, src_id, git_root, doc_mtime, memo)


def _compute_drift(conn, src_id: int, git_root, doc_mtime: float, memo: dict) -> None:
    """Set docs.drift/drift_reason: drifted when any cited code file has a
    commit newer than this doc's last change."""
    if git_root is None:
        conn.execute("UPDATE docs SET drift = 0, drift_reason = NULL WHERE id = ?", (src_id,))
        return
    doc = conn.execute(
        "SELECT source_id, path, content_hash FROM docs WHERE id = ?", (src_id,)
    ).fetchone()
    doc_ts = git_last_commit_ts(git_root, doc["path"]) if doc else None
    if doc_ts is None:
        doc_ts = doc_mtime
    cited = conn.execute(
        """SELECT d.source_id AS s, d.path AS p, d.content_hash AS h
           FROM doc_refs r JOIN docs d ON d.id = r.dst_id
           WHERE r.src_id = ? AND r.kind = ? AND r.dst_id IS NOT NULL""",
        (src_id, CITE_CODE),
    ).fetchall()
    worst_reason: str | None = None
    for c in cited:
        cts = _cached_last_commit_ts(conn, git_root, c["s"], c["p"], c["h"] or "", memo)
        if cts is not None and cts > doc_ts:
            n = _git_commits_since(git_root, c["p"], doc_ts)
            worst_reason = f"{c['p']} changed {n} commit(s) after this doc"
            break
    conn.execute(
        "UPDATE docs SET drift = ?, drift_reason = ? WHERE id = ?",
        (1 if worst_reason else 0, worst_reason, src_id),
    )


def recompute_drift_for_code_docs(
    conn: sqlite3.Connection, changed_code_doc_ids, git_root_by_source: dict, now: float
) -> None:
    """After a reindex, re-drift every doc that CITES a code file which changed
    this run — the citing doc wasn't itself touched, so its flag is stale.
    Incremental: only fires for docs with a cites-code edge to a changed file."""
    if not changed_code_doc_ids:
        return
    memo: dict = {}
    placeholders = ",".join("?" * len(changed_code_doc_ids))
    srcs = conn.execute(
        f"""SELECT DISTINCT r.src_id FROM doc_refs r
            WHERE r.kind = ? AND r.dst_id IN ({placeholders})""",
        (CITE_CODE, *changed_code_doc_ids),
    ).fetchall()
    for row in srcs:
        doc = conn.execute(
            "SELECT source_id, mtime FROM docs WHERE id = ?", (row["src_id"],)
        ).fetchone()
        if doc is None:
            continue
        root = git_root_by_source.get(doc["source_id"])
        _compute_drift(conn, row["src_id"], root, doc["mtime"], memo)
