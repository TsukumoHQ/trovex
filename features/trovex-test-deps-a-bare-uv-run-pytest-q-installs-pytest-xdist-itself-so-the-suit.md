# [trovex/test deps] a bare `uv run pytest -q` installs pytest-xdist itself, so the suite runs in any synced venv

## Team : trovex-backend-2 (tsukumo)
## Branch : trovex-backend-2/test-deps-group (from dev)
## Relay task : 36e3a08b-93a0-4131-ba2e-0fd78cfea51c
## Trace : trace=33390e4a56134103469bd0ffd04b438c
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. RED: in a venv synced from the pre-fix lock without extras, bare `uv run pytest -q` exits 4 (cited)
- [ ] 2. after the fix the same fresh venv runs bare `uv run pytest -q` green with xdist active (test count cited)
- [ ] 3. `uv sync --extra dev` still works (back-compat)

## 2. Root cause & decisions

# [trovex/test deps] bare `uv run pytest -q` self-installs pytest-xdist (task 36e3a08b)

ROOT_CAUSE: 38c5c8a0 (merged dev 525b5e9) set `addopts = "-n 3 --dist worksteal"` and put pytest-xdist in the `[project.optional-dependencies].dev` EXTRA. `uv run pytest` does NOT sync optional extras, so any venv synced before xdist landed runs a bare pytest that lacks the xdist plugin -> `pytest: error: unrecognized arguments: -n --dist`, exit 4. This rejected r5's gate validate (63ef1f3a r1) and threatens every trovex submit whose validate venv is stale.

## Decision (cto ruling option A, GO msg 82e07b0b)
Add a PEP 735 `[dependency-groups].dev` holding the test deps (pytest, pytest-asyncio, pytest-xdist, httpx, ruff, usearch). uv auto-syncs the default `dev` dependency-group on `uv run` and `uv sync` (no `--extra` needed), so a bare `uv run pytest -q` always provisions pytest AND xdist. The existing `[project.optional-dependencies].dev` EXTRA is kept verbatim for CI that calls `uv sync --extra dev`. uv.lock regenerated. No conftest fallback, no gate change, no addopts change.

## Verification (AC evidence)
- RED (pre-fix, on 525b5e9 before this commit): fresh worktree, `uv sync` (no extras) then bare `uv run pytest -q` ->
    ERROR: usage: pytest [options] ...
    pytest: error: unrecognized arguments: -n --dist
    (exit 4)
- AFTER (this commit): fresh venv (`rm -rf .venv`), `uv lock`, bare `uv sync` (NO extras) auto-installs the dev group ->
    `uv run python -c "import xdist,pytest"` -> xdist 3.8.0 pytest 9.0.3
    bare `uv run pytest -q` -> 1052 passed, 3 warnings in 240.28s (xdist active, exit 0; < 600s and < the 900s cap)
- Back-compat (AC3): `uv sync --extra dev` -> Checked 92 packages, ok (the extra still resolves).
- `uv run ruff check src tests` -> All checks passed.

## review-trovex verdict: SHIP
review-trovex: ✅ SHIP — 2 files / +37 (pyproject.toml [dependency-groups].dev, uv.lock) — gate green: ruff all-pass, bare `uv run pytest -q` 1052 passed with xdist auto-synced (was exit 4). No src/test change, no test added/removed/weakened (count unchanged 1052), no secret/brand/host/number issue. Tooling/deps only; unblocks the gate's bare verify_cmd for every trovex submit (fixes a fleet-blocking false-red, within the freeze). Diff carries no test files -> RED is the exit-4-before / green-after cited above; chore.

## Rejected alternatives
- Gate reviewer-validate runs `uv run --extra dev pytest -q` (option B): a gate change, cto's domain; the dep-group fix is self-contained and durable instead.
- conftest conditional serial fallback (option C): a stale/serial validate re-risks the 900s cap; rejected.

## 3. Files changed

```
pyproject.toml | 17 +++++++++++++++++
 uv.lock        | 20 ++++++++++++++++++++
 2 files changed, 37 insertions(+)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `36e3a08b-93a0-4131-ba2e-0fd78cfea51c`._
