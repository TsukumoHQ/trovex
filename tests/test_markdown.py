"""Tests for the XSS-safe markdown renderer behind the doc reader."""

from __future__ import annotations

from trovex.markdown import render_markdown


def test_raw_html_is_escaped_not_executed():
    html, _ = render_markdown("hello <script>alert(1)</script> world")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_headings_get_anchors_and_toc():
    html, toc = render_markdown("# Top\n\nbody\n\n## Sub section\n\nmore")
    assert '<h2 id="top">Top</h2>' in html
    assert '<h3 id="sub-section">Sub section</h3>' in html
    assert toc == [
        {"level": 1, "text": "Top", "slug": "top"},
        {"level": 2, "text": "Sub section", "slug": "sub-section"},
    ]


def test_duplicate_headings_get_unique_slugs():
    _, toc = render_markdown("## Notes\n\na\n\n## Notes\n\nb")
    assert [t["slug"] for t in toc] == ["notes", "notes-2"]


def test_fenced_code_block_is_escaped_with_lang():
    html, _ = render_markdown("```python\nx = 1 < 2\n```")
    assert 'class="highlight"' in html   # pygments-highlighted block
    assert "&lt;" in html                 # the < is escaped, never raw markup
    assert "<script" not in html


def test_inline_formatting():
    html, _ = render_markdown("a **bold** and `code` and *em* here")
    assert "<strong>bold</strong>" in html
    assert "<code>code</code>" in html
    assert "<em>em</em>" in html


def test_safe_links_kept_unsafe_dropped():
    ok, _ = render_markdown("see [docs](https://example.com/x)")
    assert '<a href="https://example.com/x" rel="noopener noreferrer">docs</a>' in ok

    bad, _ = render_markdown("click [here](javascript:alert(1))")
    assert "javascript:" not in bad        # no script-execution path
    assert 'href="javascript' not in bad   # protocol neutralised
    assert "here" in bad                    # link text preserved


def test_lists_render():
    ul, _ = render_markdown("- one\n- two")
    assert "".join(ul.split()) == "<ul><li>one</li><li>two</li></ul>"
    ol, _ = render_markdown("1. first\n2. second")
    assert "".join(ol.split()) == "<ol><li>first</li><li>second</li></ol>"
