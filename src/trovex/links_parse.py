"""Obsidian-style doc-link extraction + resolution (task a1b5a169, trovex/links L1).

Parses `[[wikilinks]]` and relative `.md` markdown links out of indexed doc
content and records them as rows in the `doc_refs` table — one queryable edge
per link, including links to docs that do not exist yet (kept as *dangling*
refs with `dst_id IS NULL`).

Why a separate table from `doc_links`: `doc_links` (db.py) is a small, curated,
typed edge set (supersedes / verdict-of / …) written by hand through
`trovex_write(links=)`, resolved by `ext_id` only, between trovex-owned docs.
`doc_refs` is the opposite: extracted automatically from ANY indexed doc
(file-backed included), untyped beyond links-to / embeds, and deliberately keeps
edges whose target is missing so a link to a not-yet-created note is still a real
edge the moment that note appears. The two never mix.

All DB mutation lives here (not in db.py / store.py / indexer.py, which are each
already >800 lines); those modules call `sync_doc_refs` from their upsert paths.
"""

from __future__ import annotations

import posixpath
import re
import sqlite3
from dataclasses import dataclass

__all__ = ["ParsedRef", "parse_links", "resolve_ref", "sync_doc_refs"]

_CONTEXT_LIMIT = 160

# A fenced code block: ``` … ``` or ~~~ … ~~~ (the fence char repeated >=3).
# DOTALL so it spans lines; non-greedy so adjacent blocks don't merge.
_FENCE_RE = re.compile(r"(?P<f>`{3,}|~{3,}).*?(?P=f)", re.DOTALL)
# Inline code: a run of backticks … matching run of backticks, single line.
_INLINE_CODE_RE = re.compile(r"(`+)(?:.*?)\1")

# [[target]], [[target#anchor]], [[target|alias]], [[target#anchor|alias]],
# and the embed form ![[target]]. The inner part forbids ']' and newlines.
_WIKILINK_RE = re.compile(r"(?P<embed>!?)\[\[(?P<inner>[^\]\n]+?)\]\]")
# Markdown link / embed: [text](href) or ![text](href). href forbids ws and ')'.
_MDLINK_RE = re.compile(r"(?P<embed>!?)\[(?P<text>[^\]\n]*)\]\((?P<href>[^)\s]+)\)")

_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.\-]*://|^(?:mailto|tel):", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedRef:
    """One link extracted from a doc's content.

    kind: 'links-to' (plain link) or 'embeds' (the `![[...]]` / `![](..)` form).
    target: the raw link target as written (wikilink name, or md link path),
        with any `#anchor` and `|alias` stripped off.
    anchor: the `#heading` fragment if present, else None.
    alias: the display text (`[[x|alias]]` or the `[text](..)` text), else None.
    context: the surrounding sentence (collapsed whitespace), <=160 chars.
    """

    kind: str
    target: str
    anchor: str | None
    alias: str | None
    context: str


def _mask_code(content: str) -> str:
    """Replace code-fence and inline-code spans with spaces of equal length.

    Links inside code must NOT be extracted, but blanking the spans while
    preserving every character offset (and newlines) means the surviving match
    positions still index the original text for context extraction.
    """

    def blank(m: re.Match) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in m.group(0))

    masked = _FENCE_RE.sub(blank, content)
    masked = _INLINE_CODE_RE.sub(blank, masked)
    return masked


_SENT_BOUND = ".!?\n"


def _context(text: str, start: int, end: int) -> str:
    """The sentence containing [start:end], whitespace-collapsed, <=160 chars."""
    left = max((text.rfind(c, 0, start) for c in _SENT_BOUND), default=-1)
    rights = [p for p in (text.find(c, end) for c in _SENT_BOUND) if p != -1]
    right = min(rights) if rights else len(text)
    sentence = text[left + 1 : right].strip()
    sentence = re.sub(r"\s+", " ", sentence)
    if len(sentence) > _CONTEXT_LIMIT:
        sentence = sentence[:_CONTEXT_LIMIT].rstrip()
    return sentence


def _split_target(inner: str) -> tuple[str, str | None, str | None]:
    """Split a wikilink inner (`target#anchor|alias`) into its three parts."""
    alias: str | None = None
    if "|" in inner:
        inner, alias = inner.split("|", 1)
        alias = alias.strip() or None
    anchor: str | None = None
    if "#" in inner:
        inner, anchor = inner.split("#", 1)
        anchor = anchor.strip() or None
    return inner.strip(), anchor, alias


