# 684035ff-allsources

## Team : trovex-backend (tsukumo)
## Branch : fix/all-sources-dense-recall (from main)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

# P2a follow-up — all-sources dense recall (finding on task 684035ff)

## ROOT_CAUSE
`_resolve_source` (mcp_app.py) returns `None` for `source='*'` AND an unpinned
connection — the documented "search the whole store" contract. But P2a's
partitioned KNN mapped `None → ['trovex']` (SSOT partition only) in BOTH vec0
MATCH paths, so any unpinned / `source='*'` DENSE query silently dropped every
dense hit from file-backed partitions. Hybrid kept only BM25 keyword matches;
`hybrid=False` returned near-nothing. Live corpus: 6 sources — an unpinned query
saw only `trovex` (460 docs), losing dense recall on 4119 docs (tsukumo 3065,
niwa-lessons 290, trovex-repo 252, wraith 247, code 1). MAJOR, user-facing
(cmo/marketing cross-source search).

## FIX
`None`/falsy source scope → enumerate ALL partitions
(`SELECT DISTINCT source_id FROM docs`), scan each, merge by distance (the
existing multi-target merge). Guarded with a final `or [RESERVED_SOURCE_ID]` for
an empty store. Applied to `search.py::_vector_rows` and
`store.py::search_chunks`. Docstrings were correct; the code broke the contract,
so the code is fixed (not the docstrings). boot/flagship/resume pass
`source_ids=['trovex']` EXPLICITLY, so they stay SSOT-scoped — unaffected (the
P2a design intent holds).

## VALIDATION
- New non-vacuous regression
  `test_unpinned_search_scans_all_partitions_not_just_trovex`: a doc matching the
  query lives only in a file-backed `code` partition; an unpinned dense-only
  search must recall it. FAILS with the `['trovex']` fallback, PASSES with the
  enumerate-all fix.
- Gate green: ruff clean, pytest 358 passed, brand clean.
- Live copy (migrated to partitioned): unpinned dense-only query spans 3 sources
  (wraith, trovex, trovex-repo) — the bug returned only `trovex`.

## review-trovex verdict: SHIP

review-trovex: ✅ ship — 3 files (2 src + 1 test) — gate green (ruff+pytest+brand),
all-sources contract restored, boot/flagship SSOT-scope intact, non-vacuous
regression, live-validated. Retrieval-path change → PR-to-cto (cto holds the
P2a redeploy to ship this together).

## 3. Files changed

```
src/trovex/search.py        | 12 ++++++++++--
 src/trovex/store.py         | 15 ++++++++++-----
 tests/test_active_memory.py | 46 +++++++++++++++++++++++++++++++++++++++++++++
 3 files changed, 66 insertions(+), 7 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `684035ff-allsources`._
