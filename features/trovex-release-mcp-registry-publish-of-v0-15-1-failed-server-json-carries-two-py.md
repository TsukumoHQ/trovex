# [trovex/release] MCP registry publish of v0.15.1 failed: server.json carries two pypi package entries and publish-mcp.yml syncs only packages[0].version, so the registry validated 'trovex 0.13.4' (404) — sync every package, fix the committed versions, pin with a test

## Team : trovex-backend (tsukumo)
## Branch : fix/registry-version-sync (from dev)
## Relay task : 5c18adb7-aa8d-41d8-9264-80a59dc9dcc0
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
- [ ] 1. publish-mcp.yml syncs every packages[].version and the top-level version to the tag, and fails loudly if any package version still differs after the sync
- [ ] 2. server.json has one entry per real artifact (duplicate removed or justified in the PR body), all versions = 0.15.1
- [ ] 3. pinned test: all packages[].version == .version; pinned test of the sync command on a fixture
- [ ] 4. make test green; review-trovex verdict in the PR body; submitted through the gate against dev

## 2. Root cause & decisions

ROOT_CAUSE: publish-mcp.yml's release-tag sync step ran `jq '.version = $v | .packages[0].version = $v'` — only `packages[0]` got the new version; server.json legitimately lists TWO `packages[]` entries (stdio transport, added 8cf4688 "trovex mcp — serve MCP over stdio", and streamable-http transport, the original) for the SAME PyPI package, both real, not a duplicate (confirmed via `git log -p` on server.json). `packages[1]` silently kept whatever was last hand-committed. Committed server.json had `0.13.4` from task 7111f05a round 2 — a guessed version I derived from the reviewer's rejection text without cross-checking the actual latest PyPI/tag state, which was already at 0.15.0. v0.15.1 tagged, PyPI step succeeded (hatch-vcs correctly builds from the tag regardless of server.json), but the MCP Registry step ran `jq` against packages[1] still reading 0.13.4 (never actually published to PyPI) -> 400.

DECISION: (1) fix the sync filter to `.packages[].version = $v` (every entry) and add a fail-loud verification step right after — re-reads the synced file and `exit 1`s if `.version` or any `.packages[].version` still differs from the tag, so a future shape change here breaks CI, not a live release. (2) Committed server.json: `.version` and both `.packages[].version` = `0.15.1` (the tag that actually shipped what's on dev right now). (3) `src/trovex/__init__.py`'s `__version__` = `0.15.1` too, matching. (4) Kept both packages[] entries — real, distinct transports, not a duplicate.

Round 1's test_version_consistency.py (7111f05a) anchored its check on CHANGELOG.md's top `## X.Y.Z` heading as ground truth. That test technically "passed" this round too (server.json/__init__.py DID agree with what I'd written in CHANGELOG.md) — the failure was CHANGELOG.md's OWN claimed number being wrong, which no self-referential test can catch. REPLACED that anchor: the blocking tests now check SELF-consistency only (every `packages[].version == server.json.version`, `__init__.py == server.json.version`) — exactly AC's literal wording ("every packages[].version equals .version") and exactly the invariant that broke. CHANGELOG.md stays pure documentation, no longer a test dependency, and its `## 0.13.4` entry is corrected to `## 0.15.1` (the tag that really carried the onboarding fix) with a note explaining the mislabel, plus a new `## Unreleased` entry for this fix.

New pinned test (AC's 2nd half) extracts the ACTUAL jq filter string from publish-mcp.yml via regex (not a hand-copied duplicate that could itself drift) and runs it through real `jq` against a 3-package fixture with a fake tag, asserting every entry updates — this is what directly pins the workflow bug, independent of whatever server.json happens to contain at any given moment. Skips gracefully if `jq` isn't on PATH.

REJECTED ALTERNATIVES:
- Drop the 2nd packages[] entry as "the duplicate": rejected — git history shows it's a deliberate, distinct stdio-transport listing (8cf4688), removing it would break the MCP registry's stdio launch entry for real clients.
- Keep CHANGELOG.md as the blocking test's anchor, just fix its number: rejected — this incident IS what happens when the anchor itself is wrong; a hand-maintained doc is not a safe ground truth for an automated gate. Self-consistency (server.json against itself) is the actual invariant that broke and the actual invariant worth pinning.

V-model: (1) reproduced the live incident directly — set server.json packages[1].version back to '0.13.4' with server.json.version at 0.15.1 -> test_server_json_packages_version_matches_top_level fails with the exact real error shape; restored -> passes. (2) reverted the workflow's jq filter to the original `.packages[0].version` form -> test_publish_mcp_sync_updates_every_package_version fails (`['9.9.9','0.1.0','0.1.0'] != ['9.9.9']*3`); restored -> passes.

make test: 708 passed. ruff clean.

## review-trovex verdict: SHIP
review-trovex: SHIP — 5 files (server.json version bump x3, __init__.py version bump, publish-mcp.yml sync fix + fail-loud check, CHANGELOG.md corrected, tests/test_version_consistency.py restructured off the CHANGELOG anchor to self-consistency + new jq-fixture test) — gate green (ruff clean, pytest 708 passed), no Active-Memory/doc-router surface touched, no secret leak, no contract break, V-model pinned on both the incident's exact shape and the workflow's own bug. cto cuts v0.15.2 after merge per the ticket's DoD.

## 3. Files changed

```
.github/workflows/publish-mcp.yml |  19 ++++++-
 CHANGELOG.md                      |  22 ++++++++-
 server.json                       |   6 +--
 src/trovex/__init__.py            |   2 +-
 tests/test_version_consistency.py | 101 ++++++++++++++++++++++++++++----------
 5 files changed, 117 insertions(+), 33 deletions(-)
```

## 4. QA Log

_(no review round yet)_

## 5. Timeline


---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `5c18adb7-aa8d-41d8-9264-80a59dc9dcc0`._
