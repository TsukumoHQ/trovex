# [trovex/eval] replay eval sees 3 queries in 7 days: /api/boot and the trovex-prompt hook (the fleet's real traffic) are not logged to mcp_queries — log them (source=boot|prompt|mcp) with served ids so --replay and the used-label cover the whole fleet

## Team : trovex-backend (tsukumo)
## Branch : feat/log-boot-prompt-queries (from dev)
## Relay task : 2b7974cf-fecd-42e6-bef6-07fd23be8412
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. /api/boot and the prompt-hook path write mcp_queries rows with source in (boot, prompt) and their served ids into mcp_query_results; additive migration; pinned test (one boot call = one row + N served ids)
- [ ] 2. used-label join applies to boot/prompt rows; pinned test
- [ ] 3. `trovex eval --replay` accepts --source and reports per-source n; pinned test on a fixture log with mixed sources
- [ ] 4. make test green; review-trovex verdict in the PR body; submitted through the gate against dev

## 2. Root cause & decisions

ROOT_CAUSE: round 1 reject was AC3 as originally written ("trovex eval --replay --since 1d on prod after deploy reports n in the hundreds ... numbers on the task") — an acceptance criterion no pre-merge PR can satisfy, since it requires a live deploy plus a day of real fleet traffic. cto-tsukumo ruled the ticket's AC3 itself was wrong and rewrote it to a fixture-testable claim: "trovex eval --replay accepts --source and reports per-source n; pinned test on a fixture log with mixed sources." The prod-numbers requirement moved to the task's DoD (post-merge, cto attaches the numbers after deploy) rather than staying a merge-gate AC.

DECISION: no code change for round 2 — the rewritten AC3 was already satisfied by the original submission: cli.py's `eval --replay --source mcp|boot|prompt` flag, eval_replay.py's `ReplayReport.per_source` breakdown, and tests/test_eval_replay.py::test_replay_reports_per_source_breakdown + test_sample_queries_source_filter (both insert a fixture mcp_queries log with mixed mcp/boot/prompt rows and assert the per-source counts and --source filtering). Resubmitting as-is.

REJECTED_ALTERNATIVE: fabricating placeholder "prod numbers" on the task to force AC3 green — rejected, since real fleet traffic doesn't exist until this deploys; a made-up number would misrepresent measured data.

## review-trovex verdict: SHIP

review-trovex: ✅ ship — 8 files, +314/-15 LoC — gate green (ruff+pytest, 810 passed). AC1 (source column + boot/prompt logging), AC2 (source-agnostic used-label join), AC4 (make test green) unchanged and previously verified green by review-2b7974cf round 1. AC3 rewritten by cto-tsukumo to a fixture-testable claim (--source flag + per-source report) — already satisfied by the original diff: cli.py `eval --replay --source`, eval_replay.py `ReplayReport.per_source`, pinned in tests/test_eval_replay.py::test_replay_reports_per_source_breakdown + test_sample_queries_source_filter (mixed mcp/boot/prompt fixture rows). No code change this round.

## 3. Files changed

```
...es-in-7-days-api-boot-and-the-trovex-prompt-.md | 48 ++++++++++++
 src/trovex/cli.py                                  |  8 +-
 src/trovex/db.py                                   | 29 ++++++-
 src/trovex/eval_replay.py                          | 32 ++++++--
 src/trovex/server.py                               | 22 +++++-
 src/trovex/usage.py                                | 59 +++++++++++++++
 tests/test_eval_replay.py                          | 42 ++++++++++-
 tests/test_server.py                               | 49 ++++++++++++
 tests/test_usage.py                                | 88 +++++++++++++++++++++-
 9 files changed, 362 insertions(+), 15 deletions(-)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-2b7974cf-fecd-42e6-bef6-07fd23be8412
- 🟢 AC1: mechanism verified end-to-end via TestClient; 35/35 tests in touched test files pass — evidence: src/trovex/server.py:903-924 calls log_pointer_query from api_boot; src/trovex/usage.py:224-282 implements log_pointer_query writing one mcp_queries row + N mcp_query_results rows; src/trovex/db.py:1005-1020 additive migration with default mcp + idx_mcp_queries_source index — test: tests/test_server.py:195 test_api_boot_logs_one_query_row_with_served_ids + tests/test_server.py:219 test_api_boot_logs_source_prompt_when_q_given + tests/test_usage.py:164 test_log_pointer_query_writes_one_row_and_its_served_ids
- 🟢 AC2: behavioral test confirms used-label join fires for source=boot rows exactly like source=mcp rows — evidence: src/trovex/usage.py:241-244 sets session_id=agent (same name the agent uses for its MCP X-TROVEX-Session header) so usage.mark_result_used src/trovex/usage.py:69-86 will UPDATE used=1 on the boot-served row when the agent later calls trovex_read(doc_id) within window — test: tests/test_usage.py:189 test_log_pointer_query_source_labels_join_with_mark_result_used
- 🔴 AC3: [partial] AC3 says numbers on the task; doer has none. Mechanism correct, prod numbers pending post-deploy re-verification — gate stays open until cto-tsukumo posts the --replay --since 1d numbers — evidence: mechanism in place: src/trovex/eval_replay.py:158 report.per_source=dict(Counter(...)); src/trovex/cli.py:1296-1349 --source flag + per_source in JSON output. Verified by test_replay_reports_per_source_breakdown. Production numbers in the hundreds NOT provided in PR body, commit message, or feature doc; doer explicitly defers to post-deploy (commit: not producible from a dev worktree). — test: tests/test_eval_replay.py:111 test_replay_reports_per_source_breakdown (mechanism only — does not prove hundreds-of-rows prod traffic)
- 🟢 AC4: deterministic gate green; the flaky unrelated files are pre-existing test isolation issues unaffected by this diff — evidence: make test exits 0 in daemon env per user-provided validate output (810 passed). Local run shows 25 pre-existing flakes in unrelated files (test_usearch_index, test_wedge_class2/3, test_reindex_single_flight, test_savings_receipt, test_mcp_resources) — each passes in isolation; diff touches none of them. Branch is feat/log-boot-prompt-queries → dev, submission through gate. — test: tests/test_eval_replay.py + tests/test_server.py + tests/test_usage.py (35/35 pass locally)

## 5. Timeline

- round 1 → **reject** (review-2b7974cf-fecd-42e6-bef6-07fd23be8412)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `2b7974cf-fecd-42e6-bef6-07fd23be8412`._
