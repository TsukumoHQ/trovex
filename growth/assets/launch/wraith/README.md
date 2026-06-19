# wrai.th — launch gallery assets

Built from launch-lead's spec (`growth/launch/wraith-gallery-asset-spec.md`).
wrai.th's **own** brand — dark `#0a0c10` + emerald `#4ade80` + mono — **not**
tsukumo acid. Drafts: a human fires the launch. No fabricated metrics; repo URL
is the only place "Synergix" may appear.

## Done (in this folder)

| file | size | use |
|---|---|---|
| `slide-4-how-it-works.png` | 1270×760 | PH gallery slide 4 (3-step flow) |
| `slide-5-trust.png` | 1270×760 | PH gallery slide 5 (trust close) |
| `og-card.png` | 1200×630 | Show HN unfurl + X/LinkedIn/Slack repo shares |
| `thumbnail-240.png` | 240×240 | PH listing thumbnail |

All copy is verbatim from the spec's copy bank (facts true).

## Pending — real dashboard captures (slides 1–3)

Slides 1 (hook/thumbnail), 2 (coordination), 3 (memory) are **real screenshots**
of the live dashboard. See `CAPTURE-BRIEF.md` — a human grabs 3 PNGs from
http://localhost:8090/v2/, design composites them into matching 1270×760 frames.

## Regenerate the built slides

```
mkdir -p /tmp/og-deps && cd /tmp/og-deps && npm i satori @resvg/resvg-js
# then run _gen.mjs from a dir where node_modules resolves (see its header)
```
Edit copy/colors in `_gen.mjs`. Tokens mirror the live v2 dashboard CSS.
