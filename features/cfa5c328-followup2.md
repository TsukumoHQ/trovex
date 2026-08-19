# cfa5c328-followup2

## Team : trovex-backend (tsukumo)
## Branch : docs/corpus-queries-filename (from main)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

ROOT_CAUSE: two comment lines in corpus-queries.txt still named the pre-rename `result.json`; the committed proof is src/trovex/_benchmark.json, so the comments lied about the filename (review-cfa5c328-followup notice). Docs-only.

Decision: rename the two refs to src/trovex/_benchmark.json. Comment-only, no logic.

review-trovex: OK ship — 1 file, 2 lines, doc-only, no gate impact.

## 3. Files changed

```
benchmarks/token-savings/corpus-queries.txt | 5 +++--
 1 file changed, 3 insertions(+), 2 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `cfa5c328-followup2`._
