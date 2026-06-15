# Demo still — the aha (install → first query → savings)

`demo-aha.png` (1280×820) — a brand-styled terminal still showing the activation aha: index a
repo, run one query, and trovex prints the tokens saved. For the landing + later launch.

The terminal lines **mirror trovex's real CLI output** (`src/trovex/cli.py`, `src/trovex/search.py`):
`index` → "total tokens indexed" + "ask a question, see the tokens saved", then `search` →
`path:line  ● fresh Nd  ~Ntok` and `≈ N tokens saved this query · read 1 canonical doc … instead
of the top K · NN% less · estimate`. So the demo reads like an actual capture, not a mockup.

## Honesty
- Numbers reconcile and carry the tool's own **"estimate"** label: saved 440 = 720 − 280, 61% less
  (the real ~60% figure). No fabricated metrics, no Synergix, lowercase `trovex`.
- Footer reads `trovex.dev · now in private beta` (no open-install promise on public surfaces).
- For the strongest asset, swap in a **real screen capture / GIF** of the actual run before a public
  launch — the still matches the real output so it's a faithful stand-in until then.

Source: `growth/assets/_src/demo-aha.svg` (render with `growth/assets/_tools/render_svg.sh`).