def _is_md_target(href: str) -> bool:
    """A markdown href we treat as a cross-doc edge: a relative `.md` path.

    External URLs, mailto/tel, and bare in-page anchors (`#x`) are not edges.
    """
    if not href or href.startswith("#") or _URL_SCHEME_RE.match(href):
        return False
    path = href.split("#", 1)[0]
    return path.lower().endswith(".md")


def parse_links(content: str) -> list[ParsedRef]:
    """Extract every wikilink and relative `.md` markdown link from `content`.

    Links inside fenced or inline code are ignored. Duplicates (same target +
    anchor) are collapsed, keeping the first occurrence's context/alias.
    """
    masked = _mask_code(content)
    seen: set[tuple[str, str | None]] = set()
    out: list[ParsedRef] = []

    for m in _WIKILINK_RE.finditer(masked):
        target, anchor, alias = _split_target(m.group("inner"))
        if not target:
            continue
        key = (target, anchor)
        if key in seen:
            continue
        seen.add(key)
        kind = "embeds" if m.group("embed") else "links-to"
        out.append(
            ParsedRef(kind, target, anchor, alias, _context(masked, m.start(), m.end()))
        )

    for m in _MDLINK_RE.finditer(masked):
        href = m.group("href")
        if not _is_md_target(href):
            continue
        path, _, anchor = href.partition("#")
        anchor = anchor.strip() or None
        target = path.strip()
        key = (target, anchor)
        if key in seen:
            continue
        seen.add(key)
        kind = "embeds" if m.group("embed") else "links-to"
        alias = (m.group("text") or "").strip() or None
        out.append(
            ParsedRef(kind, target, anchor, alias, _context(masked, m.start(), m.end()))
        )

    return out


def _norm_key(target: str) -> str:
    """The dangling-rebind lookup key for a target: basename, no `.md`, lower.

    `[[some/file]]` -> 'file'; `../b.md` -> 'b'; `[[Some Title]]` -> 'some title'.
    Stored on every row so re-binding a dangling ref when its target doc appears
    is one indexed lookup instead of a full re-resolve of every dangling row.
    """
    base = target.strip().rsplit("/", 1)[-1]
    if base.lower().endswith(".md"):
        base = base[:-3]
    return base.strip().lower()


def _basename_noext(path: str) -> str:
    base = path.rsplit("/", 1)[-1]
    if base.lower().endswith(".md"):
        base = base[:-3]
    return base.lower()


def resolve_ref(
    conn: sqlite3.Connection, src_source_id: str, src_path: str, target: str
) -> int | None:
    """Resolve a link `target` (written in a doc at src_source_id/src_path) to a
    doc id, or None if nothing matches (dangling).

    Order (first unique match wins):
      1. same-source relative path  — target joined onto the src doc's directory
      2. basename                   — a doc whose filename matches, if unique
      3. title / canonical_topic    — a doc so titled, if unique
      4. ext_id                     — an owned doc's opaque id (exact)
    """
    from .db import canonical_topic_slug

    target = target.strip()
    if not target:
        return None

    # 1. same-source relative path (only meaningful for file-backed sources,
    #    whose `path` is a real relative path — owned docs' path is their ext_id).
    # normpath collapses "sub/../b.md" -> "b.md" and "./b.md" -> "b.md". A target
    # that escapes the source root keeps its leading ".." and matches no relative
    # doc path, so it correctly falls through to the later resolution steps.
    cand = posixpath.normpath(posixpath.join(posixpath.dirname(src_path), target))
    variants = [cand]
    if not cand.lower().endswith(".md"):
        variants.append(cand + ".md")
    for v in variants:
        row = conn.execute(
            """SELECT id FROM docs
               WHERE source_id = ? AND lower(path) = lower(?) AND workspace_id = 'default'""",
            (src_source_id, v),
        ).fetchone()
        if row is not None:
            return row["id"]

    # 2. basename. Narrow with LIKE, confirm basename in Python. Prefer a match
    #    WITHIN the src doc's own source (2a) before the global store (2b): a
    #    [[design]] in repo A must bind to A's design.md even when repo B also
    #    has one — only fall back to a global-unique match when the src source
    #    has none.
    name = _norm_key(target)
    if name:
        like = (name, name + ".md", "%/" + name, "%/" + name + ".md")
        same = conn.execute(
            """SELECT id, path FROM docs
               WHERE workspace_id = 'default' AND source_id = ?
                 AND (lower(path) = ? OR lower(path) = ? OR lower(path) LIKE ? OR lower(path) LIKE ?)""",
            (src_source_id, *like),
        ).fetchall()
        same_hits = {r["id"] for r in same if _basename_noext(r["path"]) == name}
        if len(same_hits) == 1:
            return next(iter(same_hits))
        if not same_hits:  # 2b: global-unique, only when the src source has none
            rows = conn.execute(
                """SELECT id, path FROM docs
                   WHERE workspace_id = 'default'
                     AND (lower(path) = ? OR lower(path) = ? OR lower(path) LIKE ? OR lower(path) LIKE ?)""",
                like,
            ).fetchall()
            hits = {r["id"] for r in rows if _basename_noext(r["path"]) == name}
            if len(hits) == 1:
                return next(iter(hits))

    # 3. title / canonical_topic (unique).
    slug = canonical_topic_slug(target)
    rows = conn.execute(
        """SELECT id FROM docs
           WHERE workspace_id = 'default'
             AND (lower(title) = lower(?) OR (canonical_topic IS NOT NULL AND canonical_topic = ?))""",
        (target, slug or ""),
    ).fetchall()
    if len(rows) == 1:
        return rows[0]["id"]

    # 4. ext_id (exact).
    row = conn.execute(
        "SELECT id FROM docs WHERE ext_id = ? AND workspace_id = 'default'", (target,)
    ).fetchone()
    if row is not None:
        return row["id"]

    return None


