# [trovex/eval] replay real agent queries as the eval set: `trovex eval --replay --since 7d` over mcp_queries + a used-vs-served signal (which served doc ids the agent actually read), with tokens-served as a gated axis

## Team : trovex-backend (tsukumo)
## Branch : feat/eval-replay-used-signal (from dev)
## Relay task : b47301eb-dbf7-41b3-9256-5b4ff94d1b1e
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. mcp_query_results carries a used flag set when a served doc id is read by the same session within the window; additive migration + pinned test
- [ ] 2. `trovex eval --replay --since 7d` runs against a fixture query log and reports rank drift, hit@1 on used-labelled queries, and tokens-served median; pinned test
- [ ] 3. gate_retrieval_only accepts the replay report against a baseline json with min_hit_at_1 and max_tokens_served_median; pinned pass/fail tests
- [ ] 4. make test green; PR carries the review-trovex verdict; submitted through the gate against dev

## 2. Root cause & decisions

> ⚠️ Root cause / arbitration not recorded by the doer yet. The gate requires it before merge — this gap is visible on purpose.

## 3. Files changed

```
src/trovex/cli.py         |  79 +++++++++++++++++++-
 src/trovex/config.py      |   8 ++
 src/trovex/db.py          |  26 +++++++
 src/trovex/eval_replay.py | 181 ++++++++++++++++++++++++++++++++++++++++++++++
 src/trovex/mcp_app.py     |  12 +++
 src/trovex/usage.py       |  32 ++++++++
 tests/test_cli_bench.py   |  18 +++++
 tests/test_eval_replay.py | 177 +++++++++++++++++++++++++++++++++++++++++++++
 tests/test_usage.py       | 133 ++++++++++++++++++++++++++++++++++
 9 files changed, 665 insertions(+), 1 deletion(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `b47301eb-dbf7-41b3-9256-5b4ff94d1b1e`._
