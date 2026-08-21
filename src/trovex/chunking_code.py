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

# Generated/minified code with no real symbol structure (e.g. one giant chained
# expression) can blow the AST walk up to thousands of near-useless
# micro-chunks; past this many chunks for one file, fall back to a flat
# line-window split instead.
_MAX_CHUNKS_PER_FILE = 300

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


def _line_range(data: bytes, a: int, b: int) -> str:
    """1-indexed line:column label for a byte span with no symbol breadcrumb
    (module-level top scope, or nested inside an unnamed node like a bare
    expression statement). Without this, every such chunk shares the same
    empty heading_path and store.section_text's small-to-big join glues them
    ALL back into one giant "section" — a 396-token chunk expanding to the
    whole file's worth of unrelated top-level statements.

    Column (not just line) matters: minified code is characteristically ONE
    giant line, so a line-only label would collapse every chunk in the file
    back onto the same "L1" and reintroduce the exact bug this exists to
    fix. `a` (the chunk's start byte) is strictly increasing across the
    whole walk — buffers are non-overlapping, emitted in byte order — so
    line:column is always unique."""
    line_start = data.rfind(b"\n", 0, a) + 1  # -1 -> 0 when there's no prior newline
    line = data.count(b"\n", 0, a) + 1
    col = a - line_start + 1
    end_line = data.count(b"\n", 0, max(b - 1, a)) + 1
    return f"L{line}:{col}" if line == end_line else f"L{line}:{col}-L{end_line}"


def _node_label(node) -> str | None:
    name_node = node.child_by_field_name("name") or node.child_by_field_name("type")
    if name_node is None:
        return None
    text = name_node.text.decode("utf-8", errors="replace")
    prefix = _DEF_PREFIX.get(node.type)
    return f"{prefix} {text}" if prefix else text


class _Frame:
    """One level of the walk: the sibling list being merged, our position in
    it, the implicit buffer's start byte, the breadcrumb path, and the byte
    this level ends at."""

    __slots__ = ("buf_start", "end", "i", "nodes", "path")

    def __init__(self, nodes: list, buf_start: int, path: list[str], end: int) -> None:
        self.nodes = nodes
        self.i = 0
        self.buf_start = buf_start
        self.path = path
        self.end = end


def _merge_siblings(
    nodes: list,
    data: bytes,
    max_tokens: int,
    path: list[str],
    chunks: list[Chunk],
    start: int,
    end: int,
) -> None:
    """Walk the sibling tree with an explicit stack, not Python call
    recursion: generated or minified code can nest AST levels well past
    sys.getrecursionlimit() (e.g. a long chained binary expression), and a
    recursive walk would blow the stack (RecursionError) and abort the whole
    file's chunking — this must never raise on parse trouble."""

    def emit(a: int, b: int, emit_path: list[str]) -> None:
        if b <= a:
            return
        text = data[a:b].decode("utf-8", errors="replace")
        if text.strip():
            out_path = list(emit_path) if emit_path else [_line_range(data, a, b)]
            chunks.append(
                Chunk(index=len(chunks), heading_path=out_path, text=text, tokens_est=_tokens(text))
            )

    stack = [_Frame(nodes, start, path, end)]
    while stack:
        frame = stack[-1]
        if frame.i >= len(frame.nodes):
            emit(frame.buf_start, frame.end, frame.path)
            stack.pop()
            continue

        node = frame.nodes[frame.i]
        candidate = data[frame.buf_start : node.end_byte].decode("utf-8", errors="replace")
        if _tokens(candidate) <= max_tokens:
            frame.i += 1
            continue  # keep growing the implicit buffer through this node

        emit(frame.buf_start, node.start_byte, frame.path)
        frame.buf_start = node.start_byte
        solo = data[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
        if _tokens(solo) <= max_tokens:
            frame.i += 1
            continue  # node alone fits; buffer restarts at this node's start

        label = _node_label(node)
        sub_path = frame.path + [label] if label else frame.path
        frame.buf_start = node.end_byte
        frame.i += 1
        if node.named_children:
            stack.append(_Frame(list(node.named_children), node.start_byte, sub_path, node.end_byte))
        elif sub_path:
            # Labeled node (e.g. one oversized function/class body): every
            # piece keeps the SAME breadcrumb on purpose, so section_text's
            # small-to-big join reconstructs the whole symbol from its parts.
            # This is the ONLY source of duplicate heading_paths chunk_code
            # ever produces (an oversized node's own recursed frame, above,
            # hits the identical case via its own multiple buf_start emits
            # sharing frame.path) -- intra-symbol duplication is BY DESIGN,
            # not a regression; see test_ratchet_distinguishes_sibling_symbols
            # for the invariant that actually matters: distinct symbols never
            # share a path.
            for piece in _split_to_size(solo, max_tokens):
                chunks.append(
                    Chunk(index=len(chunks), heading_path=list(sub_path), text=piece, tokens_est=_tokens(piece))
                )
        else:
            # No symbol breadcrumb at all (e.g. a bare top-level expression
            # statement) -- each piece needs its OWN path, not a shared empty
            # one, or section_text glues unrelated pieces back together.
            offset = node.start_byte
            for piece in _split_to_size(solo, max_tokens):
                # Not clamped to node.end_byte: _split_to_size strips/rejoins
                # text so cumulative piece length only approximates the real
                # span, and clamping risks two pieces landing on the same
                # offset at the boundary — offset must stay strictly
                # increasing (piece is always non-empty) for uniqueness.
                end = offset + len(piece.encode("utf-8"))
                chunks.append(
                    Chunk(
                        index=len(chunks),
                        heading_path=[_line_range(data, offset, end)],
                        text=piece,
                        tokens_est=_tokens(piece),
                    )
                )
                offset = end


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
    if len(chunks) > _MAX_CHUNKS_PER_FILE:
        return _flat_line_split(content, max_tokens)
    return chunks


def _flat_line_split(content: str, max_tokens: int) -> list[Chunk]:
    """Fallback for a degenerate AST (generated/minified code with no real
    symbol structure) that would otherwise explode into thousands of
    micro-chunks: a flat paragraph/line-window split, each piece its own
    distinct section so section_text never glues unrelated pieces together.

    Column (not just line), same reasoning as `_line_range`: minified code is
    characteristically one giant line, so a line-only label would collapse
    every piece back onto "L1" and reintroduce the union bug this exists to
    fix. `offset` is strictly increasing across pieces, so line:column is
    always unique even when every piece shares line 1."""
    out: list[Chunk] = []
    offset = 0
    for i, piece in enumerate(_split_to_size(content, max_tokens)):
        end = offset + len(piece)  # not clamped to len(content) -- see _line_range's leaf-split note
        line_start = content.rfind("\n", 0, offset) + 1
        start_line = content.count("\n", 0, offset) + 1
        col = offset - line_start + 1
        end_line = content.count("\n", 0, max(end - 1, offset)) + 1
        label = f"L{start_line}:{col}" if start_line == end_line else f"L{start_line}:{col}-L{end_line}"
        out.append(Chunk(index=i, heading_path=[label], text=piece, tokens_est=_tokens(piece)))
        offset = end
    return out
