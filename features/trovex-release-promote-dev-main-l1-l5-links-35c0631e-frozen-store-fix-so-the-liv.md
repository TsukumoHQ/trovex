# [trovex/release] promote dev -> main (L1-L5 links + 35c0631e frozen-store fix) so the live :8765 deploy picks them up

## Team : trovex-backend (tsukumo)
## Branch : release/promote-main-8ad97489 (from main)
## Relay task : 8ad97489-48c9-4359-adb0-835b828f6b88
## Trace : trace=74cd2f7293fb1145baee1e2256b2db9b
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. release branch == origin/dev tip containing 35c0631e; fast-forward of main (no merge commit needed)
- [ ] 2. full suite green: uv run --extra dev python -m pytest -q
- [ ] 3. receipt (pre-merge): migrations applied on a scratch COPY of the live DB, docs count before == after, startup time measured; file .niwa/receipts/<taskid8>-release.txt

## 2. Root cause & decisions

# Decision — 8ad97489 [trovex/release] promote dev -> main

ROOT_CAUSE: n/a (release / promotion, not a bug fix). deploy/serve-trovex.sh
deploys origin/main only; dev is main + 6 already-merged, already-gate-reviewed
commits. This ships them to main so the live :8765 deploy picks up the
35c0631e frozen-store fix and the L1-L5 links.

## What ships (origin/main..origin/dev — 6 commits, FAST-FORWARD)
L1-L5 links work + 35c0631e (log_pointer_query stuck-txn rollback + loop-only
/healthz). main is an ancestor of dev, so main fast-forwards to dev with no
merge commit (AC1).

## Migrations that run on the live DB at next serve start
`open_db()` runs its migration sequence on every start; idempotent. The ones
NEW vs the currently-deployed main:
- `_migrate_add_drift` (L5): `docs.drift` + reason (ALTER ADD COLUMN)
- `_init_schema` CREATE TABLE IF NOT EXISTS: `doc_refs`, `doc_links`,
  chunk-level tables (L1 / L3 / L4)
- `_migrate_add_provenance`: `docs.source_url` / record_locator / ... (ALTER ADD COLUMN)
All additive + idempotent. Proven on a COPY of the real live DB (never the live
file): 4987 docs before == 4987 after, 0.74 s, new schema present.

## Rejected alternatives
- A merge commit into main: unnecessary — main is an ancestor of dev, so a clean
  fast-forward is the right shape (AC1).
- Touching the live DB to prove migrations: never — proof is on a `sqlite3
  .backup` COPY in a scratch dir, per the ticket.

receipt=.niwa/receipts/8ad97489-release.txt

## review-backend verdict: SHIP (promotion of already-reviewed commits; no new code)
Every commit in origin/main..origin/dev was gate-approved on its way onto dev.
This release branch == origin/dev tip byte-for-byte, so the diff-vs-main is
exactly those reviewed commits — no new code to review. Migration safety is
proven on a real-size copy (above). Full suite is the merge gate (verify_cmd).

RED_EVIDENCE:
  cmd: uv run --extra dev python -m pytest -q tests/test_server.py -k "pointer_query or healthz_503"
  test_sha: 7329c92c10f4d17f523a61f1949fe5b7b81632dc
  output: |
    (promotion — the frozen-store fix's tests, added in commit 7329c92 and
    carried in this release range, failed on the pre-fix tree; proven at
    35c0631e's gate rounds)
    E   assert 200 == 503   # /healthz answered 200 on a stale served store
    FAILED tests/test_server.py::test_log_pointer_query_rolls_back_stuck_txn_on_error
    FAILED tests/test_server.py::test_healthz_503_when_served_empty_but_db_populated
    2 failed

## 3. Files changed

```
.niwa/receipts/01-full-status.jpg                  |  Bin 0 -> 183582 bytes
 .niwa/receipts/02-heat.jpg                         |  Bin 0 -> 285644 bytes
 .niwa/receipts/03-panel.jpg                        |  Bin 0 -> 74373 bytes
 .niwa/receipts/04-perf-5k.jpg                      |  Bin 0 -> 433501 bytes
 .niwa/receipts/8ad97489-release.txt                |   24 +
 .niwa/receipts/README.md                           |   56 +
 .trovexignore                                      |    4 +
 ...bd6e-c95f-440e-8310-8ec9a49d3711-redreverify.md |  132 +
 features/DEBT.md                                   |    2 +
 ...a169-ab85-4f56-8a2e-d8a290b3eae3-redreverify.md |   82 +
 ...7dfb-5fc1-46ac-ae5a-4b6075019908-redreverify.md |   74 +
 ...4797-be7d-9f3c3a6dd6c1-redreverify-redreveri.md |   72 +
 ...4106-2c4e-4797-be7d-9f3c3a6dd6c1-redreverify.md |   73 +
 ...-links-wikilinks-relative-md-links-parsed-at.md |   95 +
 ...-trovex-read-returns-outgoing-links-backlink.md |   85 +
 ...ked-mentions-semantic-similar-neighbours-com.md |   78 +
 ...rain-graph-webgl-knowledge-graph-view-docs-c.md |  138 +
 ...-to-source-files-symbols-tickets-commits-bec.md |   82 +
 ...ty-store-api-stats-total-0-api-map-count-0-w.md |   86 +
 src/trovex/assets/skill/SKILL.md                   |    7 +
 src/trovex/code_refs.py                            |  362 +
 src/trovex/db.py                                   |   83 +
 src/trovex/graphview.py                            |  325 +
 src/trovex/implicit_refs.py                        |  188 +
 src/trovex/indexer.py                              |   52 +
 src/trovex/links_parse.py                          |  457 +
 src/trovex/mcp_app.py                              |   72 +-
 src/trovex/search.py                               |   19 +
 src/trovex/server.py                               |  174 +-
 src/trovex/state.py                                |    5 +
 src/trovex/status.py                               |    8 +
 src/trovex/store.py                                |   20 +
 src/trovex/templates/doc.html                      |   48 +
 src/trovex/usage.py                                |   11 +
 tests/test_doc_refs.py                             |  253 +
 tests/test_doc_refs_code.py                        |  197 +
 tests/test_doc_refs_implicit.py                    |  135 +
 tests/test_doc_refs_mcp.py                         |  146 +
 tests/test_mcp_contract.py                         |    5 +-
 tests/test_server.py                               |  281 +
 web/.gitignore                                     |    1 +
 web/graph.html                                     |   18 +
 web/package-lock.json                              | 9981 ++++++++++----------
 web/package.json                                   |    9 +
 web/src/graph/Graph.tsx                            |  606 ++
 web/src/graph/SidePanel.tsx                        |  132 +
 web/src/graph/api.ts                               |  140 +
 web/src/graph/graph.css                            |  391 +
 web/src/graph/lenses.ts                            |  129 +
 web/src/graph/main.tsx                             |   12 +
 web/src/graph/selectBridge.ts                      |    6 +
 web/vite.graph.config.ts                           |   35 +
 52 files changed, 10455 insertions(+), 4936 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `8ad97489`._
