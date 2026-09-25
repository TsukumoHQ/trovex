# [trovex/index] reindex_paths() phase_ms['status'] polluted by microseconds on skip — _status_t0 captured outside the if/elif

## Team : trovex-backend (tsukumo)
## Branch : fix/status-t0-skip-timing (from dev)
## Relay task : 64b5c771-51ac-4ad0-937a-16453b117324
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. _status_t0 timer moved inside each branch that actually calls compute_status; the skip path never touches phase_ms['status']
- [ ] 2. pinned test: an fs-watch event that does not change bytes leaves stats['phase_ms']['status'] == 0.0 and compute_status is never called (spy)
- [ ] 3. make test green

## 2. Root cause & decisions

> ⚠️ Root cause / arbitration not recorded by the doer yet. The gate requires it before merge — this gap is visible on purpose.

## 3. Files changed

```
src/trovex/indexer.py  |  8 +++++---
 tests/test_fs_watch.py | 24 ++++++++++++++++++++++++
 2 files changed, 29 insertions(+), 3 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `64b5c771-51ac-4ad0-937a-16453b117324`._
