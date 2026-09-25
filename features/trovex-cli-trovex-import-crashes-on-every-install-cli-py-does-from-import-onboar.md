# [trovex/cli] `trovex import` crashes on every install: cli.py does `from . import onboarding` but src/trovex/onboarding.py was never committed (missing from git, from the 0.13.3 wheel and from the serve worktree)

## Team : trovex-backend (tsukumo)
## Branch : fix/onboarding-module-missing (from dev)
## Relay task : 7111f05a-638d-4ddb-b5bd-189700fe57fb
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. `trovex import <dir> --dry-run` exits 0 on a fixture dir on dev; pinned CLI test
- [ ] 2. pinned test imports every module cli.py references so a missing module fails make test
- [ ] 3. onboarding either exists as a committed module with its own tests or the import and its dead path are removed with a one-line rationale in the PR
- [ ] 4. version bumped to 0.13.4 with a changelog line; make test green; PR carries the review-trovex verdict; submitted through the gate against dev

## 2. Root cause & decisions

ROOT_CAUSE: cli.py's `_scan_dir` (used by both `trovex import` and `trovex onboard`) does `from . import onboarding`, but `src/trovex/onboarding.py` was never committed to git — `git log -S 'onboarding' -- src/trovex/onboarding.py` has zero hits, `git ls-files src/trovex | grep onboarding` is empty on every prior commit, and there's no .gitignore rule hiding it. The module existed only on the original author's machine (an editable install still resolves it from the working tree, so it worked in that one dev environment and nowhere else), so the import has raised `ImportError` for every install since the feature merged — the published 0.13.3 wheel, `uv tool install`, and the fleet's own serve-worktree all hit it identically.

