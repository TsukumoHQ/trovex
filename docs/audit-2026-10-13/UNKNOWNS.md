# Unknowns register: trovex.dev audit 2026-10-13

Open questions found while fixing TR-01, TR-02, TR-03 and DS-01 on branch `audit/2026-10-13`.
Nothing here was guessed into the code. Where a default had to be picked to ship, the entry
says which one and how to change it.

Status values: `open` (needs a decision), `defaulted` (shipped with a reversible default,
needs confirmation), `handoff` (fix belongs to another repo or lane).

---

## U-01 · The canonical MCP hookup returns no results for an indexed repo

- **Page:** `/`, `/for/*`, README, `docs/quickstart.md` (step "point your agent at it")
- **Question:** After `trovex index /path/to/repo`, `trovex serve` and
  `claude mcp add --transport http trovex http://localhost:8765/mcp`, should the agent's
  `trovex` tool find the indexed repo?
- **Source checked:** a clean-env test of trovex 0.16.1 from PyPI (isolated HOME and data dir),
  driven through JSON-RPC over the streamable-HTTP MCP endpoint:
  - `trovex search` (CLI) and `GET /api/search` both return `docs/deploy.md` first.
  - MCP `tools/call trovex {q}` returns `(no results)`, and so does `trovex_search`.
  - MCP `tools/call trovex {q, source: "code"}` or `{source: "*"}` returns the docs.
  - Pinning on the URL (`/mcp/?source=code` or `?source=*`) still returns `(no results)`. A
    bogus pin (`?source=bogus-zz`) raises no `unknown_source` error, which suggests
    `_pinned_source()` never sees the query string over HTTP.
  - `src/trovex/mcp_app.py::_resolve_source`: when unpinned, the default is the `trovex` SSOT
    tier ("precise default, broad opt-in"). `trovex index` writes to source `code`.
- **Impact:** high. A new user following the quickstart gets an agent that finds nothing until
  it passes `source="*"` itself, which the tool docstring allows but no page tells the user about.
  The site claims (~60%) were not touched.
