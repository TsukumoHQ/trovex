"""Markdown → HTML for the doc reader, via mistune (GFM) + Pygments highlighting.

Replaces the former hand-rolled regex renderer. Returns (html, toc) where toc is
a list of {level, text, slug} for the sidebar. Headings render one level down
(# → h2) since the page already owns the h1. Inline/raw HTML is escaped
(escape=True), so agent-authored content has no injection surface.

GFM via plugins: tables, task lists, strikethrough, footnotes, bare-URL links.
Fenced code is syntax-highlighted server-side with Pygments; expose PYGMENTS_CSS
for the page to embed once.
"""

from __future__ import annotations

import html as _html
import re

import mistune
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

_TAG = re.compile(r"<[^>]+>")
_PLUGINS = ["table", "strikethrough", "task_lists", "footnotes", "url"]

# One shared formatter → one CSS blob. 'monokai' reads well on both themes since
# code blocks carry their own dark surface.
_FORMATTER = HtmlFormatter(style="monokai", cssclass="highlight")
PYGMENTS_CSS = _FORMATTER.get_style_defs(".highlight")


def slugify(text: str, seen: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-") or "section"
    slug, i = base, 2
    while slug in seen:
        slug = f"{base}-{i}"
        i += 1
    seen.add(slug)
    return slug


class _DocRenderer(mistune.HTMLRenderer):
    """HTML renderer that shifts headings down one level, collects a TOC, and
    syntax-highlights fenced code. Stateful (toc/seen) → one instance per call."""

    def __init__(self) -> None:
        super().__init__(escape=True)
        self.toc: list[dict] = []
        self._seen: set[str] = set()

    def heading(self, text: str, level: int, **attrs) -> str:
        plain = _TAG.sub("", text).strip()
        slug = slugify(plain, self._seen)
        self.toc.append({"level": level, "text": plain, "slug": slug})
        shifted = min(level + 1, 6)
        return f'<h{shifted} id="{slug}">{text}</h{shifted}>\n'

    def block_code(self, code: str, info: str | None = None) -> str:
        lang = (info or "").strip().split()[0] if info else ""
        if lang:
            try:
                return highlight(code, get_lexer_by_name(lang, stripall=False), _FORMATTER)
            except ClassNotFound:
                pass
        return f'<pre class="md-code"><code>{_html.escape(code)}</code></pre>'


def render_markdown(content: str) -> tuple[str, list[dict]]:
    renderer = _DocRenderer()
    md = mistune.create_markdown(renderer=renderer, plugins=_PLUGINS)
    return md(content or ""), renderer.toc
