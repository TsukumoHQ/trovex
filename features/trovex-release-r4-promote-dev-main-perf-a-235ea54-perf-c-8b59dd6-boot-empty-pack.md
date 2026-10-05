# [trovex/release r4] promote dev -> main (perf A 235ea54, perf C 8b59dd6, boot empty-pack fix 7fa7904; links L1-L5 already shipped) so the live :8765 deploy picks them up

## Team : trovex-backend-2 (tsukumo)
## Branch : trovex-backend-2/release-r4 (from main)
## Relay task : efeb2a08-b2ed-4ea5-8071-e912f950882b
## Trace : trace=145d5aa92311235350245332b167afe3
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. origin/main tree == origin/dev tree 8b59dd6 after merge (git diff --stat origin/dev origin/main empty)
- [ ] 2. uv run --extra dev python -m pytest -q green on the release branch (receipt)
- [ ] 3. no commit on the release branch beyond the promote (no new code)

## 2. Root cause & decisions

# .niwa-decision — trovex release r4 (efeb2a08)

ROOT_CAUSE: n/a — this is a dev→main release promotion, not a code change.

RED_EVIDENCE: n/a — release promotion of already-gated dev commits. The
promoted content (perf A 235ea54, perf C 8b59dd6, /api/boot empty-pack fix
7fa7904) each passed the gate on dev with its own red/green. The release
branch adds NO new code: its tree is byte-identical to origin/dev 8b59dd6
(`git diff --stat origin/dev <release> == empty`). The commit-type rule cannot
distinguish a promotion from new code, so this submit carries per-submit
NIWA_RED_EVIDENCE=0 (never a repo-wide opt-out, never a borrowed test_sha) per
DEC-niwa-gate-11.

SHIP: promote origin/dev (8b59dd6) tree onto origin/main; single parent
fe1c839 (prior main r3); no commit beyond the promote. cto redeploys :8765.

## review-trovex verdict: SHIP

review-trovex: ✅ ship — pure dev→main promotion (tree byte-identical to origin/dev 8b59dd6, single parent fe1c839, 0 new code) — gate green (ruff clean + pytest 1035 passed), no secret/brand-leak/debug in diff, Active-Memory invariants unchanged (promoted commits already gated on dev). Release-adjacent → PR-to-cto via gate, not self-merged.

## 3. Files changed

```
.niwa/receipts/451a5a65-release.txt                |  24 -
 .niwa/receipts/62c53f35-perf-a.txt                 |  46 ++
 .niwa/receipts/6f6d80e9-perf-c.txt                 |  43 ++
 .niwa/receipts/a998cc3a-release.txt                |  12 -
 .niwa/receipts/b02389c2-bench-after.json           |  14 +
 .niwa/receipts/b02389c2-bench-before.json          |  14 +
 .niwa/receipts/b02389c2-bench.md                   |  30 ++
 .niwa/receipts/b02389c2-perf.txt                   |  15 +
 deploy/serve-trovex.sh                             |  16 +-
 features/DEBT.md                                   |   1 +
 ...-silently-empty-pack-on-a-transient-sqlite-o.md | 118 ++++
 ...embed-cost-interactive-launchd-short-query-e.md | 115 ++++
 ...ncy-load-shed-api-boot-background-log-writer.md |  73 +++
 ...or-search-owner-as-sqlite-vec-metadata-colum.md | 124 +++++
 ...filter-inside-the-vector-search-owner-as-sql.md | 105 ++++
 ...5-links-35c0631e-frozen-store-fix-so-the-liv.md | 132 -----
 ...1-l5-links-35c0631e-frozen-store-fix-fresh-i.md | 133 -----
 ...omote-dev-main-again-so-graph-f366c750-ships.md |  49 --
 pyproject.toml                                     |   4 +
 scripts/bench_boot_concurrency.py                  | 170 ++++++
 src/trovex/boot.py                                 |  77 ++-
 src/trovex/config.py                               |  13 +
 src/trovex/db.py                                   | 185 ++++++-
 src/trovex/embedder.py                             | 108 ++++
 src/trovex/offload.py                              |  53 ++
 src/trovex/search.py                               | 127 ++++-
 src/trovex/server.py                               | 141 ++++-
 src/trovex/state.py                                |  11 +-
 src/trovex/store.py                                |   9 +
 src/trovex/usage.py                                | 210 +++++++-
 tests/test_active_memory.py                        |  16 +-
 tests/test_server.py                               | 600 ++++++++++++++++++++-
 tests/test_wal_wedge.py                            |  86 ++-
 tests/test_wedge_class2_recurrence.py              |  39 +-
 uv.lock                                            |   2 +
 35 files changed, 2437 insertions(+), 478 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `efeb2a08-b2ed-4ea5-8071-e912f950882b`._
