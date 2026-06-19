# wrai.th gallery — screenshot capture brief (slides 1–3)

Slides 4, 5, the OG card and the thumbnail are **done** (typographic/diagram,
in this folder). Slides 1–3 are **real dashboard captures** — the honesty gate
says every screen is a real run, so a human grabs them from the live dashboard
(headless capture of the live websocket SPA isn't reliable from here).

The dashboard is live at **http://localhost:8090/v2/** with this colony's real
agents/tasks/messages — ideal, real data.

## What to capture (3 PNGs)

Capture clean (hide any dev overlays; 2× / retina if possible). Drop the raw
files in this folder as `raw-slide-1.png` … `raw-slide-3.png` and ping
design-lead — I composite them into branded 1270×760 frames with the verbatim
caption + wordmark, matching slides 4–5. (Or use them raw if you prefer.)

| slide | view at /v2/ | what must be visible | verbatim caption |
|---|---|---|---|
| 1 — HOOK (also the PH thumbnail) | dashboard home | several agents listed live + their current tasks (the "oh, I get it" screen) | `mission control for your AI agent fleet` |
| 2 — COORDINATION | messaging + shared task board | inter-agent messages + a task moving claim→start→complete across 2–3 agents | `agents that message each other + share one task board` |
| 3 — MEMORY | the shared memory store | a real memory entry agents read/write; context surviving across sessions | `persistent memory that survives /clear` |

## Brand (so captures sit with the built slides)
wrai.th's own identity — dark `#0a0c10`, emerald accent `#4ade80`, mono. **Not**
tsukumo acid. Lowercase `wrai.th`. No "Synergix" in any pixel (the repo URL is the
only allowed instance). No fabricated metrics — it's a real run or it's not used.

## Frame spec (if you composite yourself)
1270×760, dark bg, 5px emerald top rule, `wrai.th` wordmark top-left (dot in
accent), verbatim caption as the headline, screenshot dominant below. The
generator `_gen.mjs` has the exact tokens + a `frame()` helper to reuse.
