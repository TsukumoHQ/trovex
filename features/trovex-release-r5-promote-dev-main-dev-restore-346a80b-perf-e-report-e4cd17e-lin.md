# [trovex/release r5] promote dev -> main (dev restore 346a80b, perf-e report e4cd17e, links L2 follow-up 0435625) so the live :8765 deploy picks them up

## Team : trovex-backend-2 (tsukumo)
## Branch : trovex-backend/release-r5 (from dev)
## Relay task : 63ef1f3a-bbdc-49f2-8595-0e314528b9f8
## Trace : trace=06ce02202d571a90788dab7ce2ade3fb
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. origin/main after merge contains every commit of origin/main 56aebc0 and of origin/dev 0435625 (git merge-base checks in the submit note)
- [ ] 2. full trovex test suite green on the merged tree (count in the note)
- [ ] 3. post-deploy: /api/stats total > 0 and a trovex_read round-trip works on :8765

## 2. Root cause & decisions

# [trovex/release r5] promote dev -> main (task 63ef1f3a)

ROOT_CAUSE: live :8765 deploys origin/main (deploy/serve-trovex.sh), but origin/main (56aebc0, r4) lags origin/dev (189d7fe) — perf A/C/D/E, boot empty-pack fix, links L1-L5 + L2 follow-up, and the suite-speed fix (38c5c8a0) never reach the live deploy until main is advanced. r5 promotes dev -> main.

## Designed release path (cto ruling c1d5327d, no gate-weakening)
niwa's release mechanism is `niwa promote` (fast-forward main up to dev), which needs main to be an ancestor of dev. The release-rN commits on main are SQUASHes, so main is NOT yet an ancestor of dev. To fix that without a RED_EVIDENCE fight:
1. This submit: a merge commit (a7c5933, parents [56aebc0 main, 189d7fe dev]) whose TREE == origin/dev, submitted to target DEV. Its dev-diff is a single file (features/trovex-release-r4-...md, the r4 note the merge keeps from main) — no src, no test files -> RED_EVIDENCE not applicable; it is a chore. Landing it on dev makes 56aebc0 (main) an ancestor of dev.
2. Then from a clean checkout: `niwa promote --repo ~/Projects/trovex` dry-run, then --execute if gate empty + fast-forward + green. That advances main up to dev (now carrying everything), no RED rule on the ff promote.

## Verification
- Merge tree == origin/dev @ 189d7fe: staged src/tests/pyproject/uv.lock vs origin/dev is empty; blob of config.py matches origin/dev (ad8371d0, matches dev). Conflicts (11 files) were squash-history artifacts, resolved `--theirs` (dev); main carries zero source outside dev history (`git log origin/dev..origin/main -- src tests` empty).
- Ancestry: 56aebc0 (main) ancestor of HEAD -> YES; origin/dev (189d7fe) ancestor of HEAD -> YES.
- Full suite already green on dev (gate ran 38c5c8a0 at 1052 passed / 111.49s). This promote adds no code vs dev.
- Behaviour change expected: none except perf-D's opt-in static path (default OFF, config.py:148 static_embed_enabled=False) and _link_hint debug logs. Scope B (perf-D included) cto-approved (msg a9415fee).
- Preconditions (ticket-required): `git merge-base --is-ancestor 8b59dd6 origin/dev` YES; src/trovex/links_parse.py on dev YES; dev not rewound.

## review-trovex verdict: SHIP
review-trovex: ✅ SHIP — dev-diff = 1 .md (no src/test) — promote of already-gated dev code, tree byte-identical to origin/dev (189d7fe); no behaviour change, no secret/brand/host/number issue, no bar-weakening. Release = gate/promote (cto-owned), submitted via the designed dev-target path.

## Rejected alternatives
- Submit merge to target MAIN directly: the diff then carries dev's test files and the RED_EVIDENCE gate demands a failed-before block for a promote whose tests are already gated on dev. cto refused flag-flip/hand-merge; the dev-target path avoids it cleanly.
- Exclude perf-D (promote only 0435625): rejected, cto approved scope B; perf-D is merged, default-OFF, and stranding it forces a needless r6.

## Incident note (no code impact)
.worktrees/trovex-backend-2 is a broken empty stub (gate-cleaned, no .git); an early merge/reset accidentally ran against the MAIN repo checkout, was caught, main repo restored to branch dev, stray branch deleted. All r5 work is in .worktrees/release-r5 [trovex-backend/release-r5].

## 3. Files changed