DECISION: keep the feature — `onboarding.py` is real, wanted functionality (both `trovex import` and the guided `trovex onboard` wizard depend on it), not dead code to delete. Write + commit the module (gather/build: walks a directory for .md files, resolves each file's true date via git-first-commit → frontmatter → mtime, derives tags from its folder path, stable ext_id so re-imports update in place instead of duplicating).

Packaging: `[tool.hatch.build.targets.wheel] packages = ["src/trovex"]` already whole-directory-includes the file — this was never a build-config exclusion, purely "never committed", so committing it is the complete packaging fix; no MANIFEST/include-list change needed.

Version (round 1 — WRONG, corrected round 2): I read `[tool.hatch.version] source = "vcs"` as "nothing to bump in-repo" and shipped round 1 without touching any version string. REJECTED — round 1 review found server.json still at 0.13.1 and src/trovex/__init__.py's __version__ still at 0.11.0. Both readings were partially right: the INSTALLED package version genuinely is git-tag-derived and correct at runtime (`trovex --version` reads `importlib.metadata.version("trovex")`, confirmed unaffected) — but server.json (the MCP registry manifest PyPI/registry tooling reads) and __init__.py's __version__ (a public, importable constant) are separate, hand-maintained strings that pyproject's vcs-derived version does NOT touch, and I didn't grep for them round 1. ACTIONABLE, fixed: bumped both to 0.13.4 (server.json's 3 occurrences: top-level + 2 packages[].version; __init__.py's __version__). Added CHANGELOG.md (none existed; added its path to .trovexignore per the md-guard's own instruction, and to pyproject's sdist include list) with a 0.13.4 entry, and made it authoritative: tests/test_version_consistency.py now pins server.json and __init__.py against CHANGELOG.md's top `## X.Y.Z` entry, so the next release forgetting to sync one of these fails `make test` instead of a second review round.

Regression coverage (the part that matters most — this exact class of bug must never ship silently again):
- tests/test_relative_imports.py: AST-walks every `src/trovex/*.py` file for `from . import X` / `from .X import Y` (at any nesting depth — this bug was specifically a lazy import inside a function body, not a top-level one) and actually imports each target, so a missing module or a missing attribute fails `make test` instead of a user's first CLI invocation.
- tests/test_onboarding.py: gather (extension filter, ignore-dirs, empty/oversized skip) + build (title extraction, all three date sources with correct priority git > frontmatter > mtime, stable ext_id across re-imports, tag derivation from folder path).
- tests/test_import_cli.py: `trovex import <fixture> --dry-run` exits 0 end-to-end through the real CLI (CliRunner), the exact repro from the incident report.

make test round 1: 700 passed (1 pre-existing flaky timing test unrelated to this change, cleared in isolation). Round 2 (version fix): 703 passed clean (700 + 2 new version-consistency tests + net files unchanged in count).

V-model on the round-2 fix: reverted __init__.py's __version__ to 0.13.1 — test_init_py_version_matches_changelog failed as expected (0.13.1 != 0.13.4); restored to 0.13.4 — passes.

## review-trovex verdict: SHIP
review-trovex: SHIP — round 2 adds 4 files (server.json version bump, __init__.py version bump, CHANGELOG.md new, tests/test_version_consistency.py new, .trovexignore + pyproject.toml sdist include updated), ~70 LoC — gate green (ruff clean, pytest 703 passed), no Active-Memory/doc-router surface touched, no secret/brand/host leak, no contract change, version drift now pinned by test so it can't silently regress again. Tag v0.13.4 + PyPI publish remain cto-tsukumo's post-merge release step per the ticket — this PR only fixes the in-repo strings the gate correctly flagged as out of sync.

## 3. Files changed

```
.trovexignore                                      |   1 +
 CHANGELOG.md                                       |  15 ++
 ...every-install-cli-py-does-from-import-onboar.md |  54 +++++++
 pyproject.toml                                     |   1 +
 server.json                                        |   6 +-
 src/trovex/__init__.py                             |   2 +-
 src/trovex/onboarding.py                           | 160 +++++++++++++++++++++
 tests/test_import_cli.py                           |  26 ++++
 tests/test_onboarding.py                           | 116 +++++++++++++++
 tests/test_relative_imports.py                     |  63 ++++++++
 tests/test_version_consistency.py                  |  52 +++++++
 11 files changed, 492 insertions(+), 4 deletions(-)
```

## 4. QA Log

### Round 1 — ❌ REJECTED by review-7111f05a-638d-4ddb-b5bd-189700fe57fb
- 🟢 AC1: Pinned CLI test exists and passes — evidence: src/trovex/onboarding.py created; tests/test_import_cli.py:14-26 pins `trovex import <dir> --dry-run` exit=0 on fixture dir — test: test_import_dry_run_exits_zero_on_fixture_dir tests/test_import_cli.py:14
- 🟢 AC2: Missing module would fail `make test` — verified by running, 194/194 pass — evidence: tests/test_relative_imports.py AST-walks all 42 src/trovex/*.py files including lazy imports inside fn bodies; cli.py:887 `from . import onboarding` is covered — test: test_relative_imports.py[cli.py-trovex.onboarding-None] and 193 other parametrized cases, all pass
- 🟢 AC3: Module exists with own tests, all green — evidence: src/trovex/onboarding.py 160 LoC committed; tests/test_onboarding.py 8 tests covering gather/build/date-priority/ext_id stability/tags — test: test_onboarding.py 8 tests pass (test_gather_finds_markdown_ignores_dirs_and_binaries, test_build_frontmatter_date_wins_over_mtime, test_build_git_first_commit_date_wins_over_frontmatter_and_mtime, test_build_ext_id_stable_across_rebuilds, test_build_tags_from_folder_path, etc.)
- 🔴 AC4: ac 4 has 5 components: version bumped to 0.13.4 (NOT DONE), changelog line (NOT DONE — no CHANGELOG.md), make test green (DONE), review-trovex verdict (DONE), submitted through gate (DONE). 2/5 components unmet = partial/red = merge stays gated. — evidence: src/trovex/__init__.py:3 still __version__="0.11.0"; server.json:6 still "version":"0.13.1"; no CHANGELOG.md exists in repo; no git tag v0.13.4 (latest is v0.15.0); pyproject.toml hatch.version=source="vcs" so version comes from git tag, but server.json is hand-bumped per test_server_json_sync docstring and the doer did not bump it — test: NONE — version bump is untested here, doer rationalized skip in feature file claiming release/tag is cto-tsukumo post-merge per ticket scope; make test green ✓ (701 passed), review-trovex verdict SHIP ✓, submitted through gate ✓

## 5. Timeline

- round 1 → **reject** (review-7111f05a-638d-4ddb-b5bd-189700fe57fb)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `7111f05a-638d-4ddb-b5bd-189700fe57fb`._
