# Verify — waitlist events + attribution on live trovex.dev

*Owner: analytics-lead · Status: code-path verified + gap fixed · Last updated: 2026-06-16*

Task: confirm `request_access_clicked` + `waitlist_submitted` + UTM/referrer attribution
actually fire/flow on the live site, note gaps. I verified the **code path** end-to-end
and **fixed the one real gap** (attribution wasn't being captured). Live browser/Plausible
confirmation needs the deploy + an active provider — runbook in §4. I do not claim to have
watched live events; that's a post-deploy check.

---

## 1. What's wired (verified in code)

| Event | Where | Status |
|-------|-------|--------|
| `landing_view` | `App.tsx` mount | ✅ fires with `geo_source`/`channel`/`utm_*` |
| `request_access_clicked` | waitlist input `onFocus`, nav + hero "Request access" buttons | ✅ fires (see §3 note) |
| `waitlist_submitted` | `WaitlistForm` on `res.ok` only | ✅ fires only on a real stored signup |
| `section_viewed`, `compare_clicked`, `/vs/` `github_clicked` | root observer + `vs/track.js` | ✅ from earlier PRs |

All go through `track()` → no-op unless an analytics script is loaded, so no errors if the
provider isn't active yet.

## 2. Gap found + FIXED (this PR)

**Attribution was not captured.** The form POSTed `{ email, company }` only, and
`/api/waitlist` stored **email only** — so signups had **no source**, which breaks the
entire "signups by source" north-star and the waitlist funnel report.

Fix (additive, end-to-end):
- `App.tsx`: POST body now `{ email, company, ...getAttribution() }` — adds the closed-enum
  source props (`geo_source`, `channel`, `utm_*`, `referrer` host). No PII.
- `api/waitlist.js`: `pickAttribution()` allowlists those 7 keys (caps each to 64 chars,
  drops everything else) and stores them with the signup — KV member is now a JSON record
  `{ts, email, ...attribution}`; the GitHub-issue body gets a `source:` block.
- Privacy preserved: the **email is still the only PII**; attribution carries none. Email
  is never logged or sent to analytics (`waitlist_submitted` stays source-only).

So **signups are now attributable to a source** at the store — the report (`a49977c2`) can
actually be built.

## 3. Notes / minor gaps (not blocking)

- **`request_access_clicked` fires on input `onFocus` AND on the nav/hero buttons.** The
  nav/hero buttons scroll to `#waitlist`; a user who then focuses the field double-counts
  intent. Treat **focus as the canonical intent signal**, or de-dupe by `location` in the
  report (the buttons carry `location=nav|hero`, the field `location=waitlist`). Not wrong,
  just read it per-location. No code change pushed (cro owns the UX).
- The endpoint returns `503 not_configured` until KV/GitHub env vars are set — the form
  honestly says "not open yet." Attribution still flows once a backend is wired.
- Provider: analytics only records after a deploy with Plausible (or Vercel WA) active. The
  Plausible snippet is first-party-proxied (`vercel.json`); confirm the proxy resolves.

## 4. Live verification runbook (post-deploy)

Run once the deploy + a provider are live:

1. Open `https://trovex.dev/?utm_source=perplexity&utm_medium=ai_answer&utm_campaign=test&utm_content=verify` in a browser with devtools.
2. Network → confirm `/js/script.js` (Plausible) and `/api/event` resolve **first-party** (200, not blocked).
3. Focus the email field → see a `request_access_clicked` event hit `/api/event` with `props.geo_source=perplexity`, `utm_source=perplexity`.
4. Submit a test email → `/api/waitlist` returns 200 (if backend wired) → `waitlist_submitted` fires; confirm the **stored record carries the attribution** (KV member JSON / GitHub issue `source:` block) and **no analytics payload contains the email**.
5. In Plausible: the events appear under Goals, breakdownable by `geo_source`/`channel`/`utm_*`.
6. Repeat from a no-UTM direct hit → `geo_source=direct`. From a `claude.ai` referrer → `geo_source=claude`.

## 5. Acceptance

- [x] Event wiring verified in code (fire points + no-op safety).
- [x] **Gap found + fixed:** attribution now captured end-to-end (client POST + endpoint store), no PII.
- [x] Minor notes logged (`onFocus` double-count, 503-until-configured).
- [x] Live verification runbook for the post-deploy check.
- [ ] Operator: run §4 once deployed + provider active; wire KV/GitHub env for real storage.
