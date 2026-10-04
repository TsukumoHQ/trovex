# [trovex/deploy] /graph mounts in deploy: build:graph runs in the deploy path + documented

## Team : trovex-frontend (tsukumo)
## Branch : feat/trovex-deploy-graph (from dev)
## Relay task : f366c750-6dfd-4f21-bd2c-3be66641ed0f
## Trace : trace=74cd2f7293fb1145baee1e2256b2db9b
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. deploy path runs build:graph (file:line)
- [ ] 2. README/DEPLOY documents it
- [ ] 3. receipt (pre-merge, from the branch): run the deploy build into a scratch tree and `trovex serve` on a spare port; curl -s -o /dev/null -w %{http_code} localhost:<port>/graph/ = 200

## 2. Root cause & decisions

# Decision — [trovex/deploy] /graph mounts in deploy (task f366c750)

ROOT_CAUSE: `src/trovex/server.py` mounts `/graph` only when `web/dist-graph/`
exists (same build-less-tolerant contract as `/receipt`), but no deploy path ever
built the graph SPA. `deploy/serve-trovex.sh` refreshed the Python server (`uv
sync`) and relaunched it, and `deploy/trovex.service` only `ExecStart`s uvicorn —
neither ran `npm run build:graph`. So `web/dist-graph/` never existed on a deployed
tree and prod `/graph` returned 404 forever. (Surfaced as the L4 residual FYI.)

## Decision
Add `deploy/build-graph.sh` as the single canonical build step
(`npm ci && npm run build:graph` in `web/`, output `web/dist-graph`). Wire it into
the macOS fleet-host launcher (`serve-trovex.sh` refresh block) best-effort, and
document the Linux systemd update step. Private `/graph` doc lives in
`deploy/README.md` (operator-facing), not the public marketing README.

## Why best-effort (not fatal)
The server must still come up if the web build hiccups or `npm` is absent — exactly
the build-less tolerance server.py already encodes. So `build-graph.sh` itself exits
non-zero on a real build failure (detectable/testable), but callers invoke it
best-effort: `serve-trovex.sh` warns-and-continues; `trovex.service` would use
`ExecStartPre=-` — except it can't build at all (see below).

## Rejected alternatives
- **ExecStartPre build in trovex.service (Linux):** rejected. The unit is hardened
  with `ProtectHome=read-only` + a narrow `ReadWritePaths`; a build-at-start (npm
  writing `node_modules`/`web/dist-graph` under `/home`) is blocked. Adding the repo
  to `ReadWritePaths` would hand npm arbitrary write under home and gut the
  hardening for a private view. Chose: build at the update step, documented.
- **Document in root README.md:** rejected. Root README is public/marketing; `/graph`
  is a private internal view. Documented in `deploy/README.md` instead. (Reading of
  the ambiguous "README/DEPLOY" AC — picked the operator doc; noted to lead.)
- **Fold `build:graph` into the main `build` script:** rejected. That is the
  separate marketing build (base `/`); the graph build is a distinct config
  (base `/graph/`, `vite.graph.config.ts`). Keeping them separate is intentional.

## Receipt
`curl -s -o /dev/null -w '%{http_code}' localhost:8799/graph/` = **200** on a tree
built via `deploy/build-graph.sh`; `/api/graph` = 200; `/graph` → 307 → `/graph/`.
Full suite: `993 passed`. New: `tests/test_deploy_graph.py` (6 passed).

## review-trovex verdict: SHIP
review-trovex: ✅ ship — 5 files / +164 LoC (deploy scripts + deploy/README.md + 1 test) — gate green (ruff clean on src+tests; full pytest 993 passed, +6 new in test_deploy_graph.py). No src/ or Active-Memory change. No secret/brand/host leak (scripts use localhost:8765; no synergix/ctx). deploy/README.md covered by the `README.md` .trovexignore glob. Base = origin/dev (not main): the /graph code only exists on dev, and the task target is dev. Deploy-path/shared surface → PR-to-cto (not self-merge), submitting to gate.

RED_EVIDENCE:
  cmd: uv run pytest tests/test_deploy_graph.py -q  (deploy wiring reverted to cc3e44e, test kept)
  test_sha: 34cae04
  output: |
    E  FileNotFoundError: [Errno 2] No such file or directory: '.../deploy/README.md'
    FAILED tests/test_deploy_graph.py::test_build_graph_script_exists_and_is_executable
    FAILED tests/test_deploy_graph.py::test_build_graph_runs_build_graph_npm_script
    FAILED tests/test_deploy_graph.py::test_serve_trovex_refresh_builds_graph
    FAILED tests/test_deploy_graph.py::test_systemd_unit_documents_graph_build
    FAILED tests/test_deploy_graph.py::test_deploy_readme_documents_graph
    5 failed, 1 passed in 0.21s

## presubmit waiver
cto-tsukumo granted NIWA_PRESUBMIT_CHECK=0 for THIS submit (msg c4f9ee5b): host freeze SIGTERMs `make test`. Hand bar = standalone green above (993 passed, ruff clean, /graph/=200). Gate review + post-merge still run.

