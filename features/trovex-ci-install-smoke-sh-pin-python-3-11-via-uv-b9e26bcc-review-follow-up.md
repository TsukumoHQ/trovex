# [trovex/ci] install-smoke.sh: pin Python 3.11 via uv (b9e26bcc review follow-up)

## Team : fullstack-lead (tsukumo)
## Branch : fix/install-smoke-py311 (from dev)
## Relay task : ff266b51-e64f-4573-b358-700e1b802af6
## Trace : trace=64dedd723a0f24ed597494f38da2907c
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. scripts/install-smoke.sh creates its venv via uv venv --python 3.11 (not bare python3 -m venv)
- [ ] 2. script runs green end to end (output pasted in .niwa-decision.md)
- [ ] 3. bash -n clean

## 2. Root cause & decisions

ROOT_CAUSE: scripts/install-smoke.sh (added in b9e26bcc) created its venv
with bare `python3 -m venv`, which uses whatever python3 resolves first on
PATH. pyproject requires-python is '>=3.11'; on a default macOS box (system
python3 = 3.9.x) the wheel install then dies with a confusing
ResolutionImpossible / no-matching-distribution error instead of a clear
version message. Flagged non-blocking by review-b9e26bcc-73ef-44a6-9ce9-4d3b3973b100.

DECISION: `uv venv --python 3.11 --seed` instead of `python3 -m venv` --
provisions/uses a real 3.11 (uv can fetch one) regardless of PATH, and
--seed keeps pip in the venv so the rest of the script is unchanged.

npm/pytest: not applicable, this is a standalone ops script with no test
suite coverage (same as the rest of scripts/*.sh in this repo -- reviewed by
bash -n + a live run, per review-b9e26bcc's own methodology).

## PR body

Ran scripts/install-smoke.sh live end to end:
  == install wheel into a clean venv ==
  (uv-provisioned 3.11 venv, pip install clean)
  == trovex setup on a fresh CLAUDE_CONFIG_DIR (no mcp) ==
  settings.json OK
  == idempotent re-run (must exit 0, no duplication) ==
  idempotent OK
  install-smoke: PASS

Confirmed the fix is PATH-independent: a throwaway `uv venv --python 3.11`
produced Python 3.11.15 while the ambient `python3` on this machine is
3.12.13 (a different case than the original bug, but proves uv's --python
flag, not PATH order, decides the interpreter).

bash -n scripts/install-smoke.sh -> clean.

## review-trovex verdict: SHIP
Two-line fix to a script this same lane added minutes ago, verified live
green, no other file touched.

## 3. Files changed

```
scripts/install-smoke.sh | 6 +++++-
 1 file changed, 5 insertions(+), 1 deletion(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `ff266b51-e64f-4573-b358-700e1b802af6`._
