"""Tests for the structure-aware markdown chunker."""

from __future__ import annotations

from trovex.chunking import chunk_markdown


def test_headings_become_chunks_with_breadcrumb():
    doc = (
        "---\ntitle: x\n---\n"
        "# Auth\n\nintro line\n\n"
        "## JWT\n\njwt body here\n\n"
        "## Rotation\n\nrotation body\n"
    )
    chunks = chunk_markdown(doc)
    paths = [c.heading_path for c in chunks]
    assert paths == [["Auth"], ["Auth", "JWT"], ["Auth", "Rotation"]]
    # frontmatter stripped (no 'title: x' leaking into a chunk)
    assert all("title: x" not in c.text for c in chunks)
    # prefix-fusion breadcrumb
    jwt = chunks[1]
    assert jwt.breadcrumb("Auth.md") == "Auth.md > Auth > JWT"
    assert jwt.embed_text("Auth.md").startswith("Auth.md > Auth > JWT\n\n")
    assert "jwt body here" in jwt.embed_text("Auth.md")


def test_fenced_code_hashes_are_not_headings():
    doc = "# H\n\nbefore\n\n```\n# not a heading\nx = 1\n```\n\nafter\n"
    chunks = chunk_markdown(doc)
    assert chunks, "expected at least one chunk"
    assert all(c.heading_path == ["H"] for c in chunks)
    assert any("not a heading" in c.text for c in chunks)


def test_oversized_section_is_split_keeping_breadcrumb():
    para = "word " * 100  # ~125 est-tokens
    doc = "# Big\n\n" + "\n\n".join([para] * 6)  # ~750 tokens under one heading
    chunks = chunk_markdown(doc, max_tokens=200)
    assert len(chunks) >= 2, "oversized section should split"
    assert all(c.heading_path == ["Big"] for c in chunks)
    assert all(c.tokens_est <= 260 for c in chunks)  # each window near the cap


def test_preamble_before_first_heading():
    doc = "some intro\n\nmore intro\n\n# First\n\nbody\n"
    chunks = chunk_markdown(doc)
    assert chunks[0].heading_path == []
    assert "some intro" in chunks[0].text
    assert chunks[1].heading_path == ["First"]
