#!/usr/bin/env python3
"""Composite agency hero CONCEPT mocks: gpt-image backdrop + crisp overlaid type.
Name-agnostic (placeholder wordmark). Type here is indicative (Fira stand-in for a
grotesk) — final type locks with the name. Writes growth/assets/_src/agency/mock-<slug>.svg.
Render with resvg; backdrops live alongside as bg-<slug>.png.
"""
import html, os

OUT = os.path.join(os.path.dirname(__file__), "..", "_src", "agency")

# slug, bg file, scrim(dir,opacity), ink (text), accent, wordmark, headline lines, tagline
VIBES = [
    ("concrete-acid", "bg-concrete-acid.png", "left", "#f4f2ec", "#c8ff00",
     ["we make", "agents", "behave."], "studio — engineering for teams shipping AI"),
    ("editorial-void", "bg-editorial-void.png", "none", "#0e0e0e", "#ff5a1f",
     ["systems for", "teams", "shipping AI."], "studio — products that behave under load"),
    ("signal", "bg-signal.png", "left", "#ececec", "#ff3b1d",
     ["engineering", "for the", "agent era."], "studio — the systems behind AI products"),
]

def esc(s): return html.escape(s, quote=False)

def mock_svg(slug, bg, scrim, ink, accent, words, tagline):
    W, H = 1536, 1024
    scrim_el = ""
    if scrim == "left":
        scrim_el = ('  <defs><linearGradient id="s" x1="0" y1="0" x2="1" y2="0">'
                    '<stop offset="0" stop-color="#000" stop-opacity="0.55"/>'
                    '<stop offset="0.7" stop-color="#000" stop-opacity="0.12"/>'
                    '<stop offset="1" stop-color="#000" stop-opacity="0"/></linearGradient></defs>\n'
                    f'  <rect width="{W}" height="{H}" fill="url(#s)"/>\n')
    head = "".join(
        f'  <text class="d" x="96" y="{430 + i*150}" font-size="150" font-weight="800" '
        f'letter-spacing="-0.03em" fill="{ink}">{esc(w)}</text>\n'
        for i, w in enumerate(words))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Agency concept mock {esc(slug)}: {esc(' '.join(words))}">
  <defs><style>
    .d {{ font-family: 'Fira Sans','Helvetica Neue',Arial,sans-serif; }}
    .m {{ font-family: 'Fira Code','SF Mono',ui-monospace,monospace; }}
  </style></defs>
  <rect width="{W}" height="{H}" fill="#101010"/>
  <image href="{bg}" x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="xMidYMid slice"/>
{scrim_el}  <!-- top bar: placeholder wordmark + index + nav -->
  <rect x="96" y="84" width="20" height="20" fill="{accent}"/>
  <text class="m" x="128" y="100" font-size="22" font-weight="600" fill="{ink}">studio</text>
  <text class="m" x="232" y="100" font-size="22" fill="{ink}" opacity="0.6">[ working name ]</text>
  <text class="m" x="{W-96}" y="100" font-size="22" fill="{ink}" opacity="0.8" text-anchor="end">work · approach · contact</text>
  <text class="m" x="96" y="{H-150}" font-size="22" fill="{accent}">01 — 04</text>

{head}  <!-- accent rule + tagline -->
  <rect x="100" y="{430 + len(words)*150 - 40}" width="120" height="10" fill="{accent}"/>
  <text class="m" x="96" y="{H-96}" font-size="24" fill="{ink}" opacity="0.85">{esc(tagline)}</text>
  <text class="m" x="{W-96}" y="{H-96}" font-size="22" fill="{ink}" opacity="0.5" text-anchor="end">concept — type indicative</text>
</svg>
'''

def main():
    for slug, bg, scrim, ink, accent, words, tagline in VIBES:
        p = os.path.join(OUT, f"mock-{slug}.svg")
        with open(p, "w") as f:
            f.write(mock_svg(slug, bg, scrim, ink, accent, words, tagline))
        print("wrote", p)

if __name__ == "__main__":
    main()
