---
name: review-tsukumo
description: fullstack-lead's self-review gate for the tsukumo SITE + lead-machine + dokan-infra lane. Run as the LAST step before opening a PR / completing a task, on YOUR OWN diff. A real checklist of THIS lane's hard constraints (secrets server-only, RLS deny-all, relay call_tool transport, dokan governance, lead-machine 0-send/commitTwenty, Tsukumo=center, copy-gate), not a rubber stamp. High-signal only. Use when finishing a fullstack-lead change in trovex web/api, tsukumo app/api, a dokan script, or the lead pipeline.
metadata:
  author: fullstack-lead
  version: "1.0.0"
---

# review-tsukumo — fullstack-lead lane self-review gate

Run from INSIDE your worktree, as the LAST step before PR/`complete_task`. Goal: catch the
high-signal, lane-specific failures in YOUR diff before CTO/cmo sees it. Fix any ❌ before shipping.

Lane = tsukumo SITE (Next.js `app/`) + the **lead-machine** (Supabase funnel + Twenty + dokan
pipeline) + **dokan infra** (scripts/monitors) + trovex `web/` + `web/api/`. North star: Tsukumo
consulting leads. The checks below are ordered cheap→deep.

## Step 0 — Diff sanity
```bash
git status                      # only files you meant to change
git --no-pager diff --stat main...HEAD
git --no-pager diff main...HEAD | wc -l   # atomic task ≈ <500 LoC
```
Surprise file / repo-wide whitespace → fix before continuing.

## Step 1 — SECRET LEAK (hard gate, the #1 lane risk)
Supabase **service_role** + any server token (TWENTY_API_KEY, OPENAI_API_KEY, RESEND, CALENDLY_API_TOKEN)
are SERVER-ONLY: never in client code, never `NEXT_PUBLIC_*`, never committed.
```bash
# a secret assigned in the diff:
git --no-pager diff main...HEAD | grep -iE "^\+.*(service_role|SUPABASE_SERVICE_ROLE|TWENTY_API_KEY|OPENAI_API_KEY|RESEND_API_KEY|CALENDLY_API_TOKEN)\s*[:=]" | head
# a server secret leaking into a PUBLIC var / client bundle:
git --no-pager diff main...HEAD | grep -iE "^\+.*NEXT_PUBLIC_[A-Z_]*(SERVICE_ROLE|SECRET|TOKEN|API_KEY)" | head
# a real key value committed (JWT / sk- / re_):
git --no-pager diff main...HEAD | grep -iE "^\+.*(eyJ[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{20,}|re_[A-Za-z0-9]{20,})" | head
```
ANY hit on a server secret → ❌ STOP, redesign server-side, rotate if it was real.
NOTE: an **IndexNow key is PUBLIC by design** (keyfile = the auth) — fine inline. A Calendly/Supabase/Twenty token is NOT.

## Step 2 — Build / syntax smoke (must exit 0)
```bash
# tsukumo Next.js change:
cd ~/Projects/tsukumo && npm run build 2>&1 | tail -6
# trovex web change:
cd ~/Projects/trovex && (npm run build 2>&1 | tail -6)   # or the repo's build
# a dokan script (.mjs) or any node:
node --check growth/automation/<script>.mjs && echo "syntax OK"
```

## Step 3 — Lane invariants (check the ones your diff touches)

