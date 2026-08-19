# cfa5c328-followup

## Team : trovex-backend (tsukumo)
## Branch : feat/savings-followup (from main)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

# feat/savings-followup — cfa5c328 review non-blockers

Follow-up to cfa5c328 (merged 2c66dc3d), addressing the two non-blocking
findings review-cfa5c328 flagged on approval.

ROOT_CAUSE: the cfa5c328 merge shipped with two loose ends the adversarial
reviewer flagged as non-blocking: (1) the new GET /api/savings/benchmark route
had no TestClient coverage — only benchmark_result() was unit-tested, so a
handler/JSON-wrap regression would go uncaught; (2) METHODOLOGY.md + run.py
--fixed help named `result.json`, a leftover from an earlier design iteration,
but the committed proof actually lives at `src/trovex/_benchmark.json` — a reader
would look for the wrong file.

## Decision

- **tests/test_savings_receipt.py** — add two TestClient cases against the
  existing `client` fixture: `test_api_savings_benchmark_serves_committed_proof`
  (route 200s, payload sane/deterministic/non-inflated, null-contract holds when
  no proof present) and `test_api_savings_carries_dollar_fields` (the additive
  $ fields + pricing block are served, $-at-precision null when unmeasured).
- **docs** — fix the three stale `result.json` references (METHODOLOGY.md lines
  48 + 68, run.py --fixed help + comment) to `src/trovex/_benchmark.json`.

Docs + tests only. No src logic change, no schema, no API-shape change.

## Gate

`uv run ruff check` clean; `uv run pytest -q` → 308 passed (+2 new); brand +
security guards green.

review-trovex: ✅ ship — 3 files, ~33 LoC — gate green (ruff+pytest), docs/tests
only, no leak/secret/number issue.

## 3. Files changed

```
benchmarks/token-savings/METHODOLOGY.md |  7 ++++---
 benchmarks/token-savings/run.py         |  4 ++--
 tests/test_savings_receipt.py           | 27 +++++++++++++++++++++++++++
 3 files changed, 33 insertions(+), 5 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `cfa5c328-followup`._
