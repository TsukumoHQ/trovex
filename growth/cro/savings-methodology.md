# How we measure "~60% fewer tokens"

*Owner: cro-lead · Conversion team. Source for the landing's `~60%` claim — the
reproducible-benchmark page a skeptical developer should be able to land on and verify.
Status: ready to wire (link the landing/README `~60%` here once it's a published page).*

> Why this exists: research on dev-tool landings is clear — for a tool with no
> testimonials, the credible above-the-fold proof is a **quantified, reproducible
> benchmark linked to its methodology** (the way `uv` links "faster than pip" to a
> benchmarks page). trovex shows `~60%` but hasn't linked the how. This is the how.
> Honest, grounded in the actual code, reproducible on the reader's own machine.

## What the number means

`~60% fewer tokens` is about **`.md` doc lookups by a coding agent**, not the whole
session. Without trovex, an agent typically Globs/Greps then Reads 2–3 candidate `.md`
files to work out which is current. With trovex it gets one ranked, freshness-marked
answer and reads the **one canonical doc** (or zero, if all candidates are stale).
The savings is the tokens it *didn't* read.

It is a **reduction on doc-lookup token spend**, stated as `~` because the real figure
depends on your corpus (how many overlapping/stale `.md` you have) and your agent's
habits. We don't claim a universal constant — we claim a method you can run.

## Two ways it's measured (both in the product)

### 1. Per-query estimate — what the dashboard and CLI show
Implemented in `src/trovex/savings.py`. For each `trovex` query:

```
would_have_read = sum(tokens of the top 3 candidate docs)   # the triage an agent skips
actual_read     = tokens of the top 1 canonical doc          # what it reads instead
response        = the trovex pointer output (~small)
saved           = max(0, would_have_read - actual_read - response)
ratio           = saved / would_have_read
```

This is an **estimate of avoided work**, shown per-query in `trovex search` and
aggregated on the `/savings` dashboard. It's a model: it assumes the unaided baseline is
"read the top 3 candidates," which is the common triage pattern but not a law.

### 2. Real before/after — `trovex measure` (the honest benchmark)
Implemented in `src/trovex/measure.py`. This doesn't model anything — it reads the
**actual `.md` read events** your agent logged (via the `trovex-baseline` hook into
`~/.claude/trovex-baseline.jsonl`) and compares two time windows:

```
baseline window (before / without trovex routing)   →  tokens per .md read
current  window (with trovex routing)                →  tokens per .md read
Δ tokens/read = 1 - current/baseline                 →  compared against the -60% target
```

Run it yourself:

```bash
uv run trovex measure            # default: prior 7d vs last 7d
```

It prints both windows, the Δ%, a verdict (`✓ HIT` ≥60%, `~ on track` ≥30%,
`✗ below target`), and the top paths by tokens. This is the number a skeptic should
trust, because it's **your** logs, not our model.

## How a skeptical developer verifies it

1. Install the baseline hook so `.md` reads are logged (see repo hooks).
2. Work normally for a few days **without** routing through trovex → baseline window.
3. Index your repo and route your agent through trovex → current window.
4. `uv run trovex measure` → read the Δ on *your* corpus.

If your number is lower than 60%, that's the honest answer for your repo — the method is
the claim, not a fixed percentage.

## Honesty constraints (do not violate)

- Pre-launch, **zero customer numbers**. The dashboard mock on the landing uses
  illustrative figures and is labelled as the product UI, not a customer result.
- Never present the per-query *estimate* as a measured before/after — they're different
  (one models avoided work, one reads real logs). The landing's `~60%` should resolve
  here to *both*, clearly distinguished.
- The `~` stays. No "60%" without the tilde, no "up to" inflation, no cherry-picked best
  case dressed as typical.

## Wiring (follow-up, needs cmo/geo-lead)
- Publish this as a real page (e.g. `/how-we-measure` or a section) and link the
  landing's `~60% fewer tokens` and the trust card to it.
- geo-lead: this is exactly the extractable, citable methodology AI engines reward —
  good GEO surface. Coordinate the route + schema.
