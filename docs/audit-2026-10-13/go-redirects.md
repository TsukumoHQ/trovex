# /go/* redirect inventory (audit 2026-10-13, TR-02)

Checked 2026-10-14 07:32Z with `curl` from a normal (non-sandboxed-browser) session:
`curl -sS -o /dev/null -w '%{http_code} -> %{redirect_url}'` for the first hop, and the same
with `-L` for the final status. Each slug was probed twice, a few seconds apart, with the same
result both times.

## Where the slugs live

None of the `/go/*` links on trovex.dev are served by trovex.dev. Every one points at
`https://tsukumo.ch/go/<slug>`, served by the tsukumo repo
(`src/app/(frontend)/go/[slug]/route.ts`). The destination of each slug is a row in the
Payload CMS `shortlinks` collection, editable in tsukumo.ch/admin. It is **not in any repo**,
so the configured destinations cannot be read from code.

Route behaviour (`src/lib/shortlinks.ts`):

- DB lookup OK, slug enabled → **308** to the configured destination.
- DB lookup OK, slug unknown or disabled → **404**.
- DB lookup fails (after 1 retry) → money-path slugs fall back with a **307** to a hard-coded
  on-site page (`call`/`book` → `/book`, `consulting` → `/consulting`,
  `assessment` → `/assessment`). Every other slug returns **503** "Temporarily unavailable".

At check time the shortlink DB lookup was failing. Every probed slug answered with a 307
fallback or a 503, never a 308. A made-up slug (`/go/zzz-nonexistent`) also returned 503
instead of 404, which confirms the lookup error. **The configured CMS destinations therefore
could not be observed** (see UNKNOWNS U-03).

## Inventory: links on trovex.dev before this branch

| Slug | Linked from (before) | Uses | Observed first hop | Final | Status after this branch |
|---|---|---|---|---|---|
| `/go/call` | 26 `/answers/*` pages (`?s=answers-band`), 12 `/vs/*` pages (`?s=vs-band`), landing consult band (`?s=landing`) | 40 | 307 → `https://tsukumo.ch/book` (DB-error fallback) | 200 `tsukumo.ch/book` | **Kept.** Lands on `/book` today, but only through the fallback; the CMS row is unverified (U-03). |
| `/go/consulting` | README "Working with a team?" (`?s=readme`), `/audit` endplate (`?s=magnet`) | 2 | 307 → `https://tsukumo.ch/consulting` (DB-error fallback) | 200 `tsukumo.ch/consulting` | **Kept.** |
| `/go/discord` | landing hero "join Discord" (`?s=landing`) | 1 | **503** | 503 | **Replaced** with `https://tsukumo.ch/discord` (the `community.href` in `web/src/suite.json`, no UTM per the link policy). That route is defined in code, fires a server-side `Discord Join` event and does not depend on the CMS. Placement is still tracked client-side (`oss_adopt: discord`). See U-02 to move back to `/go/discord?s=…` once the shortlink store is reliable. |
| `/go/wraith` | landing footer suite line (`?s=landing`) | 1 | **503** | 503 | **Replaced** with `https://tsukumo.ch/wraith` (200), from `web/src/suite.json`. |
| `/go/site` | landing footer "built by tsukumo" (`?s=landing`) | 1 | **503** | 503 | **Replaced** with `https://tsukumo.ch` (200), from `web/src/suite.json`. The "built by tsukumo" label is kept. |

After this branch, trovex.dev links only the two money-path slugs (`call`, `consulting`),
which degrade safely when the CMS is down. Non-critical links go straight to code-defined
pages.

## Related redirects checked

| URL | First hop | Final | Notes |
|---|---|---|---|
| `https://tsukumo.ch/book` | 200 | 200 | Booking page. In the tsukumo repo `origin/main` it still embeds `calendly.com/hello-tsukumo/tsukumo-1-hour-call`; the move to Google Calendar is tsukumo-repo work (U-04). trovex.dev never links Calendly directly. |
| `https://tsukumo.ch/discord` | 308 → `discord.gg/FDG5ZcJZPj` | 200 `discord.com/invite/FDG5ZcJZPj` | Canonical community link. The invite resolves on the Discord API. |
| `https://tsukumo.ch/slack` | 307 → `join.slack.com/t/tsukumogroupe/…` | **403** `tsukumogroupe.slack.com/join/…` | No longer linked from trovex.dev (it was in the landing "start" and footer, and in llms.txt / llms-full.txt). |
| `https://trovex.dev/beta` | 308 → `/` | 200 | `web/vercel.json` |
| `https://trovex.dev/blog` | 308 → `https://tsukumo.ch/blog` | 200 | `web/vercel.json` |
| `https://trovex.dev/blog/<any>` | 307 → `https://tsukumo.ch/blog` | 200 | `api/blog-gone.js` |
| `https://trovex.dev/methodology` | 308 → `/method` | 200 | `web/vercel.json` |

## /go/call → tsukumo.ch/book

Required: `/go/call` must resolve to `https://tsukumo.ch/book`, never to Calendly.

- Observed: it lands on `/book`, but through the hard-coded DB-error fallback, not the CMS row.
- To guarantee it: in tsukumo.ch/admin → Shortlinks, set `call` → destination `/book` (relative,
  so `go-attribution.ts` keeps the UTM on the same site), enabled. Then re-probe once the DB is
  healthy and expect `308 → https://tsukumo.ch/book?...`. This is a CMS data change, outside
  this repo (U-03).