## presubmit waiver (round 4, P1 priority re-fire)
CHECK=0: presubmit 1200s cap under host load 40+, cto waiver 00:37Z, manual pytest 997 passed.
Evidence: `uv run --extra dev python -m pytest -q` in this worktree = 997 passed, 1 warning, 196.44s (2026-10-04T00:3xZ). Same tip (898cc65). cto set ticket verify_cmd so the gate runs pytest itself post-submit.

## 3. Files changed

```
.niwa/receipts/f366c750-graph.txt                  |  80 +++++++++++++++
 deploy/README.md                                   |  39 ++++++++
 deploy/build-graph.sh                              |  53 ++++++++++
 deploy/serve-trovex.sh                             |   9 ++
 deploy/trovex.service                              |   6 ++
 ...-build-graph-runs-in-the-deploy-path-documen.md | 108 +++++++++++++++++++++
 tests/test_deploy_graph.py                         |  57 +++++++++++
 7 files changed, 352 insertions(+)
```

## 4. QA Log

### Round 2 — ❌ REJECTED by human:cto-tsukumo

### Round 5 — ❌ REJECTED by review-f366c750-6dfd-4f21-bd2c-3be66641ed0f
- 🟢 AC1: Deploy path on macOS fleet-host refresh is wired and calls build:graph; the textual tests lock the wiring. Independently re-ran in scratch tree (/tmp/receipt-scratch, cleaned up): build-graph.sh succeeded -> web/dist-graph/index.html built. — evidence: deploy/serve-trovex.sh:170 invokes bash $(dirname $0)/build-graph.sh inside the refresh block; deploy/build-graph.sh:47 runs `npm run build:graph`; web/package.json:23 defines `build:graph` as `tsc -b && vite build --config vite.graph.config.ts && node -e renameSync(dist-graph/graph.html, dist-graph/index.html)` (emits web/dist-graph/index.html). End-to-end chain: serve-trovex.sh refresh -> build-graph.sh -> npm run build:graph -> vite -> web/dist-graph -> server.py:526 mount /graph. — test: tests/test_deploy_graph.py::test_serve_trovex_refresh_builds_graph (L39-43) + test_build_graph_runs_build_graph_npm_script (L26-29) + test_build_graph_is_a_real_npm_script (L32-36); also test_build_graph_script_exists_and_is_executable (L19-23). All 6 in tests/test_deploy_graph.py pass (`pytest tests/test_deploy_graph.py -v` = 6 passed).
- 🟢 AC2: Both README surfaces document the /graph build step. AC explicitly says 'README/DEPLOY documents it' - deploy/README.md is the operator doc, deploy/trovex.service carries the inline unit comment. — evidence: deploy/README.md:1-39 (new, 39 lines) documents the /graph build step end-to-end (the contract, the macOS + Linux update flow, the curl verify line). deploy/trovex.service:20-25 (added comment block above ExecStart) documents why build-at-start is blocked by ProtectHome=read-only and what the update operator must run. — test: tests/test_deploy_graph.py::test_deploy_readme_documents_graph (L53-57) + test_systemd_unit_documents_graph_build (L46-50). Both pass.
- 🔴 AC3: Brief hard rule: receipt-bearing criterion is green ONLY if doer COMMITTED the receipt artifact on the branch under .niwa/receipts/<file>. None exists for f366c750 / trovex-deploy-graph. The .niwa/receipts/* present are L4 screenshots, not AC3's required curl /graph/=200 transcript. — evidence: No receipt artifact committed on branch under .niwa/receipts/<file> for task f366c750. `git ls-tree -r HEAD | grep -iE f366c750|deploy-graph` under .niwa/ finds nothing new - only the prior L4 task's 4 jpgs + README (committed by 4958228 feat/trovex-links-l4 for task 266ebd6e). No sha on origin/dev...HEAD adds a curl transcript for /graph/=200. Receipt-bearing AC3 is hard-required to cite receipt=<file> from the branch; absent that, AC3 = RED regardless of test green. Behaviorally verified in /tmp/receipt-scratch (since cleaned): bash deploy/build-graph.sh emitted web/dist-graph/index.html; uv sync + .venv/bin/trovex serve --host 127.0.0.1 --port 8799 came up; curl -s -o /dev/null -w '%{http_code}' localhost:8799/graph/ = 200, /graph = 307 (redirect to /graph/), /healthz = 200 - but doer did NOT commit this transcript. — test: NONE - no committed receipt artifact under .niwa/receipts/ for this task. The new textual tests (test_deploy_graph.py) cannot satisfy a receipt-bearing criterion per the brief.

## 5. Timeline

- round 2 → **reject** (human:cto-tsukumo)
- round 5 → **reject** (review-f366c750-6dfd-4f21-bd2c-3be66641ed0f)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `f366c750-6dfd-4f21-bd2c-3be66641ed0f`._
