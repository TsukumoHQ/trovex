# Suite GitHub Reach — 2026-06-18

*Top-of-funnel reach for the OSS suite repos (the surface for CLI tools with no landing). GitHub stars/forks + 14-day traffic (views, unique clones). `gh` CLI auth (push). No PII — repo-level counts only. n/a = repo absent or no access.*

| Repo | Stars | Forks | Views 14d (total/uniq) | Clones 14d (total/uniq) |
|------|------:|------:|------------------------|-------------------------|
| Synergix-lab/WRAI.TH | 21 | 9 | 86/24 | 1367/404 |
| Synergix-lab/trovex | 0 | 0 | 14/3 | 1004/5 |
| Synergix-lab/yoru | n/a | n/a | n/a | n/a (repo absent / no access) |

## Why this exists
WRAI.TH (and yoru, if a CLI) have **no web property**, so the browser analytics module
(`oss_surface_view` etc.) can't be ported there — there's no page to fire it. Their
top-of-funnel reach lives in **GitHub traffic**. The suite→agency hook for these repos is a
**UTM'd tsukumo link in the README** (`utm_source=wraith&utm_medium=oss-suite&utm_campaign=consulting`),
which tsukumo captures as `tsukumo_visit{source=suite}` — no repo-side analytics needed.

## Honesty
- 14-day window is GitHub's max for the traffic API; pull weekly to build history (GitHub
  only retains 14d, so this report IS the archive).
- Stars/clones are reach (vanity-adjacent) — they matter only insofar as they precede
  suite→agency clicks and consulting leads. The north star stays `assessment_request` (suite).
- CLI install/adopt telemetry would be the truer `oss_adopt` signal but is **opt-in only**
  (the CLI runs on the user's machine) — a separate, consent-gated decision, not built here.
