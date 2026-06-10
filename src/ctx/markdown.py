"""Tiny, XSS-safe Markdown → HTML renderer for the doc reader.

Dependency-free and safe by construction: every line is HTML-escaped *first*,
then a limited set of inline/block transforms inject our own trusted tags. Raw
HTML in the source can never reach the page (it's already escaped), so
agent-authored content renders without an injection surface.

Returns (html, toc) where toc is a list of {level, text, slug} for a
table-of-contents sidebar. Headings render one level down (# → h2) since the
page already owns the h1.
"""

from __future__ import annotations

import html as _html
import re

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
_FENCE = re.compile(r"^```")
_HR = re.compile(r"^(?:---+|\*\*\*+|___+)$")
_ULI = re.compile(r"^[-*+]\s+(.*)$")
_OLI = re.compile(r"^\d+\.\s+(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")

_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITAL = re.compile(r"(?<![\w*])[*_]([^*_]+)[*_](?![\w*])")
_SAFE_URL = re.compile(r"^(?:https?:|mailto:|/|#)")


def slugify(text: str, seen: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-") or "section"
    slug = base
    i = 2
    while slug in seen:
        slug = f"{base}-{i}"
        i += 1
    seen.add(slug)
    return slug


def _inline(escaped: str) -> str:
    """Inline transforms on already-escaped text — injects only trusted tags."""
    def link(m: re.Match) -> str:
        text, url = m.group(1), m.group(2)
        if not _SAFE_URL.match(url):
            return text
        return f'<a href="{url}" rel="noopener noreferrer">{text}</a>'

    escaped = _LINK.sub(link, escaped)
    escaped = _CODE.sub(r"<code>\1</code>", escaped)
    escaped = _BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = _ITAL.sub(r"<em>\1</em>", escaped)
    return escaped


def _toc_text(raw: str) -> str:
    return re.sub(r"[`*_]", "", raw).strip()


def render_markdown(content: str) -> tuple[str, list[dict]]:
    lines = content.splitlines()
    out: list[str] = []
    toc: list[dict] = []
    seen: set[str] = set()
    para: list[str] = []
    i, n = 0, len(lines)

    def flush_para() -> None:
        if para:
            out.append(f"<p>{_inline(_html.escape(' '.join(para)))}</p>")
            para.clear()

    while i < n:
        line = lines[i]

        if _FENCE.match(line):
            flush_para()
            lang = line[3:].strip()
            buf: list[str] = []
            i += 1
            while i < n and not _FENCE.match(lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            cls = f' data-lang="{_html.escape(lang)}"' if lang else ""
            out.append(
                f'<pre class="md-code"{cls}><code>'
                f'{_html.escape(chr(10).join(buf))}</code></pre>'
            )
            continue

        m = _HEADING.match(line)
        if m:
            flush_para()
            level = min(len(m.group(1)) + 1, 6)
            raw = m.group(2)
            slug = slugify(_toc_text(raw), seen)
            toc.append({"level": len(m.group(1)), "text": _toc_text(raw), "slug": slug})
            out.append(f'<h{level} id="{slug}">{_inline(_html.escape(raw))}</h{level}>')
            i += 1
            continue

        if _HR.match(line.strip()):
            flush_para()
            out.append('<hr class="md-hr">')
            i += 1
            continue

        if _ULI.match(line) or _OLI.match(line):
            flush_para()
            ordered = bool(_OLI.match(line))
            tag = "ol" if ordered else "ul"
            pat = _OLI if ordered else _ULI
            items: list[str] = []
            while i < n and pat.match(lines[i]):
                items.append(_inline(_html.escape(pat.match(lines[i]).group(1))))
                i += 1
            lis = "".join(f"<li>{it}</li>" for it in items)
            out.append(f"<{tag}>{lis}</{tag}>")
            continue

        if _QUOTE.match(line):
            flush_para()
            quoted: list[str] = []
            while i < n and _QUOTE.match(lines[i]):
                quoted.append(_QUOTE.match(lines[i]).group(1))
                i += 1
            out.append(
                f"<blockquote>{_inline(_html.escape(' '.join(quoted)))}</blockquote>"
            )
            continue

        if not line.strip():
            flush_para()
            i += 1
            continue

        para.append(line.strip())
        i += 1

    flush_para()
    return "\n".join(out), toc
