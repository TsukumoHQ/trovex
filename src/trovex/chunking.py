"""Structure-aware markdown chunking for chunk-level retrieval.

The literature consensus (arXiv:2603.24556, 2606.00881) is that structure-aware
chunking beats semantic/sliding-window at lower cost — and markdown gives us the
structure for free. We split on headings, keep a heading breadcrumb per chunk,
and resplit oversized sections by paragraph windows.

Each chunk's embed text is *prefix-fused* with its breadcrumb ("title > h1 > h2")
— the single biggest retrieval gain per arXiv:2510.24402, kept small ("seasoning",
not a metadata dump) per the same line of work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
FENCE_RE = re.compile(r"^\s*```")

DEFAULT_MAX_TOKENS = 450


@dataclass
class Chunk:
    index: int
    heading_path: list[str] = field(default_factory=list)
    text: str = ""
    tokens_est: int = 0

    def breadcrumb(self, title: str = "") -> str:
        parts = ([title] if title else []) + self.heading_path
        return " > ".join(p for p in parts if p)

    def embed_text(self, title: str = "") -> str:
        """Prefix-fusion: breadcrumb + body — the text we actually embed."""
        bc = self.breadcrumb(title)
        return f"{bc}\n\n{self.text}" if bc else self.text


def _est_tokens(text: str) -> int:
    return len(text) // 4


def _split_to_size(text: str, max_tokens: int) -> list[str]:
    if _est_tokens(text) <= max_tokens:
        return [text]
    paras = re.split(r"\n\s*\n", text)
    out: list[str] = []
    cur: list[str] = []
    cur_tok = 0
    for p in paras:
        pt = _est_tokens(p)
        if cur and cur_tok + pt > max_tokens:
            out.append("\n\n".join(cur))
            cur, cur_tok = [], 0
        cur.append(p)
        cur_tok += pt
        if cur_tok > max_tokens and len(cur) == 1:  # lone oversized paragraph
            out.append("\n\n".join(cur))
            cur, cur_tok = [], 0
    if cur:
        out.append("\n\n".join(cur))
    return [o for o in (s.strip() for s in out) if o]


def chunk_markdown(content: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> list[Chunk]:
    """Split markdown into structure-aware chunks with heading breadcrumbs."""
    content = FRONTMATTER_RE.sub("", content)
    lines = content.splitlines()

    sections: list[tuple[list[str], str]] = []
    stack: list[tuple[int, str]] = []  # (level, heading text)
    path: list[str] = []
    body: list[str] = []
    in_fence = False

    def flush() -> None:
        text = "\n".join(body).strip()
        if text:
            sections.append((list(path), text))

    for line in lines:
        if FENCE_RE.match(line):
            in_fence = not in_fence
            body.append(line)
            continue
        m = None if in_fence else HEADING_RE.match(line)
        if m:
            flush()
            body = []
            level, htext = len(m.group(1)), m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, htext))
            path = [t for _, t in stack]
        else:
            body.append(line)
    flush()

    chunks: list[Chunk] = []
    for sec_path, text in sections:
        for piece in _split_to_size(text, max_tokens):
            chunks.append(
                Chunk(
                    index=len(chunks),
                    heading_path=sec_path,
                    text=piece,
                    tokens_est=_est_tokens(piece),
                )
            )
    return chunks
