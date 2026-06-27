---
name: review-trovex
description: Domain self-review for the trovex lane (Python/FastAPI/sqlite-vec/MCP backend + Vite/React web + the doc-router & Active-Memory subsystem). Run on your OWN diff as the LAST step before posting a PR; paste the verdict in the PR body. Catches the trovex-specific gotchas a generic review misses — gate command, Active-Memory invariants, brand/host leaks, registry case, PyPI immutability, secrets, md-guard/SSOT. Use when you finished a trovex change in a .worktrees/ branch.
metadata:
  author: fullstack-trovex
  version: "1.1.0"
---

# review-trovex — trovex-lane self-review gate

Run from INSIDE your worktree, as the LAST step before the PR. High-signal only — fix real findings, stay silent on nitpicks. Output a one-line verdict for the PR body. One pass, no loops.

## Step 1 — Diff sanity
```bash
git status                       # ONLY the files you meant to change (no stray uv.lock/.next/whitespace)
git diff --stat origin/main...HEAD
git checkout origin/main -- uv.lock 2>/dev/null   # uv runs dirty it; drop unless you meant to change deps
```
Branch must be off **origin/main** (not a stale base — leads' worktrees drift). If the diff surprises you, fix before continuing. Multi-worktree: never let one worktree's change ride in on another's branch.

## Step 2 — The gate (must be green)
```bash
uv run ruff check src tests        # ruff/pytest live in [project.optional-dependencies].dev
uv run pytest -q                   # → CI uses `uv sync --extra dev` (NOT --dev)
```
- `ruff check` + `pytest` is the **temporary gate**. `ruff format --check` is RED tree-wide and DEFERRED to cto's coordinated reflow — do NOT run a format reflow yourself (conflict-bombs live worktrees).
- Tests are **hermetic** (BagEmbedder, no model download). If a test needs a real embedder/OpenAI, it's wrong — mock it. New HTTP route → add a `tests/test_server.py` TestClient test (no `with` lifespan, inject AppState). New capture/boot path → cover it.
- core CI (`.github/workflows/core.yml`) is a REQUIRED check on main. Never post a PR you haven't gated locally.

## Step 3 — Doc-router + Active-Memory invariants (the subsystem that bites)
- **Scope first, score second.** Owner/kind retrieval filters by `tags`/`kind` BEFORE scoring. NEVER gate recall on an absolute score threshold alone (semantic scores cluster ~0.6–0.7; in-domain-absent sits on the floor). `Searcher.search` must widen the knn pool when filters are on.
- **Owner tags are lowercased** on BOTH capture (tag write) and boot (tag query) — a mixed-case agent (`COO`) must recall its own records. Regression-test the case path.
- **Stable doc_id = deterministic upsert** (`owner-<agent>-current-state`) → one canonical record, no dup pile. `trovex_write` blocks near-dup on CREATE, never on UPDATE (doc_id set).
- `/api/search` filters `q,limit,summary,kind,tags`; owner-scoped recall = `/api/boot`; capture = `/api/capture` (free-summary verbatim; transcript path distils via BYOK LLM, best-effort, never raises into the agent).

## Step 4 — Secrets, brand, host, numbers (public-surface red flags)
```bash
git diff origin/main...HEAD | grep -iE '^\+.*(sk-|api[_-]?key|write[_-]?token|password|secret)\s*[:=]'
git diff origin/main...HEAD | grep -iE '^\+.*(synergix|Synergix-lab|\bctx\b)'        # brand/leak on public surfaces
git diff origin/main...HEAD | grep -nE '^\+.*(TODO|FIXME|print\(|console\.log)'
```
- **Secrets server-only.** OpenAI key / write-token never in client, git, logs, or echoed back. BYOK via `X-TROVEX-*` headers; the rerank key lives in a context var, not committed.
- **Brand:** lowercase `trovex` wordmark; NO `synergix`/`ctx`/`Synergix-lab` on public surfaces (README, web/, src/trovex/templates, repo meta). Run `cd web && node scripts/check-brand.mjs`.
- **Host = local-first.** User-facing MCP config / hook URLs = `http://localhost:8765` (the user runs their own `trovex serve`). `trovex.prod.synergix.ch` is owner private-infra — never in user-facing copy.
- **Registry/PyPI release:** `server.json name` + the README `mcp-name` marker = `io.github.TsukumoHQ/trovex` — EXACT org case (the registry grant is case-sensitive). PyPI is IMMUTABLE: any change to a published artifact (incl. README long-desc) needs a version bump. A pushed tag runs ONLY the workflows present in the tagged commit.
- **No fabricated numbers.** The `~60%` savings claim ships only with a real measured method; never invent an `Nx`/`%`. (Marketing copy itself = non-author gate; you build the surface, not the words.)

## Step 5 — md-guard / SSOT
- New `.md` on disk → add its path to `.trovexignore` (the PreToolUse guard denies otherwise; note the guard resolves `git -C $(dirname)` so the file's parent dir must already exist). "rien en md, tout dans trovex": records/decisions/post-mortems → `trovex_write(kind=record)`, not a scattered file.

## Step 6 — Logic self-audit (read your full diff once)
1. Happy path: would the new code do what you intended if run right now?
2. One edge case: empty input / missing field / zero rows / unknown agent — loud-fail or silent-wrong?
3. Broke a contract? Renamed a field / changed a return shape? `git grep '<old-name>' -- '*.py'` — update every caller or note the break.

## Step 7 — Merge-policy check (before you post)
- **Self-merge** only if ALL: green gate + isolated + single-lane + no schema + no prod deploy + no release tag + no shared/cross-lane file + no human-facing copy.
- **PR-to-cto** if ANY: schema/migration, prod deploy, release tag/release-adjacent, cross-lane or shared surface (CI config, another lane's files), human-facing copy, or a change that could turn trunk RED.
- TRUNK-GREEN IS SACRED: never merge onto/while RED. Found trunk RED → ping cto, don't pile on.

## Step 8 — Product Q&A (AX self-report — STANDING DUTY, enforced)
You are a FIRST USER of the tools you build/run on (trovex / wrai.th / dokan / yoru). Your friction = the roadmap. Spec = trovex doc `b8e05fa3`; method = `2a0f3aa1` (agent-experience-AX-research).
- **WHEN**: on a CTO "product interview" call → answer THAT tick (don't defer); **and** standing — fold ≥1 *fresh* friction/footgun into your standup DOGFOOD line every cycle. Silence ≠ "no problems".
- **THE RULE**: blunt, friction is the gold, do NOT flatter. **Trace-grounded** — cite a real call / doc-id / error / retry / token-cost; claims must be log-confirmable (cto triangulates vs telemetry). No confabulation — if you can't tie it to evidence, mark `hypothesis`. Flag **"I build this"** on trovex (bias-weight). Name ≥1 thing that works fine (falsify the please-reflex).
- **6 Qs per tool you USE**: (1) JOB — job-to-be-done; (2) WIN — what saves the most; (3) FRICTION — cite the step you worked around; (4) MISSING — the ONE 10x change; (5) FOOTGUN — cite what misled/broke silently; (6) AGENT-LENS — how YOU (an agent, polling on a timer) use it vs a human.
- **SUBMIT**: reply to cto, type `response`, subject `AX Q&A: trovex`. One block per tool; skip tools you didn't use this cycle.

## Self-verdict (paste in the PR body)
- **✅ ship** — gate green, diff narrow, invariants held, no leak/secret/number issue.
- **⚠️ ship-with-note** — minor/pre-existing issue noted (e.g. unrelated pre-existing test).
- **❌ fix** — real issue found; fix + re-run once.

Format: `review-trovex: ✅ ship — <N files, M LoC> — gate green (ruff+pytest), Active-Memory invariants held, no leak/secret`.

## Anti-patterns
- Don't run a `ruff format` reflow (cto-owned, deferred). Don't self-grade product copy (marketing non-author gate). Don't loop the skill. Don't widen scope "while you're in there". Don't merge a cross-lane/release/CI change yourself — that's cto's.