def sync_doc_refs(
    conn: sqlite3.Connection,
    *,
    src_id: int,
    source_id: str,
    path: str,
    content: str,
) -> None:
    """Refresh the outgoing refs of doc `src_id` from its current `content`, then
    re-bind any dangling ref (from any doc) that now resolves to this doc.

    Does NOT commit — the caller owns the transaction. Idempotent: a re-sync of
    unchanged content yields the identical row set.
    """
    # (a) Replace this doc's outgoing refs wholesale — cheap, and the only way a
    #     content edit that DROPPED a link removes the stale edge.
    conn.execute("DELETE FROM doc_refs WHERE src_id = ?", (src_id,))
    for ref in parse_links(content):
        dst_id = resolve_ref(conn, source_id, path, ref.target)
        conn.execute(
            """INSERT OR IGNORE INTO doc_refs
                   (src_id, dst_id, dst_raw, dst_norm, anchor, alias, context, kind)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                src_id,
                dst_id,
                ref.target,
                _norm_key(ref.target),
                ref.anchor,
                ref.alias,
                ref.context,
                ref.kind,
            ),
        )

    # (b) This doc may be the target a dangling ref has been waiting for (a new
    #     note, or a rename making a basename newly unique). Re-resolve only the
    #     dangling rows whose lookup key could point here, and bind the ones that
    #     now do — covers rename (delete+insert) and links to future docs.
    meta = conn.execute(
        "SELECT title, canonical_topic, ext_id FROM docs WHERE id = ?", (src_id,)
    ).fetchone()
    keys: set[str] = {_basename_noext(path)}
    if meta is not None:
        if meta["title"]:
            keys.add(meta["title"].strip().lower())
        if meta["canonical_topic"]:
            keys.add(meta["canonical_topic"])
        if meta["ext_id"]:
            keys.add(meta["ext_id"].strip().lower())
    keys.discard("")
    if not keys:
        return
    placeholders = ",".join("?" for _ in keys)
    dangling = conn.execute(
        f"""SELECT r.id, r.dst_raw, d.source_id AS src_source_id, d.path AS src_path
            FROM doc_refs r JOIN docs d ON d.id = r.src_id
            WHERE r.dst_id IS NULL AND r.dst_norm IN ({placeholders})""",  # noqa: S608 - keys are bind params
        tuple(keys),
    ).fetchall()
    for row in dangling:
        bound = resolve_ref(conn, row["src_source_id"], row["src_path"], row["dst_raw"])
        if bound is not None:
            conn.execute("UPDATE doc_refs SET dst_id = ? WHERE id = ?", (bound, row["id"]))
