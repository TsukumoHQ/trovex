# DRAFT — second-session retention nudge

*Owner: cro-lead · Conversion team · status: **DRAFT for cmo review — do NOT ship live***

> This is a draft only. Nothing here is wired up. No email is sent, no telemetry is
> collected, no live copy is deployed by this document. It exists so cmo can decide
> what (if anything) to turn on later.

## The problem it addresses

2026 growth is retention-first: a leaky bucket makes awareness spend worthless. For
trovex the risk is the classic dev-tool drop-off — someone installs, indexes, sees the
savings number once (the aha we now print on first `trovex search`), and never comes
back to wire it into their agent. The value compounds only across sessions; a one-time
install captures none of it.

**Goal of the nudge:** get the user from session 1 (saw the number) to session 2
(wired into their agent, savings start accumulating on the dashboard) — without being
annoying, without dark patterns, and without anything that leaves their machine unless
they explicitly opt in. trovex is local-first; the retention mechanic must respect that.

## Principle: earn the return, don't nag

- Local-first means the honest default channel is **the CLI itself**, not email.
- No surprise network calls. No "we noticed you stopped using us" guilt.
- One useful next step at a time. The nudge teaches; it doesn't beg.

## Option A — CLI tip (recommended, ship-ready when approved)

A short, contextual one-liner trovex prints at natural moments. No new infrastructure,
no PII, no opt-in needed because nothing leaves the machine.

**A1 — after first `index`, if the server was never started** (state already trackable
locally, e.g. a flag in `data_dir`):
```
tip: you've indexed but haven't wired trovex into your agent yet.
     run `uv run trovex serve` and point your MCP client at /mcp —
     savings start adding up on the dashboard at /savings.
```

**A2 — on `trovex search`, occasionally (e.g. every ~5th run) when not served via MCP:**
```
tip: these savings aren't being tracked yet. wire trovex into your agent
     (`uv run trovex serve`) and the dashboard tallies them automatically.
```

**A3 — `trovex stats` / `trovex serve` startup footer, week 1 only:**
```
this week: saved 840k tokens across 312 lookups. see the trend → /savings
```
(Reuses `savings.totals` — honest, real, no fabrication. Suppressed if usage is trivial.)

Tone rules: lowercase, plain, one tip max per invocation, never blocks the command,
silenceable with `--no-tips` / a config flag. Tips stop once the user is clearly
activated (served + recurring queries).

## Option B — optional email (DRAFT copy only; opt-in, off by default)

Only if a user **explicitly** opts in (e.g. `trovex serve --email you@x.com` or a
dashboard field). Default OFF. One email, then they choose to continue. This is a
maybe — Option A is preferred because it needs no PII and no sending infra.

**Draft — "your first week" (sent ~7 days after first activation, opt-in only):**

> Subject: trovex saved your agents 840k tokens this week
>
> Hi —
>
> Your agents made 312 lookups through trovex in the last 7 days and skipped about
> 840k tokens of rereading (~61% less on .md lookups). The full trend is on your
> dashboard: http://localhost:8765/savings
>
> Two things that make it compound:
> - keep trovex running so every agent session routes through it
> - if a teammate's agents work the same repo, point them at the same store — one
>   source of truth, shared savings
>
> That's it. No marketing list — you asked for this one note. Reply STOP and it's the
> last.
>
> — trovex

Constraints if B is ever built: real numbers only (no projections), one-click
unsubscribe, no list rental, no drip beyond this single message without a fresh opt-in.

## Anti-patterns (explicitly refuse)

- Fake urgency / streak-loss guilt ("don't break your 3-day streak!").
- Emailing anyone who didn't opt in. Harvesting emails from git config or env.
- Fabricated or projected savings to manufacture a reason to return.
- A tip that blocks or delays the actual command.
- Any nudge that fires after the user is already activated (respect "done").

## Measurement (coordinate with analytics-lead before shipping)

- Define **session-2 activation** = user runs trovex via MCP (served) AND ≥1 query in a
  session after the install session.
- A/B the CLI tip (Option A) vs control on session-2 rate. Do not ship the nudge as a
  "win" until instrumented — optimizing blind is against playbook.

## Recommendation

Ship **Option A (CLI tips)** first when approved — zero PII, zero infra, local-first,
reversible with a flag. Treat **Option B (email)** as opt-in-only and probably later.
Both gated on analytics-lead instrumenting session-2 activation so we measure the loop
instead of guessing.

**Decision needed from cmo:** approve Option A tips for an implementation task? Hold
Option B? This doc ships nothing on its own.
