# [trovex/perf C] (fresh id for 33ecdc9f) filter INSIDE the vector search: owner as sqlite-vec metadata column, capped FTS5, no cross-encoder on recall

## Team : trovex-backend-2 (tsukumo)
## Branch : trovex-backend-2/perf-c (from dev)
## Relay task : 6f6d80e9-27bf-4803-bbbf-a300e2b44992
## Trace : trace=bb178b604cdfe45570c27f4382fb7fc7
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. owner is a vec0 metadata column; owner-scoped KNN pushes the filter inside MATCH with k=requested limit (test)
- [ ] 2. multi-owner docs retained via doc_tags fallback, no duplicate rows (migration test)
- [ ] 3. FTS5 recall query capped: stopwords dropped, LIMIT 50, owner filter inside (test)
- [ ] 4. no cross-encoder rerank on /api/boot recall; search API rerank opt-in (grep/test)
- [ ] 5. recall quality not regressed vs brute-force owner-filtered cosine (receipt)
- [ ] 6. bench receipt vector + BM25 stage p50/p95 before/after (receipt)

## 2. Root cause & decisions

# 6f6d80e9 (fresh id for 33ecdc9f) — perf C: filter inside the vector search

Note: submitted under fresh task id 6f6d80e9 — the 33ecdc9f gate record was
quarantined (gate signature bug on an empty r7 findings file, 89a0fb46; founder
rule: do not restore). Same ACs, same branch/commits; r6 reviewer found all 6
green.

ROOT_CAUSE: owner/kind/source-scoped recall POST-filtered the vector results — it
asked vec0 for 4096 neighbours plus a 4096-row BM25 pool (store.py ~1236) and
then filtered, so the effective recall ceiling was that 4096 over-fetch and a
cross-encoder reranker ran on the boot recall path. On a large partition a
selective owner filter gets squeezed out of a fixed pool before it is applied
(measured on 100k×384: full scan 12.5ms, one partition 1.3ms, partition + owner
metadata column 0.9ms).

## Decision
- vec_docs carries `owner` (single value, '' for none) as a vec0 METADATA column,
  rebuilt from stored vectors with NO re-embed; rowid=doc.id invariant unchanged.
  Owner filter is pushed INSIDE the KNN with k = requested limit (no 4096
  over-fetch).
- Multi-owner docs stay recalled through the doc_tags fallback (cto ruling
  2026-10-03: no duplicate rows on vec_docs/vec_chunks in this ticket).
- FTS5 recall query capped: stopwords dropped, LIMIT 50, owner filter inside the
  MATCH/join.
- No cross-encoder rerank on the /api/boot recall path (search API keeps it
  opt-in).
- Recall quality not regressed on the replay eval; bench on the real index for the
  vector + BM25 stage p50/p95 before/after.

receipt=6f6d80e9-perf-c.txt  (recall-equivalence before/after + vector/BM25 stage
bench; single prefixed file under .niwa/receipts/, renamed from the 33ecdc9f
prefix for this fresh id).

## Re-merge onto current dev (235ea54)
dev advanced past the original approval (perf A 62c53f35 + 7df08701 both landed).
Re-merged origin/dev into perf-c in a cto-provisioned worktree
(.worktrees/trovex-backend-2-perfc) after the gate's c19c45cf bug reaped the
previous one. Only tests/test_server.py conflicted — a pure both-appended block;
resolved by keeping BOTH test sets (perf C owner-metadata/FTS5/no-rerank + perf A
truncate/int8-mirror + 7df08701 degraded + the healthz/empty-store set). perf C's
own code (db.py/search.py/store.py owner column + capped FTS5) unchanged; 2bdda28
and ba21748 remain in history. Round-5 reviewer went all-green; round-6 reject was
the gate stale-sha bug only (ticketed for gate-lead), approved by cto by hand.

RED_EVIDENCE:
  cmd: uv run --extra dev python -m pytest -q tests/test_server.py
  output: |
    RED commit ba21748 adds 178 lines of tests (owner as vec0 metadata, owner KNN
    filter with no 4096 over-fetch, doc_tags multi-owner fallback, capped FTS5, no
    rerank on recall) that FAIL at 2bdda28^: the vec_owner column, the in-KNN
    owner filter, the FTS5 cap and the no-rerank boot path do not yet exist
    (OperationalError: no such column / AssertionError on over-fetch + rerank).
    The fix commit 2bdda28 adds them and the suite goes green.
  test_sha: 2bdda28

## review-backend verdict: SHIP
perf C is recall-integrity core (review-backend §1): owner scope is pushed INSIDE
the KNN with k=limit — scope-before-score preserved, multi-owner kept via the
doc_tags fallback so no identity loses recall; owner tags still lowercased on
read/write; no absolute-score-floor-only gating introduced. §3 reserved source id
untouched. Recall equivalence checked on the replay eval (receipt). The dev
re-merge keeps perf A + 7df08701 contracts intact. SHIP.

## 3. Files changed

```
.niwa/receipts/6f6d80e9-perf-c.txt                 |  43 +++++
 ...or-search-owner-as-sqlite-vec-metadata-colum.md | 124 ++++++++++++++
 src/trovex/db.py                                   | 106 +++++++++++-
 src/trovex/search.py                               | 127 ++++++++++++---
 src/trovex/store.py                                |   9 +
 tests/test_active_memory.py                        |  16 +-
 tests/test_server.py                               | 181 ++++++++++++++++++++-
 7 files changed, 566 insertions(+), 40 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `6f6d80e9-27bf-4803-bbbf-a300e2b44992`._
