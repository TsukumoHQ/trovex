# [ci/cost] trovex repo: no GitHub CI on the private repo except the tag-triggered OIDC publish: delete the 7 other workflows, dep-audit -> dokan schedule, announce-release -> scripts/, docs/ops/ci.md

## Team : fullstack-lead (tsukumo)
## Branch : ci/drop-private-actions (from dev)
## Relay task : b9e26bcc-73ef-44a6-9ce9-4d3b3973b100
## Trace : trace=1dbe99a2a95338bcb258113a250bb9a9
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. trovex .github/workflows contains exactly publish-mcp.yml (sh scripts/verify-no-workflows.sh passes: empty except publish-mcp.yml); `gh run list` shows no new non-tag runs after merge
- [ ] 2. brand/security guard coverage proven by the existing pytest guards (names in PR body); install-smoke + announce-release live in scripts/ and run green once (output in PR body)
- [ ] 3. dep-audit daily audit exists as a dokan schedule (schedule id + script name in the PR body) or is listed as dropped with one line of reason
- [ ] 4. docs/ops/ci.md (trovex) states the niwa gate is the CI, the kept publish workflow, and where each folded job now runs
- [ ] 5. PR merged via the Q&A gate against dev

## 2. Root cause & decisions

ROOT_CAUSE: founder rejected standing up a self-hosted GitHub Actions runner
to dodge private-repo Actions minutes ("je vois pas pourquoi runner CI ? au
pire on la met juste pas", task 819445bf, 2026-09-26 21:32Z) -- the real fix
is to stop running GitHub Actions on this private repo at all (except the
one workflow that needs Actions' own OIDC identity), since the niwa review
gate already gates every merge. Sibling of 819445bf (tsukumo half); split by
cto-tsukumo 21:20Z into this task (b9e26bcc, trovex half) because one gate
record can only track one repo/worktree -- ruling 707574cc.

DECISION: delete core.yml, web.yml, brand.yml, security.yml, skill-gate.yml,
dep-audit.yml, announce-release.yml. Keep publish-mcp.yml (tag push,
id-token: write -- PyPI Trusted Publishing + MCP registry OIDC; a keyless
trust handshake that only GitHub Actions' own OIDC issuer can do, can't move
off Actions). brand.yml/security.yml were already fully redundant with
tests/test_{brand,security}_guard.py::test_live_repo_scans_clean (calls the
real scan() against the live tree from inside `pytest -q`, which the gate
already runs) -- verified 18/18 guard tests green, 919/919 full suite green
(rebased onto current dev). core.yml's ruff+pytest and web.yml's `npm run
build` (already chains lint+typecheck+vitest+every brand/sitemap/pii/voice
guard) are what the gate runs pre-merge. web.yml's indexnow ping: `npm run
indexnow` script already exists, run manually post-deploy. skill-gate.yml:
superseded by the niwa QA gate's own verdict requirement. install-smoke
(core.yml job) and announce-release.yml folded into scripts/install-smoke.sh
and scripts/announce-release.sh, run by hand. dep-audit.yml's daily
pip-audit/npm-audit cron: dropped, no replacement (see PR body).

REJECTED: keep a scaled-down Action for the daily dep-audit cron -- rejected
for the same reason as everything else here: any GitHub Action on this repo
burns the private-repo minutes the founder called out.

## PR body

**AC1** -- `.github/workflows` contains exactly `publish-mcp.yml`:
  sh scripts/verify-no-workflows.sh -> no-extra-workflows (exit 0)

**AC2** -- brand/security guard coverage + install-smoke/announce-release live:
  - Coverage already proven by pytest: `tests/test_brand_guard.py::test_live_repo_scans_clean`,
    `tests/test_security_guard.py::test_live_repo_scans_clean` (both call the
    real scan() against the live tree; part of `pytest -q` / `make test`).
    18/18 guard tests green, 919/919 full suite green.
  - scripts/install-smoke.sh run live just now:
      == build wheel == ... Successfully built dist/trovex-<version>-py3-none-any.whl
      == install wheel into a clean venv == (clean install, no conflicts after
      the dist/*.whl cleanup fix in this same PR)
      == trovex setup on a fresh CLAUDE_CONFIG_DIR (no mcp) ==
      settings.json OK
      == idempotent re-run (must exit 0, no duplication) ==
      idempotent OK
      install-smoke: PASS
  - scripts/announce-release.sh: extracted verbatim from the deleted workflow
    (gh api release lookup + Discord webhook post); not run live here (needs
    a real published tag + Discord webhook secret, neither present in this
    worktree) -- shape-checked with `bash -n`, clean.

**AC3** -- dep-audit (daily pip-audit + npm audit, no PR involved) is
  DROPPED, no replacement. Reason: it was the only check that ran without a
  human opening a PR; every other guard/test moved to what the niwa gate
  already runs per-PR. Accepted risk per the founder's Actions-off call --
  re-add as a dokan daily schedule later if a real CVE gap bites.

**AC4** -- docs/ops/ci.md (trovex) states the niwa gate is the CI, names the
  kept publish-mcp.yml, and tables where each dropped job's job now lives
  (pytest, npm run build, npm run indexnow, scripts/install-smoke.sh,
  scripts/announce-release.sh, dropped-dep-audit).

**AC5** -- merged via qa-submit against `dev` (this task, b9e26bcc).

## review-trovex verdict: SHIP
Workflow deletion + two folded shell scripts (one bug fixed live: stale
dist/*.whl broke a clean install, fixed and re-verified PASS) + doc, no
production code path touched. .github/workflows now has only
publish-mcp.yml, docs/ops/ci.md documents the new model, pytest 919/919 and
npm run build both green on this branch (rebased onto current origin/dev).

## 3. Files changed

```
.github/workflows/announce-release.yml |  95 ------------------------------
 .github/workflows/brand.yml            |  20 -------
 .github/workflows/core.yml             | 104 ---------------------------------
 .github/workflows/dep-audit.yml        |  44 --------------
 .github/workflows/security.yml         |  20 -------
 .github/workflows/skill-gate.yml       |  71 ----------------------
 .github/workflows/web.yml              |  55 -----------------
 docs/ops/ci.md                         |  39 +++++++++++++
 scripts/announce-release.sh            |  65 +++++++++++++++++++++
 scripts/install-smoke.sh               |  52 +++++++++++++++++
 scripts/verify-no-workflows.sh         |  12 ++++
 11 files changed, 168 insertions(+), 409 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `b9e26bcc-73ef-44a6-9ce9-4d3b3973b100`._
