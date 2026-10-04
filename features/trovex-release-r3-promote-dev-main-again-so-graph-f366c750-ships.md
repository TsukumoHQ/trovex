# [trovex/release r3] promote dev -> main again so /graph (f366c750) ships

## Team : trovex-backend (tsukumo)
## Branch : release/promote-r3 (from main)
## Relay task : a998cc3a-d3be-4c0d-b7ce-d277e5b13394
## Trace : trace=74cd2f7293fb1145baee1e2256b2db9b
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. release branch contains origin/main and origin/dev tip incl. f366c750's merge; main -> release is a fast-forward
- [ ] 2. full suite green: uv run --extra dev python -m pytest -q
- [ ] 3. receipt (pre-merge): .niwa/receipts/<taskid8>-release.txt lists commits main..release, the main-only commits absorbed from r2, and any new migrations since r2 (or 'none')

## 2. Root cause & decisions

ROOT_CAUSE: release r3 — /graph (f366c750 = e26caf7 on dev) is not on main; r2 promoted dev @ 7329c92 only. Fix = promote dev tip e26caf7 to main. Release branch = origin/dev + merge of origin/main (e3b930e, r2 promote commit: receipts + redreverify/feature docs, no code). No new migrations since r2.
Rejected alternatives: cherry-pick e26caf7 onto main (would fork main from dev, breaks ff rule); rebase release onto main (rewrites published history).
Receipt: .niwa/receipts/a998cc3a-release.txt (commits main..release, absorbed r2 commit, migrations none).
Suite: 997 passed (279.95s) on release tip 961cd00.

## review-trovex verdict: SHIP — release merge (origin/dev e26caf7 + origin/main e3b930e), receipts/docs + /graph deploy wiring from dev, no new code; ruff clean, suite 997 passed, no secret/brand/TODO hits.

RED_EVIDENCE n/a: release promotion of gated dev commits (f366c750 merged e26caf7); cto ruling 03:08Z

## 3. Files changed

```
.niwa/receipts/a998cc3a-release.txt                |  12 +++
 .niwa/receipts/f366c750-graph.txt                  |  80 +++++++++++++++
 deploy/README.md                                   |  39 ++++++++
 deploy/build-graph.sh                              |  53 ++++++++++
 deploy/serve-trovex.sh                             |   9 ++
 deploy/trovex.service                              |   6 ++
 ...-build-graph-runs-in-the-deploy-path-documen.md | 109 +++++++++++++++++++++
 tests/test_deploy_graph.py                         |  57 +++++++++++
 8 files changed, 365 insertions(+)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `a998cc3a-d3be-4c0d-b7ce-d277e5b13394`._
