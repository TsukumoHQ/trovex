# [trovex/suite speed] the full trovex test suite finishes well under the gate's 900s slot cap

## Team : trovex-backend-2 (tsukumo)
## Branch : trovex-backend-2/suite-speed (from dev)
## Relay task : 38c5c8a0-b412-4fa8-917c-5e354e69e4f9
## Trace : trace=cf9c1acffa607040461350a80dbcaa02
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. before/after wall time of the full suite cited in the submit, with host load at run time
- [ ] 2. full suite <= 600s locally under the gate's job count, all tests still run (count unchanged)
- [ ] 3. suite green 3 runs in a row with the new parallelism (no new flakes)

## 2. Root cause & decisions

# [trovex/suite speed] clear the gate 900s slot cap (ticket 38c5c8a0)

ROOT_CAUSE: `uv run pytest -q` runs the trovex suite SERIALLY (no pytest-xdist in deps). Measured 300.87s at host load ~18, and ~1215s under fleet load 40-100 — the latter overran the gate's 900s wall-clock slot cap, so `niwa slot run` killed the process group and every trovex submit (dev and main, incl. r5 63ef1f3a) was blocked. The suite is not hung (it completes); it is just too slow serially. --durations=40 top costs: test_status_incremental::...2000_doc_corpus_reindex (86.2s), test_reindex_embed_perf::...2000_doc_corpus (56.4s), test_chunking_code 2 tests (23.1s+21.0s), test_server::test_api_boot_truncates_long_query (20.9s). The two 2000-doc reindex tests do real work in the test body (not a cacheable fixture), so the cause is total serial wall-time, not a single fixture.

## Decision
- Add `pytest-xdist>=3.6` to the dev extra and set `addopts = "-n 3 --dist worksteal"` in [tool.pytest.ini_options]. No model/fixture rewrite was needed — the dominant tests do genuine per-test reindex work, so the win is parallelism, not fixture caching.
- `-n 3` is a FIXED, bounded worker count (NOT `-n auto`). `-n auto` (18 workers) saturated the cores and made the ~1s TOOL_TIMEOUT_SEC capture-deadline tests 504 (test_wedge_class2_recurrence::test_fast_capture_is_unaffected failed in the gate slot under contention). 3 workers match the gate's job budget and leave CPU headroom so those timing assertions stay honest, while still cutting the suite from ~300s serial to ~114-163s.
- `worksteal` so the long reindex tests don't tail-block a worker while others idle.
- NO cap raise, NO NIWA_PRESUBMIT_CHECK=0 waiver, NO test deleted/skipped/@slow-excluded. Test count unchanged (1052).

## Isolation safety (why -n auto is safe here)
Audited tests/ before parallelizing: every test uses its own `settings.data_dir` tmp path + sqlite file (grep found no shared/hardcoded on-disk db path); the only `localhost:PORT` refs are mocked (test_embedder_byo asserts a base_url, no real bind); no module/session-scoped fixtures (all function-scoped, independent). Each xdist worker is its own process with its own singletons. No ordering deps.

## Verification (AC evidence)
- BEFORE: 300.87s serial, 1052 passed, host load avg ~18 (1.28/5/15m: 18.54/28.09/34.92 at start). Under fleet load 40-100 it was ~1215s and the gate killed it at 900s.
- AFTER (`uv run pytest -q`, addopts -n 3 applied; xdist: 1052 tests collected):
    RUN 1: 162.66s  1052 passed  (load ~14.6)  fast_capture flake: 0
    RUN 2: 144.90s  1052 passed  (load ~15.0)  fast_capture flake: 0
    RUN 3: 113.69s  1052 passed  (load ~10.1)  fast_capture flake: 0
  3 green runs in a row, no new flakes (the capture-deadline tests passed every run), test count unchanged (1052). All < 600s target and well under the 900s cap.
  (An earlier -n auto attempt hit 116-134s locally but 504'd test_fast_capture_is_unaffected in the gate slot under contention — see Rejected alternatives; that is why the final value is -n 3.)
- `uv run ruff check src tests`: All checks passed.

## review-trovex verdict: SHIP
review-trovex: ✅ SHIP — 2 files / +~40 (pyproject.toml dev-dep + addopts, uv.lock) — gate green: ruff all-pass, `uv run pytest -q` 1052 passed x3 (163/145/114s, was 300s serial), capture-deadline tests 0 flakes at -n 3. No src/behaviour change, no test added/removed/weakened (count unchanged 1052), isolation audited safe for -n auto, no secret/brand/host/number issue. Infra/perf change, within the niwa-v1 fixes-only freeze (unblocks a dead gate). Diff carries no test files -> RED_EVIDENCE not applicable (no behaviour-changing AC; perf/chore).

## Rejected alternatives
- Raise the slot cap / CHECK=0 waiver: cto refused (gate-weakening = founder-only).
- Shrink the 2000-doc corpus or @slow-exclude the heavy tests: weakens coverage; cto forbade.
- `-n auto` (18 workers): REJECTED. Fastest locally (~116s) and green at low load, but saturates all cores; in the gate slot under fleet contention the ~1s TOOL_TIMEOUT_SEC capture handler exceeded its deadline and test_fast_capture_is_unaffected 504'd (1 failed). Oversubscription breaks the load-shed timing tests. -n 3 keeps headroom and is still ~2x+ faster than serial.

## 3. Files changed

```
pyproject.toml | 16 ++++++++++++++++
 uv.lock        | 24 ++++++++++++++++++++++++
 2 files changed, 40 insertions(+)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `38c5c8a0-b412-4fa8-917c-5e354e69e4f9`._
