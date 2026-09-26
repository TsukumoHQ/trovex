# [trovex/tests] 7 usearch tests fail on a checkout without the optional `usearch` dep (reviewer of 6851d755 saw them red locally, green on the daemon): skip-if-missing with a pinned marker, so `make test` is green on every install

## Team : trovex-backend (tsukumo)
## Branch : fix/usearch-test-skip-marker (from dev)
## Relay task : 52532317-f35e-4504-ba55-ccd13dc58ec1
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. the usearch-dependent tests skip cleanly when the module is absent (importorskip or marker), listed in the PR body
- [ ] 2. a pinned test asserts the sqlite-vec fallback when usearch is missing
- [ ] 3. make test exit 0 both with and without the usearch extra; both command outputs in the PR body
- [ ] 4. review-trovex verdict in the PR body; submitted through the gate against dev

## 2. Root cause & decisions

> ⚠️ Root cause / arbitration not recorded by the doer yet. The gate requires it before merge — this gap is visible on purpose.

## 3. Files changed

```
tests/test_usearch_fallback.py | 74 ++++++++++++++++++++++++++++++++++++++++++
 tests/test_usearch_index.py    | 11 +++++++
 2 files changed, 85 insertions(+)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `52532317-f35e-4504-ba55-ccd13dc58ec1`._
