#!/usr/bin/env python3
"""Emit brand-system comparison OG cards (1200x630) for the vs/ pages.
Honest + fair: each card credits where the other tool is the right choice
(matches the page's own "when to use X" section). Real ~60% only.
Writes growth/assets/_src/og-vs-<slug>.svg for each card. Render with resvg.
"""
import html, os

OUT = os.path.join(os.path.dirname(__file__), "..", "_src")

# slug, title-right (after "trovex vs "), left column header, 3 rows (left, right, optional green sub), footer
CARDS = [
    ("context-hub", "context-hub (CTX)", "chunk-retrieval server (CTX)", [
        ("a ranked list of chunks", "one canonical doc", None),
        ("you pick from candidates", "one current answer, path:line", None),
        ("no freshness signal", "★ canonical · ✗ stale markers", "~60% fewer tokens per lookup"),
    ], "a general retrieval server fits broad search. trovex answers which repo doc is current."),
    ("cursor-memory", "Cursor memory", "Cursor memory / rules", [
        ("editor-locked rules", "portable across MCP clients", None),
        ("Cursor only", "Claude Code, Cursor, Windsurf, Zed…", None),
        ("hand-written rules", "indexed docs + freshness", "~60% fewer tokens per lookup"),
    ], "Cursor memory is great inside Cursor. trovex travels with your repo."),
    ("mem0", "mem0", "mem0", [
        ("remembers conversations", "serves your repo's docs", None),
        ("user / agent memory", "one canonical doc per query", None),
        ("general memory layer", "repo SSOT + freshness marker", "~60% fewer tokens per lookup"),
    ], "mem0 is great for conversational memory. trovex for your repo's canonical docs."),
    ("vector-db-rag", "a vector-DB RAG setup", "vector-DB RAG (DIY)", [
        ("a pipeline you build", "turnkey, runs on your machine", None),
        ("embed + chunk + rank yourself", "index once, ask, get one doc", None),
        ("returns a set of chunks", "one canonical answer + freshness", "~60% fewer tokens per lookup"),
    ], "a custom RAG stack fits bespoke needs. trovex for repo docs out of the box."),
]

ROW_Y = [246, 318, 390]

def esc(s):
    return html.escape(s, quote=False)

def card_svg(slug, title_right, left_head, rows, footer):
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="trovex vs {esc(title_right)}. {esc(footer)}">',
        '  <defs><style>',
        "    .sans { font-family: 'Fira Sans','Segoe UI',system-ui,-apple-system,sans-serif; }",
        "    .mono { font-family: 'Fira Code','SF Mono',ui-monospace,monospace; }",
        '  </style></defs>',
        '  <rect width="1200" height="630" fill="#0a0e17"/>',
        '  <rect x="0" y="0" width="1200" height="6" fill="#22c55e"/>',
        f'  <text class="sans" x="64" y="88" font-size="42" font-weight="700" fill="#e6edf3">trovex <tspan fill="#7c8798">vs</tspan> {esc(title_right)}</text>',
        f'  <text class="mono" x="96" y="168" font-size="24" font-weight="600" fill="#8b97a8">{esc(left_head)}</text>',
        '  <text class="mono" x="664" y="168" font-size="24" font-weight="600" fill="#22c55e">trovex</text>',
        '  <line x1="636" y1="140" x2="636" y2="500" stroke="#1c2430" stroke-width="2"/>',
        '  <line x1="64" y1="186" x2="1136" y2="186" stroke="#1c2430" stroke-width="1.5"/>',
        '  <g class="sans" font-size="25">',
    ]
    for (left, right, sub), y in zip(rows, ROW_Y):
        parts.append(f'    <text x="96" y="{y}" fill="#9aa6b8">{esc(left)}</text>')
        parts.append(f'    <text x="664" y="{y}" fill="#e6edf3">{esc(right)}</text>')
        if sub:
            parts.append(f'    <text x="664" y="{y+32}" font-size="22" font-weight="600" fill="#22c55e">{esc(sub)}</text>')
    parts += [
        '  </g>',
        '  <line x1="64" y1="524" x2="1136" y2="524" stroke="#1c2430" stroke-width="1.5"/>',
        f'  <text class="sans" x="64" y="572" font-size="22" fill="#7c8798">{esc(footer)}</text>',
        '  <text class="mono" x="1136" y="572" font-size="20" fill="#5a6577" text-anchor="end">trovex.dev</text>',
        '</svg>',
    ]
    return "\n".join(parts) + "\n"

def main():
    for slug, title_right, left_head, rows, footer in CARDS:
        path = os.path.join(OUT, f"og-vs-{slug}.svg")
        with open(path, "w") as f:
            f.write(card_svg(slug, title_right, left_head, rows, footer))
        print(f"wrote {path}")

if __name__ == "__main__":
    main()
