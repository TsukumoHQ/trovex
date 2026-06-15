#!/usr/bin/env python3
"""Emit tailored brand-system OG cards (1200x630) for the for/<agent> pages.
Each card names the agent + its specific MCP wiring hook + the real ~60%.
Private-beta framing, no open-install copy. Writes growth/assets/_src/og-for-<slug>.svg.
Render with resvg.
"""
import html, os

OUT = os.path.join(os.path.dirname(__file__), "..", "_src")

# slug, agent name, mechanism subline, "connect" chip (mono), wiring note
CARDS = [
    ("claude-code", "Claude Code",
     "one canonical doc per query — not a CLAUDE.md reread of the repo",
     "point Claude Code at trovex over MCP"),
    ("cursor", "Cursor",
     "one canonical doc per query — not a whole-repo reread",
     "add to  .cursor/mcp.json"),
    ("windsurf", "Windsurf",
     "one canonical doc per query — not a whole-repo reread",
     "add to  mcp_config.json"),
    ("cline", "Cline",
     "one canonical doc per query — not a whole-repo reread",
     "add a remote MCP server in the MCP Servers panel"),
]

def esc(s):
    return html.escape(s, quote=False)

def card_svg(slug, agent, sub, connect):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="trovex for {esc(agent)}. {esc(sub)}. About 60 percent fewer tokens per lookup. {esc(connect)}. Now in private beta.">
  <defs><style>
    .sans {{ font-family: 'Fira Sans','Segoe UI',system-ui,-apple-system,sans-serif; }}
    .mono {{ font-family: 'Fira Code','SF Mono',ui-monospace,monospace; }}
  </style></defs>
  <rect width="1200" height="630" fill="#0a0e17"/>
  <rect x="0" y="0" width="1200" height="6" fill="#22c55e"/>

  <!-- via MCP pill -->
  <g>
    <rect x="64" y="92" width="150" height="44" rx="22" fill="#0f1a14" stroke="#22c55e" stroke-width="1.5"/>
    <circle cx="90" cy="114" r="6" fill="#22c55e"/>
    <text class="mono" x="108" y="121" font-size="20" fill="#cdd6e2">via MCP</text>
  </g>

  <text class="sans" x="64" y="240" font-size="62" font-weight="700" fill="#e6edf3">trovex for <tspan fill="#22c55e">{esc(agent)}</tspan></text>
  <text class="sans" x="64" y="300" font-size="29" font-weight="400" fill="#9aa6b8">{esc(sub)}</text>

  <text class="sans" x="64" y="408" font-size="60" font-weight="700" fill="#e6edf3">~60%<tspan dx="20" font-size="38" font-weight="600" fill="#22c55e">fewer tokens per lookup</tspan></text>

  <!-- connect chip -->
  <rect x="64" y="452" width="1072" height="64" rx="12" fill="#0d1119" stroke="#1c2430" stroke-width="2"/>
  <text class="mono" x="88" y="492" font-size="24" fill="#7c8798">connect:  <tspan fill="#cdd6e2">{esc(connect)}</tspan></text>

  <line x1="64" y1="556" x2="1136" y2="556" stroke="#1c2430" stroke-width="1.5"/>
  <text class="mono" x="64" y="598" font-size="21" fill="#7c8798">trovex.dev · <tspan fill="#22c55e">now in private beta</tspan></text>
  <text class="sans" x="1136" y="598" font-size="20" fill="#5a6577" text-anchor="end">local-first · open core</text>
</svg>
'''

def main():
    for slug, agent, sub, connect in CARDS:
        path = os.path.join(OUT, f"og-for-{slug}.svg")
        with open(path, "w") as f:
            f.write(card_svg(slug, agent, sub, connect))
        print(f"wrote {path}")

if __name__ == "__main__":
    main()
