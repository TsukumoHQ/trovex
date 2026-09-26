# [trovex/capture] steal #13: surprisal gate on capture: embed the free summary, KNN against owner/<agent> records, skip near-duplicates, write verbatim in the middle band, distil only novel + long captures

## Team : trovex-backend (tsukumo)
## Branch : feat/capture-surprisal (from dev)
## Relay task : 7984d9e3-2236-4ba2-b44d-9f861c11836e
## Trace : trace=3827c3d9b9ccfac4c9bfb82be496b0b4
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. a capture whose summary embeds within cosine > 0.95 of an existing owner/<agent> record is skipped and the skip is recorded (reason, max_cos, nearest doc_id); pinned test with a fake embedder
- [ ] 2. a capture in the middle band is written verbatim without calling the distiller; a novel long capture calls the distiller; pinned tests assert distiller call counts
- [ ] 3. thresholds and the min length are config keys with documented defaults; setting skip threshold to 1.0 disables the gate (pinned test)
- [ ] 4. /api/status or the capture response exposes counts skip/verbatim/distil for the run; make test green

## 2. Root cause & decisions

# Decision — capture surprisal gate (task 7984d9e3)

ROOT_CAUSE: capture_state had no novelty check: every PostCompact re-wrote the agent's current-state record even when the summary said nothing new (churn, re-embed, version snapshots), and the BYOK distiller was called for any transcript-only capture regardless of whether it added anything.

## Decision
- Embed the incoming text (free summary, else the last 4000 chars of the transcript) and take its max cosine against the agent's own active `owner/<agent>` records (`SqliteStore.nearest_owner_record`: vec0 KNN restricted to that owner's rowids, so another agent's identical state never causes a skip; cosine = 1 - vec0 cosine distance).
- max_cos > capture_skip_cosine (0.95) -> skip, nothing written; capture_skip_cosine=1.0 disables the gate. max_cos >= capture_verbatim_cosine (0.80) or text shorter than capture_distil_min_chars (1500) -> verbatim (no distiller). Otherwise -> distil (novel AND long), merged with the prior state; a failed distil keeps the summary.
- A transcript-only capture (no free summary) can only be skipped or distilled: a raw transcript is not a state record, and the existing contract (test_distil) is distil-or-nothing.
- Every gated capture appends a row to the new `capture_decisions` table (agent, decision, max_cos, nearest_doc_id, chars); the response carries decision, max_cos, nearest_doc_id (on skip) and the running {skip, verbatim, distil} counts read from that table (survive a restart).

## Rejected alternatives
- In-memory counters only: rejected, lost on restart, the DoD needs the decision mix over a day.
- Re-using check_duplicate: rejected, it is source+kind scoped, uses `1 - d/2`, and does not scope to one owner.
- Distiller never applied to summaries: rejected, the ticket says novel + long captures are distilled.
- [LEGACY_OPPORTUNITY] check_duplicate's similarity `1 - distance/2` is not a cosine for a cosine-metric vec0 column (it maps cos 0.9 to 0.95); dup_cosine_threshold is tuned against that scale, do not unify blindly.

## Verification
`make test`: 849 passed, ruff clean. tests/test_capture_surprisal.py: skip+record, middle band verbatim (distiller calls == 0), novel long distil (calls == 1), novel short verbatim, first capture, owner scoping, skip=1.0 disables, config defaults + min length, transcript gating, run counts.

## review-trovex verdict: SHIP
Additive table; store.put path unchanged; capture never raises into the agent (gate failure -> nearest None -> treated as novel); owner tag lower-cased as before.

RED_EVIDENCE:
  cmd: uv run pytest tests/test_capture_surprisal.py -q
  test_sha: bc03f76
  output: |
    E       assert True is False
    E       KeyError: 'decision'
    E                   AttributeError: 'Settings' object has no attribute 'capture_skip_cosine'
    E       KeyError: 'counts'
    FAILED tests/test_capture_surprisal.py::test_near_duplicate_capture_is_skipped_and_recorded
    FAILED tests/test_capture_surprisal.py::test_middle_band_is_written_verbatim_without_the_distiller
    FAILED tests/test_capture_surprisal.py::test_novel_long_capture_calls_the_distiller_once
    FAILED tests/test_capture_surprisal.py::test_novel_but_short_capture_is_verbatim
    FAILED tests/test_capture_surprisal.py::test_thresholds_and_min_length_are_config_keys

## 3. Files changed

```
Makefile                                           |  10 +-
 features/DEBT.md                                   |   1 +
 ...te-on-capture-embed-the-free-summary-knn-aga.md |  74 +++++++++
 src/trovex/capture.py                              |  66 +++++++-
 src/trovex/config.py                               |  10 ++
 src/trovex/db.py                                   |  12 ++
 src/trovex/store.py                                |  56 +++++++
 tests/test_capture_surprisal.py                    | 179 +++++++++++++++++++++
 tests/test_makefile.py                             |  23 +++
 9 files changed, 421 insertions(+), 10 deletions(-)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by human:cto-tsukumo

### Round 1 — ❌ REJECTED by human:cto-tsukumo

### Round 1 — ❌ REJECTED by human:cto-tsukumo

### Round 1 — ❌ REJECTED by human:cto-tsukumo

## 5. Timeline

- round 1 → **reject** (human:cto-tsukumo)
- round 1 → **reject** (human:cto-tsukumo)
- round 1 → **reject** (human:cto-tsukumo)
- round 1 → **reject** (human:cto-tsukumo)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `7984d9e3-2236-4ba2-b44d-9f861c11836e`._