- **Options:** (a) fix the URL pin, then put `…/mcp?source=*` (or the repo's source id) in the
  canonical `mcpUrl`; (b) when the SSOT tier is empty or has no hit, fall back to all sources;
  (c) document "ask with source=*" in the quickstart.
- **Recommendation:** (a) and (b). Then update `web/src/quickstart.json` `mcpUrl`/`claudeCode`
  if the URL changes; the build guard will name every page to fix.
- **Decider:** trovex-backend / owner
- **Status:** open

## U-02 · Discord link: `/go/discord?s=` (link policy) vs `tsukumo.ch/discord` (works today)

- **Page:** landing hero, "Get started", footer; every static page's suite footer; `/savings`;
  `/audit`
- **Question:** Which URL should community links use?
- **Source checked:** commit 1900a82 (cmo: "Discord only"), README (already Discord), tsukumo
  `src/app/(frontend)/discord/route.ts` (code-defined, server-side `Discord Join` event),
  live probes (`/go/discord` returned 503 twice, `/discord` returned 200 to a valid invite), and
  the local link-policy hook (no hand-rolled UTMs; prefers `/go/<slug>?s=`).
- **Impact:** medium. Per-placement attribution on the server-side `Discord Join` goal is lost
  (it records `utm_source=other`). Client-side `oss_adopt: discord` still fires on the landing.
- **Options:** (a) keep plain `tsukumo.ch/discord`; (b) switch to `/go/discord?s=<placement>`
  once the shortlink store is reliable; (c) give `/discord` a `?s=` param in the tsukumo repo.
- **Recommendation:** (b) once U-03 is fixed. It is a one-field change in
  `web/src/suite.json` (`community.href`), then `npm run sync:suite`.
- **Decider:** cmo
- **Status:** defaulted to (a). Slack is removed from trovex.dev; `tsukumo.ch/slack` ends in
  a 403 on Slack.

## U-03 · `/go/*` CMS destinations can't be observed (shortlink store failing)

- **Page:** all `/answers/*` and `/vs/*` consult bands, landing consult band, README, `/audit`
- **Question:** What does each `/go/<slug>` row in the tsukumo Payload `shortlinks` collection
  point to? Is `call` set to `/book`?
- **Source checked:** tsukumo `origin/main` (`go/[slug]/route.ts`, `lib/shortlinks.ts`,
  `payload.config.ts`), plus live curl at 07:32Z (details in `go-redirects.md`). Every slug got a
  DB-error fallback (307) or a 503, including a made-up slug.
- **Impact:** high for the consult funnel if the outage persists. `call` and `consulting` still
  land correctly through the hard-coded fallback.
- **Options:** owner checks tsukumo.ch/admin → Shortlinks, sets `call` → `/book`, and fixes
  the DB lookup error; or remove `/go` from trovex entirely.
- **Recommendation:** keep `/go/call` and `/go/consulting` (they degrade safely), fix the store,
  set `call` → `/book`, then re-probe and expect a 308.
- **Decider:** owner (tsukumo admin) / tsukumo fullstack lane
- **Status:** handoff

## U-04 · `/book` still embeds Calendly

- **Page:** `tsukumo.ch/book` (the target of `/go/call`)
- **Question:** When does `/book` move to Google Calendar?
- **Source checked:** tsukumo `origin/main` `src/app/(frontend)/book/page.tsx`
  (`BOOK_URL = calendly.com/hello-tsukumo/tsukumo-1-hour-call`). trovex.dev never links Calendly
  directly; the only `calendly` strings in this repo are analytics click heuristics in
  `copy-track.js` and `vs/track.js`.
- **Impact:** none on trovex.dev, which only links `/go/call` → `/book`.
- **Decider:** tsukumo fullstack lane
- **Status:** handoff

## U-05 · `https://tsukumo.ch/products` returns 404 (target of "A Tsukumo product")

- **Page:** every page (signature in the topbar and suite footer)
- **Question:** Is `/products` live before trovex.dev deploys?
- **Source checked:** live curl (404); no `products/page.tsx` on any tsukumo branch.
- **Impact:** high if trovex.dev deploys first, because every signature link would be a 404.
- **Options:** (a) hold the trovex deploy until tsukumo IA-01 ships `/products`; (b) temporarily
  set `signature.href` to `https://tsukumo.ch` in `web/src/suite.json` and run
  `npm run sync:suite`.
- **Recommendation:** (a) if `/products` is near; otherwise (b), reverting when it ships.
- **Decider:** owner / tsukumo CTO
- **Status:** open (**deploy blocker**)

## U-06 · Signature casing: "A Tsukumo product" vs the site's lowercase house style

- **Page:** all
- **Question:** trovex.dev writes brand names in lowercase ("built by tsukumo", trovex, yoru,
  wrai.th, dokan; niwa.build also writes "niwa"). The ticket and audit specify "A Tsukumo
  product". Keep the audit's exact string, or lowercase it?
- **Source checked:** landing footer, the static pages, the niwa.build `<title>`, audit §11.
- **Impact:** low (consistency).
- **Recommendation:** keep the exact string if it is the cross-site contract (same on Niwa and
  Yoru); otherwise lowercase it. Either way it is one field in `suite.json`.
- **Decider:** cmo / brand
- **Status:** defaulted to "A Tsukumo product". Product names stay lowercase.

## U-07 · Suite descriptors and destinations

- **Page:** suite footer (all pages)
- **Question:** Are these the approved one-line descriptors and URLs?
  niwa: "autonomous engineering crews, early access" → `https://niwa.build`;
  yoru: "session receipts" → `https://www.yoru.sh`;
  wrai.th: "agent orchestration" → `https://tsukumo.ch/wraith`;
  dokan: "deterministic execution" → `https://tsukumo.ch/dokan`.
- **Source checked:** niwa.build `<title>`, the ticket ("early access"), the README "Part of the
  suite" section (which links GitHub for wrai.th and dokan), the previous landing footer
  ("wrai.th (agent orchestration)"), live curl (all 200).
- **Impact:** low. The audit asks for "the same short description everywhere" and says to
  confirm Niwa's features before rewriting promises.
- **Recommendation:** owner confirms. If tsukumo publishes canonical one-liners, copy them into
  `suite.json`.
- **Decider:** owner / cmo
- **Status:** defaulted

## U-08 · Claude Code hookup: `claude mcp add` or `trovex setup` as the canonical step

- **Page:** README, `/for/claude-code`, `docs/quickstart.md`
- **Question:** The README led with `trovex setup` (TSU-220); `/for/claude-code` used
  `claude mcp add`. Which one is canonical?
- **Source checked:** `src/trovex/setup_cmd.py` (it runs
  `claude mcp add --scope user --transport http trovex http://localhost:8765/mcp` and also
  installs the skill and hooks).
- **Impact:** low. Both work, but they register at different scopes (user vs local).
- **Recommendation:** shipped as `claude mcp add` (the same pattern as every other editor), with
  `trovex setup` as the documented one-step option on README, docs and `/for/claude-code`.
- **Decider:** cmo / trovex owner
- **Status:** defaulted

## U-09 · Quickstart side effects seen in testing

- **Page:** quickstart (all surfaces)
- **Question:** (1) `trovex index` and `uvx trovex index` both write to the global
  `~/.trovex-data`, so a user's first index joins whatever is already there; should the
  quickstart say so? (2) On a 3-doc sample, the same query ranked `docs/deploy.md`, `README.md`
  or `docs/onboarding.md` first across different runs and environments.
- **Source checked:** `src/trovex/config.py` (`data_dir = ~/.trovex-data`), test transcripts.
- **Impact:** low (tiny corpus; may not reproduce on real repos).
- **Decider:** trovex-backend
- **Status:** open

## U-10 · Pre-existing mobile overflow (390px)

- **Page:** every static page (topbar "star on GitHub" overflows by 67px); landing hero window
  (14px)
- **Question:** Fix now (QA-01) or leave as is?
- **Source checked:** Playwright at 390px. The signature added on this branch is hidden under
  640px and is not the cause. The landing footer link row, which this branch touched, now wraps.
- **Decider:** cmo / frontend
- **Status:** open

## U-11 · Backend format gate

- **Page:** n/a (repo)
- **Question:** The trovex-fullstack gate includes `ruff format --check src tests`; on
  `origin/dev` 60 files already fail it. `make test` (lint + pytest) is green.
- **Decider:** CTO
- **Status:** open (not changed here, to keep the diff on-ticket)
