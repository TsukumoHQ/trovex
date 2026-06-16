#!/usr/bin/env python3
"""Emit tsukumo work/case-study cards (1200x750) in the acid/brutalist system.
Tokens: ink #121212 / bone #f3f1ea / concrete / acid #c8ff00; Archivo + Space Mono.
QUALITATIVE ONLY — no fabricated numbers. Copy is DRAFT for content-lead to approve.
Writes growth/assets/_src/agency/case-<slug>.svg. Render with resvg.
"""
import html, os

OUT = os.path.join(os.path.dirname(__file__), "..", "_src", "agency")

# slug, index, label, name, two body lines (qualitative), tag
CASES = [
    ("studio", "01", "case · studio", "our own stack",
     ["we run agents in production: WRAI.TH (orchestration),",
      "trovex (context), yoru (observability) — open source."],
     "the studio is the proof"),
    ("fund", "02", "case · under NDA", "a quant fund",
     ["agentic workflows in a live trading environment,",
      "built to the team's standards. anonymized."],
     "regulated · NDA"),
    ("cil", "03", "case · client", "CI-Léman",
     ["production AI inside an existing real-estate platform,",
      "shipped into the team's dev environment — not a demo."],
     "shipped, not a POC"),
]

def esc(s): return html.escape(s, quote=False)

def card(slug, idx, label, name, body, tag):
    W, H = 1200, 750
    body_el = "".join(
        f'  <text class="m" x="72" y="{498 + i*40}" font-size="26" fill="#f3f1ea" opacity="0.88">{esc(l)}</text>\n'
        for i, l in enumerate(body))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="tsukumo case study: {esc(name)}. {esc(' '.join(body))}">
  <defs><style>
    .d {{ font-family: 'Archivo','Inter Tight',system-ui,sans-serif; }}
    .m {{ font-family: 'Space Mono','Geist Mono',ui-monospace,monospace; }}
  </style></defs>
  <rect width="{W}" height="{H}" fill="#121212"/>
  <rect x="0" y="0" width="{W}" height="8" fill="#c8ff00"/>

  <text class="m" x="72" y="120" font-size="24" fill="#c8ff00">{esc(label)}</text>
  <text class="m" x="1128" y="120" font-size="60" font-weight="700" fill="#1b1a18" text-anchor="end">{esc(idx)}</text>

  <text class="d" x="68" y="320" font-size="116" font-weight="800" letter-spacing="-0.035em" fill="#f3f1ea">{esc(name)}</text>

  <rect x="74" y="430" width="110" height="9" fill="#c8ff00"/>
{body_el}
  <line x1="72" y1="628" x2="1128" y2="628" stroke="rgba(243,241,234,0.14)" stroke-width="1.5"/>
  <text class="m" x="72" y="676" font-size="22" fill="#f3f1ea" opacity="0.7">{esc(tag)}</text>
  <text class="m" x="1128" y="676" font-size="22" fill="#c8ff00" text-anchor="end">tsukumo</text>
</svg>
'''

def main():
    for slug, idx, label, name, body, tag in CASES:
        p = os.path.join(OUT, f"case-{slug}.svg")
        with open(p, "w") as f:
            f.write(card(slug, idx, label, name, body, tag))
        print("wrote", p)

if __name__ == "__main__":
    main()
