#!/usr/bin/env python3
"""Emit brand-system AEO OG cards (1200x630) for the answers/ pages.
Each card = the real question + trovex's honest one-line answer + the ~60%.
Writes growth/assets/_src/og-answer-<slug>.svg. Render with resvg.
"""
import html, os

OUT = os.path.join(os.path.dirname(__file__), "..", "_src")

# slug, question lines (<=2), answer lines (<=2)
CARDS = [
    ("bigger-context-window-rereading",
     ["Does a bigger context window", "make rereading docs cheaper?"],
     ["No — the reread is paid every session, every agent.", "trovex serves one current doc per query instead."]),
    ("canonical-context-for-agents",
     ["What is canonical context", "for coding agents?"],
     ["The single current doc that answers a query —", "a path:line pointer with a freshness marker."]),
    ("reduce-agent-token-costs",
     ["How do I reduce the token cost", "of a coding agent's context?"],
     ["Serve one canonical doc per query instead of", "rereading the repo to guess which file is current."]),
    ("shared-source-of-truth-multiple-agents",
     ["How do I keep multiple agents", "working from the same docs?"],
     ["One shared trovex store — write once, and every", "agent and teammate reads the same canonical answer."]),
    ("stop-agent-rereading-docs",
     ["How do I stop my agent rereading", "the same files every session?"],
     ["Index once; trovex returns the one current", "section per query, not the whole repo."]),
]

def esc(s):
    return html.escape(s, quote=False)

def card_svg(slug, q, a):
    q_lines = "".join(
        f'  <text class="sans" x="64" y="{210 + i*64}" font-size="48" font-weight="700" fill="#e6edf3">{esc(line)}</text>\n'
        for i, line in enumerate(q))
    a_lines = "".join(
        f'  <text class="sans" x="64" y="{406 + i*44}" font-size="27" font-weight="400" fill="#9aa6b8">{esc(line)}</text>\n'
        for i, line in enumerate(a))
    aria = esc(" ".join(q) + " " + " ".join(a))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="{aria}">
  <defs><style>
    .sans {{ font-family: 'Fira Sans','Segoe UI',system-ui,-apple-system,sans-serif; }}
    .mono {{ font-family: 'Fira Code','SF Mono',ui-monospace,monospace; }}
  </style></defs>
  <rect width="1200" height="630" fill="#0a0e17"/>
  <rect x="0" y="0" width="1200" height="6" fill="#22c55e"/>

  <g>
    <rect x="64" y="92" width="132" height="44" rx="22" fill="#0f1a14" stroke="#22c55e" stroke-width="1.5"/>
    <circle cx="90" cy="114" r="6" fill="#22c55e"/>
    <text class="mono" x="108" y="121" font-size="20" fill="#cdd6e2">answer</text>
  </g>

{q_lines}  <line x1="64" y1="356" x2="1136" y2="356" stroke="#1c2430" stroke-width="2"/>
{a_lines}
  <g>
    <rect x="64" y="520" width="320" height="56" rx="12" fill="#0f1a14" stroke="#22c55e" stroke-width="1.5"/>
    <text class="sans" x="224" y="556" font-size="26" font-weight="700" fill="#22c55e" text-anchor="middle">~60% fewer tokens</text>
  </g>
  <text class="mono" x="1136" y="556" font-size="21" fill="#7c8798" text-anchor="end">trovex.dev · private beta</text>
</svg>
'''

def main():
    for slug, q, a in CARDS:
        path = os.path.join(OUT, f"og-answer-{slug}.svg")
        with open(path, "w") as f:
            f.write(card_svg(slug, q, a))
        print(f"wrote {path}")

if __name__ == "__main__":
    main()
