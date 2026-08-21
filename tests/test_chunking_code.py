"""Tests for the cAST-style structure-aware code chunker."""

from __future__ import annotations

from trovex.chunking_code import CODE_EXTENSIONS, EXTENSION_LANGUAGES, chunk_code


def test_python_top_level_defs_become_chunks_with_breadcrumb():
    src = (
        "import os\n\n\n"
        "def foo():\n    return 1\n\n\n"
        "class Bar:\n    def baz(self):\n        return 2\n"
    )
    chunks = chunk_code(src, "python", max_tokens=5)
    paths = [c.heading_path for c in chunks]
    # each def is small enough to stand alone once the budget forces a split;
    # the class recurses so its method carries a two-level breadcrumb.
    assert ["def foo"] in paths
    # tree-sitter-python has one node type for both funcs and methods
    assert ["class Bar", "def baz"] in paths


def test_small_file_merges_into_one_chunk():
    src = "def foo():\n    return 1\n\n\ndef bar():\n    return 2\n"
    chunks = chunk_code(src, "python", max_tokens=450)
    assert len(chunks) == 1
    assert "def foo" in chunks[0].text
    assert "def bar" in chunks[0].text


def test_nothing_between_merged_siblings_is_dropped():
    src = "x = 1\n# a comment between statements\ny = 2\n"
    chunks = chunk_code(src, "python", max_tokens=450)
    joined = "\n".join(c.text for c in chunks)
    assert "a comment between statements" in joined
    assert "x = 1" in joined and "y = 2" in joined


def test_oversized_leaf_falls_back_to_line_split():
    body = "    " + " ".join(["word"] * 400)
    src = f"def huge():\n{body}\n"
    chunks = chunk_code(src, "python", max_tokens=50)
    assert len(chunks) >= 2
    assert all(c.tokens_est <= 100 for c in chunks)  # near the cap, not unbounded


def test_go_function_and_type_breadcrumbs():
    src = "package main\n\nfunc Foo() {}\n\ntype Bar struct{}\n"
    chunks = chunk_code(src, "go", max_tokens=1)
    paths = [c.heading_path for c in chunks]
    assert ["func Foo"] in paths
    assert any(p and p[0] == "type Bar" for p in paths)


def test_rust_impl_block_labels_methods_by_type_field():
    src = "struct Bar;\n\nimpl Bar {\n    fn baz(&self) {}\n}\n"
    chunks = chunk_code(src, "rust", max_tokens=1)
    paths = [c.heading_path for c in chunks]
    assert ["impl Bar", "fn baz"] in paths


def test_typescript_class_and_interface():
    src = "class Bar {\n  baz() {}\n}\n\ninterface Qux {}\n"
    chunks = chunk_code(src, "typescript", max_tokens=1)
    paths = [c.heading_path for c in chunks]
    assert any(p and p[0] == "class Bar" for p in paths)
    assert ["interface Qux"] in paths


def test_extension_language_map_covers_v1_langs():
    assert set(EXTENSION_LANGUAGES) == {"py", "go", "rs", "ts", "tsx"}
    assert frozenset(EXTENSION_LANGUAGES) == CODE_EXTENSIONS


def test_empty_file_yields_no_chunks():
    assert chunk_code("", "python") == []


def test_whitespace_only_file_yields_no_chunks():
    assert chunk_code("\n\n   \n", "python") == []