```
...erf-a-235ea54-perf-c-8b59dd6-boot-empty-pack.md | 87 ++++++++++++++++++++++
 ...ev-restore-346a80b-perf-e-report-e4cd17e-lin.md | 63 ++++++++++++++++
 2 files changed, 150 insertions(+)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-63ef1f3a-bbdc-49f2-8595-0e314528b9f8
- 🟢 AC1: Both required commits are present in the release-r5 history. The doer's only tree change vs origin/dev is one documentation file, so the merged tree is identical to origin/dev - a clean fast-forward promotion. — evidence: git merge-base --is-ancestor 56aebc0 66bb575 -> IS ancestor; git merge-base --is-ancestor 0435625 66bb575 -> IS ancestor. Release-r5 tip 66bb575 sits on merge 8d27f3c (parents: 56aebc0 + 525b5e9/dev); 0435625 is an ancestor of 525b5e9. After the cto merges 8d27f3c to origin/main, main contains both 56aebc0 (parent 1) and the dev tip 525b5e9 (parent 2), hence all of dev including 0435625. — test: N/A - AC is a structural git-ancestry invariant; the verifying test is the merge itself (commit 8d27f3c merge of 56aebc0+525b5e9) and the ancestor check `git merge-base --is-ancestor 0435625 66bb575` returning true.
- 🟢 AC2: Full suite green on the merged tree. The original machine-verify line was a config-args mistake (missing --extra dev) and not a code defect. — evidence: Ran `uv run --extra dev python -m pytest -q` in the review worktree (at the release-r5 tip 66bb575 / the merged tree). Output: '1052 passed, 3 warnings in 102.30s'. The previous machine-verify line (exit=4, 'unrecognized arguments: -n --dist') failed because it ran `uv run pytest -q` without `--extra dev`; with the dev extras the pytest-xdist plugin is present and the suite is fully green. The 1052 count is consistent with the r4 receipt's 1035 plus new tests shipped on dev between r4 and r5. — test: tests/test_server.py 61 test_ functions; tests/test_wal_wedge.py; tests/test_wedge_class2_recurrence.py; tests/test_active_memory.py; tests/test_links_parse.py (99 lines, added in merge). All 1052 tests pass.
- 🟢 AC3: /api/stats total=5176 (>0) and a write+search round-trip returns the captured doc. Live :8765 is up and serving the post-merge state correctly. — evidence: Live curl against http://localhost:8765: GET /healthz -> 'ok'; GET /api/stats -> {total:5176,total_tokens:12076064,...} (total > 0); POST /api/capture with body {agent:'qa-reviewer-r5',summary:'# QA review probe r5...'} -> {captured:true,doc_id:'owner-qa-reviewer-r5-current-state',tokens:34,decision:'verbatim'}; GET /api/search?q=QA+review+probe+r5&k=3 -> the just-captured doc is the top hit (path='owner-qa-reviewer-r5-current-state', score=0.0333). Round-trip works end-to-end on :8765 with the post-merge tree. — test: The live server is the verifying test for the deployed behavior: /api/stats is asserted by GET /api/stats returning total>0; the trovex_read round-trip is asserted by capture+search returning the just-captured doc as the top result. In-tree, the analogous offline tests are tests/test_server.py:959 test_healthz_ok_when_store_populated and tests/test_server.py:1319 test_api_boot_normal_path_is_dense_not_static.

### Round 2 — ❌ REJECTED by review-63ef1f3a-bbdc-49f2-8595-0e314528b9f8
- 🟢 AC1: origin/main 56aebc0 and origin/dev 0435625 both sit inside the a7c5933 r5 promote merge, and the round-2 fix 189d7fe plus the rest of r5 are present. — evidence: git merge-base --is-ancestor 56aebc0 a7c5933=YES; --is-ancestor 0435625 a7c5933=YES; --is-ancestor for 189d7fe (test-deps), 525b5e9 (suite-speed), 235ea54 (perf A), e4cd17e (perf E), 346a80b (dev restore) all YES; r5 promote Merge: 56aebc0 189d7fe — test: the merge topology is the verifying check for the ancestry claim; runtime footprint covered by the AC2 full-suite run on the merged tree
- 🟢 AC2: Round-1 RED (uv run pytest -q exit 4 — unrecognized arguments -n --dist) is fixed: pyproject.toml:87-95 adds [dependency-groups].dev holding pytest-xdist, uv 0.11.7 auto-syncs the default group on uv run. Confirmed fresh-venv -> 1052 tests collected and the full run finishing in 100.41s under the 900s cap. Diff carries no test files; pure dep-group plumbing. — evidence: rm -rf .venv && uv run pytest -q (bare command at HEAD 65ca7f1) -> 1052 passed, 3 warnings in 100.41s exit 0; --collect-only reported 1052 tests collected with addopts -n 3 --dist worksteal now recognised; uv run ruff check src tests -> All checks passed! — test: the suite itself IS the verifying test (no test added/removed/weakened by the round-2 delta — 189d7fe only touches pyproject.toml, uv.lock, features/...md); pre-existing test_wedge_class2_recurrence.test_api_stats_stays_off_loop + test_server.test_api_boot_and_search_200_over_4096_docs cover the runtime routes AC3 hits
- 🟢 AC3: Live :8765 is serving the post-promote tree: /api/stats total=5186 (>0, sources populated) and /api/search returns the round-2 provenance doc plus the suite-speed/test-deps neighbourhood — trovex_read round-trip works. /api/capture returns {captured:false, reason:no agent} which is the daemon expected write-gate refusal, not a regression. — evidence: curl -sf http://localhost:8765/api/stats: total=5186 (>0, 5 sources populated); curl -G /api/search --data-urlencode q=review test deps trovex round 2 returns 3 relevant docs including qa-verdict-36e3a08b-r1 and features/trovex-suite-speed-... — round-trip read matches the round-2 surface — test: tests/test_wedge_class2_recurrence.py::test_api_stats_stays_off_loop and tests/test_server.py::test_api_boot_and_search_200_over_4096_docs + test_server.py::test_api_search_scopes_by_kind_and_tags exercise /api/stats + /api/search — same routes the live :8765 AC3 probes, all green in the 1052-pass run

## 5. Timeline

- round 1 → **reject** (review-63ef1f3a-bbdc-49f2-8595-0e314528b9f8)
- round 2 → **reject** (review-63ef1f3a-bbdc-49f2-8595-0e314528b9f8)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `63ef1f3a-bbdc-49f2-8595-0e314528b9f8`._
