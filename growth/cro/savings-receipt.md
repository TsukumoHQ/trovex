# Spec — shareable savings receipt (built-in referral loop)

*Owner: cro-lead · Conversion team · status: spec for review*

## Why this exists

trovex's north star is qualified reach that surfaces consulting leads. The cheapest
reach is word-of-mouth, and the most credible word-of-mouth a dev tool can produce is
a **real number from the user's own machine**: "trovex saved my agents 2.3M tokens this
week." This is not an incentive scheme — it's a built-in product loop: the savings
receipt *is* the ad. Every share carries a number worth bragging about and a link back.

This builds on the aha already shipped: the per-query savings line in `trovex search`
and the savings dashboard at `/` (`savings_mod.totals`, week-over-week delta, sparkline).
The receipt packages that same data into something one-click shareable.

## Design principles (what makes a dev artifact actually spread)

1. **Auto-generated from real usage.** Never a number the user types. Reads the same
   `mcp_queries` model as the dashboard (`would_have_read − top_result − response`).
2. **Identity-expressing.** It says something flattering about the sharer ("my agents
   are efficient / I don't waste tokens"), not just about trovex.
3. **One-click, zero-friction.** Copy a line, copy a badge, or save an image — no login,
   no account, no upload. Local-first, like the rest of trovex.
4. **Carries a backlink.** Every format embeds `trovex.dev` so a share is also a
   discovery surface. This is the only "growth" instrumentation in the loop.
5. **Honest or absent.** If the user has zero/low real savings, there is **no receipt**
   — we never fabricate a number, a streak, or a comparison. Pre-launch, the only
   credible numbers are the user's own. A receipt that overclaims kills the trust the
   whole brand is built on.

## What it shows (data contract)

All fields come from existing `savings.py` over a chosen window (default: last 7 days):

| Field | Source | Example |
|-------|--------|---------|
| `saved` | `totals(db, since)["saved"]` | `2,340,000` |
| `ratio` | `totals(...)["ratio"]` | `0.61` (→ "61% less") |
| `queries` | `totals(...)["queries"]` | `1,204` |
| `window` | caller (7d default) | "last 7 days" |
| `wow_delta` | from `daily_series` (already computed for the dashboard) | "+18% vs prior 7d" (omit if no prior data) |

Rounding: humanize (`2.3M`, `840k`) for the headline; exact with thousands separators
in the detail line. Never show a fake precision the model can't support.

## The three formats (ship in this order)

### 1. Terminal text card (MVP — lowest effort, highest dev-native fit)
A `trovex receipt` CLI command prints a clean, paste-ready block:

```
  trovex · last 7 days
  ─────────────────────────────
  saved 2.3M tokens · 61% less
  across 1,204 agent lookups
  ─────────────────────────────
  https://trovex.dev
```

Plus a `--tweet` flag that prints a single ready-to-paste line:

```
trovex saved my coding agents 2.3M tokens this week (61% fewer on .md lookups). https://trovex.dev
```

Honesty gate: if `saved < THRESHOLD` (e.g. < 50k) or `queries < 20`, print
"not enough usage yet — come back after your agents have run for a bit" and exit 0.
No card.

### 2. Markdown badge (for READMEs / repos — passive, compounding reach)
`trovex receipt --badge` prints a copy-paste markdown badge:

```
[![trovex saved 2.3M tokens](https://img.shields.io/badge/trovex-saved%202.3M%20tokens-22c55e)](https://trovex.dev)
```

(Shields static badge or a self-hosted `/savings/badge.svg` if the server is public.
Default to the static shields form so it works with zero infra.) A teammate seeing the
badge in a repo is exactly the small-team tech-lead persona.

### 3. Image share card (for X / LinkedIn / Slack — highest spread, most effort)
A server route renders a branded card from the same data:

- `GET /savings/receipt.svg` — SVG, generated server-side with the existing product
  tokens (green `#22c55e`, Fira mono), the headline number, ratio, window, sparkline,
  and `trovex.dev`. SVG first (no headless-browser dependency).
- `GET /savings/receipt.png` — optional later, via `resvg`/`cairosvg` from the SVG.
- The dashboard at `/` gets a small **"Share" button** next to the savings block:
  copies the tweet line + offers "save card" (the SVG). One click.

## Privacy (hard constraint)

The receipt exposes **only aggregate counts** — saved tokens, ratio, query count, window.
It must **never** include doc paths, titles, query text, repo names, or `user` values.
trovex is local-first and that's a trust pillar; the receipt cannot become a leak. The
SVG/PNG route takes no parameters that echo private data.

## Copy variants (voice: plain, cost-framed, no hype)

- Headline: `saved 2.3M tokens · 61% less`
- Tweet line A: `trovex saved my coding agents 2.3M tokens this week (61% fewer on .md lookups). https://trovex.dev`
- Tweet line B (curiosity): `my coding agents stopped rereading the repo. 2.3M tokens saved last week. https://trovex.dev`
- Badge alt text: `trovex saved 2.3M tokens`
- Low-usage state: `not enough usage yet — come back after your agents have run for a bit`

Banned (per brand voice): revolutionary, seamless, supercharge, unlock, "AI-powered",
exclamation-mark hype, fake urgency. The number does the work.

## How it ties to the funnel

- **Referral:** the share line + badge + card carry `trovex.dev` → new awareness from
  existing happy users, at zero CAC. This is the loop closing.
- **Retention:** generating a receipt is a reason to reopen the dashboard ("how much
  this week?"), reinforcing the second-session habit.
- **Consulting:** a team-lead who sees a teammate's badge/card is the exact consulting
  persona; the receipt is the top of that path.

## Build plan / sequencing (ICE-ordered)

1. **`trovex receipt` CLI** (text card + `--tweet` + `--badge`, honesty gate). Pure
   stdlib + existing `savings.totals`/`daily_series`. ~½ day. Highest ICE — dev-native,
   no infra, ships the loop immediately. **MVP.**
2. **Dashboard "Share" button** (copy tweet line + copy badge). Small server/UI change.
3. **`/savings/receipt.svg`** branded card. Medium effort, biggest social spread.
4. **`/savings/receipt.png`** + optional OG-image meta so a shared `trovex.dev` link
   itself previews a savings card.

## Acceptance for the implementation tasks (follow-ups)

- `trovex receipt` reads only real local data, respects the honesty gate, leaks no
  private fields, embeds `trovex.dev`. Output matches the copy above.
- Instrumentation note: coordinate with analytics-lead to attribute sessions arriving
  from receipt backlinks (UTM or referrer) so we can measure the loop, not guess.

## Out of scope / explicitly not doing

- No incentives, points, leaderboards, or "invite N friends" mechanics.
- No auto-posting anywhere — the user always copies/shares manually (no surprise
  network calls; local-first trust).
- No fabricated or projected numbers, ever.