### 3.1 Supabase / RLS (funnel DB)
- Writes go through a **server route** with the service-role key — never the browser.
- RLS stays deny-all on `leads` / `waitlist` / `newsletter` / `applications` (no public policy added).
- New table holding PII/inquiries → RLS ON + no anon policy. (The weekly `secret-leak-rls-scan` 425 enforces this in prod — don't regress it.)
- No PII in logs; capture `source`/`utm`/`referer` for attribution.

### 3.2 Relay from a dokan script (transport gotcha)
The relay MCP is a **`call_tool` DISPATCHER** — a raw `tools/call name:'send_message'` returns
**-32602 'tool not found'**. Any dokan script posting to the board MUST wrap:
```js
{ method:'tools/call', params:{ name:'call_tool', arguments:{ tool:'send_message', args:{project,as,to,...} } } }
```
Reach the relay at `host.docker.internal:8090` (loopback-exempt; gateway 172.17.0.1 is refused).
```bash
git --no-pager diff main...HEAD | grep -E "name:\s*'send_message'" && echo "⚠️ direct tool name — must be call_tool dispatcher"
```

### 3.3 dokan governance (every script you create/own)
- TESTED live (`run_script`, exit 0, captured run_id) BEFORE schedule. Untested ≠ done.
- P0-24h self-receipt sent via relay (verbatim response + run_id).
- **zero-local**: it runs in dokan, not a local cron/launchd; the `.mjs` in git is a review mirror only.
- tagged `created_by:'fullstack-lead'` + the catalogue (trovex `9356bddc`) row updated.
- Scheduled MONITOR exits 0 + emits `::dokan:result::` (nonzero exit shows red/"failed").
- Source mirror in git == the uploaded dokan source (don't let them drift).

### 3.4 Lead-machine (hand-raiser 395 / Calendly / Twenty)
- **0 SEND invariant**: the pipeline drafts + writes the CRM; it NEVER emails/DMs the prospect.
- `commitTwenty` gate respected (false = plan-only). Live CRM write only when owner-approved.
- Twenty: 3-state email dedup (found/absent/unknown — only "absent" creates); note-idempotency
  (skip if a 'Setter draft' Note exists). tier is written by analytics scorer 422, NOT by 395.
- **Tsukumo = center**: booking/conversion → `tsukumo.ch` (e.g. tsukumo.ch/book), NEVER `trovex.dev/booked`.
  Products (trovex/wrai.th/yoru/dokan) = top-of-funnel that drain to Tsukumo consulting.

### 3.5 Versioning (if you touched versions/release)
versions.ts → manifest → tag → GitHub Release order; don't hand-edit a version out of band.

## Step 4 — COPY GATE (do NOT self-grade prose)
If the diff changes ANY human-facing copy (hero/landing/answers/blog/FAQ/meta/OG/CTA/microcopy):
**STOP** — that's marketing-owned. Requires (1) a named marketing author, (2) the `anti-ai-slop`
skill run by a NON-AUTHOR. You build the SURFACE (render/plumbing/JSON-LD/og-render), not the WORDS.
Rendering-only diff = fine. Copy strings inside = route to the content owner.

## Step 5 — Logic self-audit (read your full diff once)
1. Happy path actually works if run now?
2. One edge case (empty input / missing field / zero rows / API non-200) → loud-fail, not silent-wrong?
3. Broke an existing contract (renamed field / changed return shape / route signature)? Search callers:
   `git grep "<old-name>" -- '*.ts' '*.tsx' '*.js' '*.mjs' '*.py' | head`

## Step 6 — Verdict (one line in the PR body / completion summary)
- ✅ ship — all applicable checks green, diff narrow
- ⚠️ ship-with-note — minor/pre-existing issue noted
- ❌ fix — real finding; fix + re-run the relevant check
Format: `<desc> — branch <name> — review-tsukumo: ✅ ship (N files)`

## Merge routing (eng policy)
- **Self-merge** ONLY: isolated + single-lane + green (incl `core` CI) + no schema push + no prod deploy
  + no release tag + no cross-lane/shared file + no human-facing copy.
- **PR-to-CTO**: schema/migration, prod deploy, release tag, cross-lane surface, trunk-RED risk,
  human-facing copy, AND **any skill change** (shared fleet tooling).

## Anti-patterns
- Don't rubber-stamp — if a check doesn't apply, say so explicitly; don't skip a check that does.
- Don't self-grade copy (Step 4). Don't auto-post GH review comments (that's CTO's pr-review-merge).
- Don't schedule an untested dokan script. Don't let the git mirror drift from the dokan source.
- One pass. Fix real findings, ship. Nitpicks stay silent.
