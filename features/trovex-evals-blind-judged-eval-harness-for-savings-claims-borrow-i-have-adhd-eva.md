# [trovex/evals] Blind-judged eval harness for savings claims (borrow i-have-adhd evals design)

## Team : trovex-backend (tsukumo)
## Branch : feat/trovex-eval-harness (from dev)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

ROOT_CAUSE: trovex had no claims-grade eval harness — `bench --eval` gives a binary
CORRECT/WRONG A/B per query but no single gate-able score, no blind judge separate from the
answer-quality judge, no $ budget/resumability, and no `make`-wired release gate. Savings
claims (caveman/rtk/trovex token-savings numbers) had nothing enforcing them at release time.
Task 4b2db04b: borrow the i-have-adhd evals/ design (weighted rubric, blind judging, budget +
resume, release gate) without depending on that repo.

DECISION: built `src/trovex/eval_rubric.py` (weighted rubric — correctness35/autonomy25/
actionability20/safety10/concision10, blind judge_fn signature, fails closed to all-0 on
unparsable judge output) + `src/trovex/eval_harness.py` (combines the free retrieval-quality
pass with the budgeted/resumable rubric pass into one `HarnessReport`, two gates). Versioned
`benchmarks/token-savings/cases.jsonl` (47 cases, C1-C8 taxonomy) against the existing pinned
`corpus/` fixture, reused for reproducibility rather than inventing a new corpus.

REJECTED ALTERNATIVE: the checkpoint's plan named the new CLI command `trovex eval` — wrong,
there is already a `trovex eval` command (cli.py:1243, a live-store recall sanity-checker,
unrelated, predates this task). Silently overwriting it would have broken an existing tool
users may already script against. Renamed the new command to `trovex eval-harness` instead of
clobbering the collision.

DECISION: split the release gate in two rather than hand-waving the "needs OPENAI_API_KEY"
problem — `--retrieval-only` (no LLM, no key, gates on hit@1 alone via the new
`gate_retrieval_only()`) is what `make eval` runs, CI-safe; the full blind-rubric pass needs
`OPENAI_API_KEY` and stays a manual/CI-secret-gated run, documented as such in the README.

BUG FOUND AND FIXED (self-review): `run_harness`'s per-case answer-context retrieval ignored
`rerank=True` — it fed the answerer un-reranked search results while `evaluate_retrieval`
(the reported retrieval stats) DID apply rerank. That's a silent-wrong: `--rerank` would show
an improved hit@1 in the retrieval half of the report while the rubric half's answers were
still generated from un-reranked context — the two halves of one report disagreeing with each
other. Fixed by applying the same `rerank_results()` (mirroring `retrieval_eval.py`'s own
usage) to the per-case search results before selecting context, with the same widened
`max(k, 20)` candidate pool for a fair reorder.

CAVEATS (flagged honestly, not swept under): no OPENAI_API_KEY in this environment — the
rubric path is code-complete and unit-tested with fakes only, never run end-to-end against a
real model this session. `eval-baseline.json` thresholds (min_hit_at_1=0.5, min_weighted=60)
are placeholder guesses (marked as such in the file's own `_comment` and in the README), not
measured — a real run's `hit@1` came back at 0.51, right at the placeholder floor; the
threshold needs a deliberate re-set once a real baseline run exists.

## review-backend verdict: SHIP

Ran the review-backend skill (worktree-scoped variant) against the full diff. Findings:
- §1 recall/retrieval integrity: N/A — no changes to search.py/store.search_chunks/boot.py;
  eval_harness calls the existing `evaluate_retrieval`/`searcher.search` unmodified.
- §2/§3 write-side integrity / reserved source id: N/A — no writes to the live store; the CLI
  command builds an isolated temp-dir Settings exactly like the existing `bench` command.
- §4 auth/secrets: N/A — CLI-only, no new MCP tool or HTTP route; OPENAI_API_KEY read once at
  the CLI boundary and passed to the OpenAI client, never logged/persisted (mirrors `bench`).
- §5 best-effort vs genuine error: `parse_rubric_json` fails closed to all-0 on unparsable
  judge output (never a silent pass); `load_cases`/`_load_resume` fail loud (KeyError/JSONDecodeError)
  on malformed input — correct for CLI-authored files, not agent-critical-path code.
- §6 local-first defaults: unchanged — same temp-dir isolation, same 127.0.0.1 default, no key
  requirement flip.
- §7 schema/embed-dim: N/A — no schema touched.
- §8 honest numbers: the one real finding (rerank inconsistency, above) is fixed; baseline
  thresholds are explicitly marked placeholder, not fabricated as measured.
- §9 validation/tests: no new param reaches a LIKE/regex/SQL clause; 28 new hermetic tests
  (BagEmbedder pattern, fake OpenAI client, no network) cover rubric parsing/weighting, cases
  loading, retrieval-only vs full run, resume dedup, budget stop-without-drop, both gates, and
  report formatting. Full suite: 439 passed, ruff clean.

## 3. Files changed

```
Makefile                                    |   4 +-
 README.md                                   |  20 ++
 benchmarks/token-savings/cases.jsonl        |  63 ++++++
 benchmarks/token-savings/eval-baseline.json |   5 +
 src/trovex/cli.py                           | 123 ++++++++++++
 src/trovex/eval_harness.py                  | 262 ++++++++++++++++++++++++
 src/trovex/eval_rubric.py                   | 113 +++++++++++
 tests/test_eval_harness.py                  | 297 ++++++++++++++++++++++++++++
 tests/test_eval_rubric.py                   | 131 ++++++++++++
 9 files changed, 1017 insertions(+), 1 deletion(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `4b2db04b-2e0f-4cd5-a5b9-ce2df2510104`._
