# CI on this repo

trovex is a private TsukumoHQ repo. GitHub Actions minutes on private repos are
billed, and standing up a self-hosted runner just to avoid that bill was
rejected by the founder (task 819445bf, 2026-09-26: "je vois pas pourquoi
runner CI ? au pire on la met juste pas" — don't run CI here at all).

**The niwa review gate is the CI.** Every change lands through
`~/.agentd/agent-hook.sh qa-submit`, which spawns an adversarial reviewer that
runs the test suite before a merge is allowed. There is no `.github/workflows`
testing/lint/gate pipeline on this repo anymore.

## What's kept

- **`.github/workflows/publish-mcp.yml`** — tag-push (`v*`) publish to PyPI
  (Trusted Publishing) and the MCP Registry, authenticated via GitHub Actions
  OIDC (`id-token: write`). This can't move off Actions: the whole point is a
  keyless trust handshake that only GitHub's OIDC issuer can do. This is the
  one workflow still running here.

## What was dropped, and where it went

| Old workflow | What it did | Now |
|---|---|---|
| `core.yml` | `ruff check` + `pytest -q` + `pip-audit` on every PR/push to main | `pytest -q` is what the gate reviewer runs before approving; `ruff check` is part of that same command in this repo's dev loop. No separate CI needed. |
| `web.yml` (build+lint+typecheck+test) | `npm run build` on every PR/push to `web/` | `npm run build` already chains lint, typecheck, `vitest run`, and every brand/sitemap/pii/voice/analytics guard (see `web/package.json`) — this is what the gate runs, not a GitHub Action. |
| `web.yml` (indexnow job) | Ping IndexNow with the sitemap after a prod deploy | `npm run indexnow` (`web/scripts/indexnow-ping.mjs`) still exists — run it by hand after a prod deploy, or wire it to a Vercel deploy hook later. |
| `brand.yml` | `python3 scripts/brand_guard.py` on every PR | Already redundant: `tests/test_brand_guard.py::test_live_repo_scans_clean` calls `brand_guard.scan()` against the live tree and is part of `pytest -q`. Zero coverage lost. |
| `security.yml` | `python3 scripts/security_guard.py` on every PR | Same as brand: `tests/test_security_guard.py::test_live_repo_scans_clean` already runs the real scan inside `pytest -q`. Zero coverage lost. |
| `skill-gate.yml` | Required a `review-<lane>` verdict block in the PR body | Superseded by the niwa QA gate, which already requires and checks its own verdict (`.niwa-decision.md`) before merge — a second, weaker check on the PR body text is redundant. |
| `core.yml` (`install-smoke` job) | Cold-install activation gate: build the wheel, install it in a clean venv, run `trovex setup` (twice, checking idempotency) | Folded into `scripts/install-smoke.sh` — run it by hand before tagging a release. |
| `announce-release.yml` | Post a Discord release announcement on a published tag | Folded into `scripts/announce-release.sh` — run it by hand (`TAG=vX.Y.Z bash scripts/announce-release.sh`) right after publishing the GitHub Release. |
| `dep-audit.yml` | Daily cron: `pip-audit` + `npm audit --audit-level=high`, independent of any PR | **Dropped, no replacement.** This was the only check that ran without a human opening a PR (catching a CVE disclosed against an already-merged dependency). Accepted risk per the founder's Actions-off call; re-add as a dokan daily schedule if a real CVE gap bites us. |
| `uptime.yml` | N/A — this repo never had one | — |

## Public repos

WRAI.TH, dokan, and yoru are public — GitHub Actions minutes there are free.
Their workflows are untouched.
