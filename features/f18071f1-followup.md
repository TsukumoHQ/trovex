# f18071f1-followup

## Team : trovex-backend (tsukumo)
## Branch : docs/card-comment-soften (from main)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

ROOT_CAUSE: the card `_fmt_card` docstring + inline comment claimed the card rung is "strictly cheaper" / "the cheapest rung" than the passage, an absolute that is false for a section under ~50 words (card = extract + escalation hint can tie or exceed a tiny passage). review-f18071f1 notice; no bug (ledger honest), just an overstated comment.

Decision: soften both to "cheaper for any section past ~50 words; a very short section can tie". Comment/docstring-only, no logic.

review-trovex: OK ship — 1 file, comment-only, no gate/behaviour impact.

## 3. Files changed

```
src/trovex/mcp_app.py | 9 ++++++---
 1 file changed, 6 insertions(+), 3 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `f18071f1-followup`._
