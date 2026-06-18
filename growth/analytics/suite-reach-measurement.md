# Suite-Side Reach Measurement (CLI tools have no web property)

*Owner: analytics-lead · 2026-06-18 · Finding + approach from the WRAI.TH suite-side port task.*

## The finding

The "port the browser analytics module to WRAI.TH" plan **doesn't apply as written**:
**WRAI.TH is a Go CLI with no web landing** (no `package.json`, no site — `main.go` +
`install.sh`; the surface is the GitHub repo + README). A browser module (`oss_surface_view`
fires in a `<page>`) has nowhere to mount. Same will hold for **yoru** if it's also a CLI.
trovex is the exception — it *has* a landing, so its suite-side events are live (trovex #187).

So suite-side measurement splits by surface type:

| Surface | Reach (top) | Adopt | Suite → agency |
|---------|-------------|-------|----------------|
| **Web landing** (trovex) | `oss_surface_view` (Plausible) | `oss_adopt` (waitlist) | `suite_to_agency_click` + UTM |
| **CLI repo** (WRAI.TH, yoru) | **GitHub stars/forks/views/clones** | CLI telemetry — **opt-in only** | **UTM'd README link** → tsukumo captures `source=suite` |

## What I shipped (the achievable part)

**`github-suite-reach.mjs`** — pulls stars / forks / 14-day views / unique clones for the
suite repos via the `gh` CLI (push auth; no key in code; repo-level counts, no PII), writes
`reports/suite-github-reach-<date>.md`. First read (2026-06-18): **WRAI.TH 21★ · 1367 clones
/404 uniq · 86 views** (biggest TOF, as expected); trovex 0★ · 14 views; yoru repo absent.
Run weekly — GitHub only retains 14 days of traffic, so the report is the archive.

## The suite → agency hook for CLI repos (recommend — cross-lane)

WRAI.TH's README has **no tsukumo link** today. The clean, privacy-respecting way to measure
"does WRAI.TH drive agency leads" without any repo-side analytics: add a **UTM'd tsukumo link**
to the README (e.g. a "built by tsukumo / consulting for teams running agents" line):

```
https://tsukumo.ch/?utm_source=wraith&utm_medium=oss-suite&utm_campaign=consulting
```

tsukumo then records the click as `tsukumo_visit{source=suite, geo_source=wraith}` — the
cross-property funnel closes, no WRAI.TH analytics needed. **This is a README/content change
→ for content-lead/cmo** (I flagged it; I did not edit WRAI.TH's README). yoru follows.

## Deferred (privacy)

CLI install/adopt telemetry would be the truest `oss_adopt` for a CLI, but it runs on the
user's machine → **opt-in only, explicit consent, honor `DO_NOT_TRACK`** (skill rule). A
separate, consent-gated decision — not built here.

## Acceptance

- [x] Reported the scope finding honestly (CLI = no web property → browser module N/A; not fabricated).
- [x] Shipped the achievable reach signal: `github-suite-reach.mjs` + first real report.
- [x] Defined the per-surface measurement split; flagged the README UTM crosslink to content/cmo.
- [ ] content/cmo: add the UTM'd tsukumo link to WRAI.TH (+ yoru) README → closes the suite→agency loop.
- [ ] CLI opt-in telemetry = separate consent-gated task if/when wanted.
