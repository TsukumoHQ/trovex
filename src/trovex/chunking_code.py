"""cAST-style structure-aware chunking for source code (arXiv:2506.15655).

Port of yilinjz/astchunk's greedy AST merge/split onto py-tree-sitter +
tree-sitter-language-pack, mirroring chunking.py's markdown chunker: parse,
greedily merge adjacent siblings up to a token budget, recurse into any
single node that alone exceeds the budget, and fall back to a line-window
split for a leaf node that still doesn't fit. Every byte of the region being
chunked ends up in exactly one chunk (or is dropped only if pure whitespace)
— nothing between merged siblings (comments, blank lines) is lost, since
buffers are contiguous byte spans of the source, not concatenations of node
texts.

Breadcrumb = enclosing symbol path (e.g. ["class Bar", "def baz"]), fused
into embed_text exactly like chunk_markdown's heading breadcrumb.
"""

from __future__ import annotations

from functools import cache

from .chunking import DEFAULT_MAX_TOKENS, Chunk, _split_to_size

# Extension -> tree-sitter-language-pack grammar name. v1 languages picked to
# match what the fleet actually indexes (trovex/yoru = Python, WRAI.TH/agentd
# = Go/Rust, dashboards = TS/TSX) — see design doc for 9299f37d.
EXTENSION_LANGUAGES: dict[str, str] = {
    "py": "python",
    "go": "go",
    "rs": "rust",
    "ts": "typescript",
    "tsx": "tsx",
}

CODE_EXTENSIONS = frozenset(EXTENSION_LANGUAGES)

# Definition-like node types get a short kind prefix in the breadcrumb so
# "class Bar" reads distinctly from a bare identifier; anything else falls
# back to its bare name.
_DEF_PREFIX: dict[str, str] = {
    "function_definition": "def",
    "function_declaration": "func",
    "function_item": "fn",
    "method_definition": "method",
    "method_declaration": "method",
    "class_definition": "class",
    "class_declaration": "class",
    "struct_item": "struct",
    "enum_item": "enum",
    "trait_item": "trait",
    "impl_item": "impl",
    "interface_declaration": "interface",
    "type_declaration": "type",
    "type_spec": "type",
}


@cache
def _get_parser(lang: str):
    from tree_sitter_language_pack import get_parser

    return get_parser(lang)


def _tokens(text: str) -> int:
    from .tokens import count_tokens

    return count_tokens(text)


def _node_label(node) -> str | None:
    name_node = node.child_by_field_name("name") or node.child_by_field_name("type")
    if name_node is None:
        return None
    text = name_node.text.decode("utf-8", errors="replace")
    prefix = _DEF_PREFIX.get(node.type)
    return f"{prefix} {text}" if prefix else text


def _merge_siblings(
    nodes: list,
    data: bytes,
    max_tokens: int,
    path: list[str],
    chunks: list[Chunk],
    start: int,
    end: int,
) -> None:
    def emit(a: int, b: int) -> None:
        if b <= a:
            return
        text = data[a:b].decode("utf-8", errors="replace")
        if text.strip():
            chunks.append(
                Chunk(index=len(chunks), heading_path=list(path), text=text, tokens_est=_tokens(text))
            )

    buf_start = start
    for node in nodes:
        candidate = data[buf_start : node.end_byte].decode("utf-8", errors="replace")
        if _tokens(candidate) <= max_tokens:
            continue  # keep growing the implicit buffer through this node
        emit(buf_start, node.start_byte)
        buf_start = node.start_byte
        solo = data[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
        if _tokens(solo) <= max_tokens:
            continue  # node alone fits; buffer restarts at this node's start
        label = _node_label(node)
        sub_path = path + [label] if label else path
        if node.named_children:
            _merge_siblings(
                list(node.named_children), data, max_tokens, sub_path, chunks, node.start_byte, node.end_byte
            )
        else:
            for piece in _split_to_size(solo, max_tokens):
                chunks.append(
                    Chunk(index=len(chunks), heading_path=list(sub_path), text=piece, tokens_est=_tokens(piece))
                )
        buf_start = node.end_byte
    emit(buf_start, end)


def chunk_code(content: str, lang: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> list[Chunk]:
    """Split source code into structure-aware chunks along AST boundaries.

    `lang` is a tree-sitter-language-pack grammar name (see
    EXTENSION_LANGUAGES for the extension mapping). Falls back to treating
    the whole file as one chunk if the grammar can't parse it into any named
    top-level nodes (e.g. an empty or pathological file) — never raises on
    parse trouble."""
    parser = _get_parser(lang)
    data = content.encode("utf-8", errors="replace")
    tree = parser.parse(data)
    chunks: list[Chunk] = []
    _merge_siblings(list(tree.root_node.named_children), data, max_tokens, [], chunks, 0, len(data))
    return chunks
