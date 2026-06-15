# Docs / blog diagrams (brand-system)

Concept diagrams for the docs + blog. Crisp SVG → `resvg` (sources in `growth/assets/_src/`).
Brand `#0a0e17` / green `#22c55e` / Fira, lowercase `trovex`, real ~60% only.

| File | Size | Explains |
|------|------|----------|
| `diagram-freshness.png` | 1200×760 | the freshness markers — `★ canonical` (served), `✗ stale` (demoted), `⚠ duplicate` (deduped), `◯ plan`. Markers match `src/trovex/search.py`. |
| `diagram-writepath.png` | 1200×760 | the shared write path / SSOT — one agent writes a canonical note, every other agent + teammate reads it; write once, read many. |

Pairs with the core landing diagram `web/public/diagram-canonical.{svg,png}`.
