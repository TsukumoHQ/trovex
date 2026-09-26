# [trovex/serve] steal #4: budget-fitted serving: budget= tokens on /api/boot and trovex_search, server picks pointer count + tier per pointer to fit within 15%, reports what it trimmed

## Team : trovex-codex (tsukumo)
## Branch : codex/59e9ff0e-budget-serving (from dev)
## Relay task : 59e9ff0e-77a3-4ea7-a60c-7c2f274dda20
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. /api/boot and trovex_search accept budget (tokens); the returned set's sum of tokens_est is <= budget and >= 0.85*budget when enough candidates exist, chosen by binary search over count then tier per pointer (stub < card < passage); pinned tests on a 50-record fixture at budgets 200, 1000, 5000
- [ ] 2. the response carries budget_used, budget_requested and a trimmed list (doc_id + tier dropped); header X-Trovex-Budget-Used on the HTTP path; pinned test
- [ ] 3. omitting budget keeps today's behaviour byte-for-byte (existing boot and search tests green unchanged)
- [ ] 4. mcp_queries rows record budget_requested and budget_used; pinned test; make test green

## 2. Root cause & decisions

ROOT_CAUSE: Retrieval serving used fixed result-count caps (boot k=5; search k/default ceiling) and had no caller-visible token budget, so callers could only truncate locally without knowing which ranked pointers or content tiers the server omitted.

DECISION: Add a shared budget fitter that binary-searches the largest ranked stub prefix, upgrades each selected pointer through stub/card/passage while it fits, and returns budget_requested, budget_used, and explicit trimmed doc/tier receipts. Preserve the existing response byte path when budget is omitted. Persist requested/used values in mcp_queries and expose the HTTP used value in X-Trovex-Budget-Used.

REJECTED: Greedy whole-passage packing only; it wastes budgets when the next passage is large and does not provide graduated access.

REJECTED: Always returning the new JSON envelope from trovex_search; it breaks existing text consumers and violates the no-budget compatibility AC.

[LEGACY_OPPORTUNITY]: The boot and prompt hook local truncation paths can be removed after deployment once they send their existing local token ceiling as budget.

## review-trovex verdict: SHIP

review-trovex: ✅ ship — 11 files, 317 LoC — gate green (ruff+pytest: 839 passed), Active-Memory scope/case invariants held, no leak/secret/brand issue; schema migration correctly routes to cto-tsukumo.

## 3. Files changed

```
src/trovex/boot.py            | 58 +++++++++++++++++++++++++++++++++--
 src/trovex/budget.py          | 71 +++++++++++++++++++++++++++++++++++++++++++
 src/trovex/db.py              | 20 +++++++++++-
 src/trovex/mcp_app.py         | 45 +++++++++++++++++++++++++--
 src/trovex/server.py          | 20 ++++++++++--
 src/trovex/usage.py           | 18 ++++++++---
 tests/test_budget_serving.py  | 29 ++++++++++++++++++
 tests/test_mcp_contract.py    |  5 ++-
 tests/test_server.py          | 16 ++++++++++
 tests/test_terse_citations.py | 20 ++++++++++++
 tests/test_usage.py           | 15 +++++++++
 11 files changed, 304 insertions(+), 13 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `59e9ff0e-77a3-4ea7-a60c-7c2f274dda20`._
