# Beta feedback → case-study capture template

*Owner: content-lead · internal · pairs with [content-strategy.md](./content-strategy.md) and
[lead-magnet-token-audit.md](./lead-magnet-token-audit.md)*

trovex is pre-launch with zero customers, so the proof we lack (real savings numbers, real
quotes) can only come from beta testers. This is the template for capturing that as it
happens, so a future case study is assembled from things people actually said and measured,
never invented.

**Hard rules (no exceptions):**
- **Nothing gets published without explicit written consent.** Capturing ≠ permission to
  publish. See the consent ladder below.
- **No fabrication, no embellishment.** Numbers are the tester's real dashboard figures.
  Quotes are verbatim. If a field is unknown, leave it blank, never fill it with a plausible
  guess.
- **Anonymize by default.** Many devs will share results but not their name or employer.
  A real anonymous number beats a fake named one.
- **The honest-negative is also data.** "Saved me almost nothing on my small repo" is a true
  result worth recording. Don't capture only the wins.

---

## One record per tester

Copy this block per tester. Fill what you have; leave the rest blank.

```yaml
tester_id:            # internal handle, not their name
date_captured:        # YYYY-MM-DD
source:               # how they came in (waitlist / founder network / community)

# --- their setup (context for the number) ---
repo_shape:           # e.g. "monorepo, ~300 .md, runbooks + ADRs"
agents_used:          # Claude Code / Cursor / Windsurf / Zed / other
team_or_solo:         # solo | small team (N)
agent_traffic:        # rough sessions or lookups per week, if known

# --- the measured result (their dashboard, verbatim figures) ---
savings_pct:          # their real % from /savings, NOT our ~60%
tokens_saved:         # absolute, if they shared it
timeframe:            # over what period (e.g. "first week")
measured_how:         # "trovex savings dashboard" (don't claim methods they didn't use)

# --- their words (verbatim only) ---
quote:                # exact words; no cleanup beyond obvious typos
problem_before:       # how they described the pain, in their words
what_clicked:         # the moment/feature that landed
what_fell_short:      # honest negatives — capture these too

# --- consent (see ladder) ---
consent_level:        # none | anonymous | first-name | full-named | logo
consent_evidence:     # link/screenshot of the explicit yes
attribution_string:   # exactly how THEY want to be credited, if named
follow_up_ok:         # may we ask a follow-up? y/n

# --- usability ---
publishable_as:       # quote | mini-case | full-case | metric-only | not-yet
notes:                # anything else (redactions needed, NDA, etc.)
```

---

## Consent ladder

Capture the highest level the tester explicitly grants, in writing. Default to the lowest
until they say otherwise.

| Level | What we may publish | Need from them |
|-------|--------------------|----------------|
| `none` | nothing (internal learning only) | n/a |
| `anonymous` | the number + an unattributed quote ("a solo dev on a 300-file monorepo") | a plain "yes, anonymously" |
| `first-name` | quote + first name / handle | explicit yes + the name/handle to use |
| `full-named` | quote + full name + role | explicit yes + exact attribution string |
| `logo` | company name / logo | written yes from someone allowed to grant it |

If in doubt, drop a level. A weaker-attributed true story is always safe; an over-attributed
one is a trust (and possibly legal) problem.

## How to ask (lightweight, not a survey funnel)

Most captures come from a normal feedback exchange, not a form. When a tester shares a good
result, ask like a person:

> "That's a great number. Two things: mind if I save it as a possible case study later, and
> if so, how would you want to be credited, anonymous, first name, or full name and company?"

Record their answer verbatim in `consent_level` + `attribution_string`. No answer means
`none`.

## From capture to published proof

1. **Capture** every result here as it happens (wins and misses).
2. **Confirm consent** at the right level before anything leaves this file.
3. **Assemble** a case study only from captured, consented fields, the number is theirs, the
   quote is verbatim, the attribution is exactly what they granted.
4. **Show them the draft** before it goes live. A tester who approves the final is a tester
   who'll share it.

Until a record clears steps 2–4, it stays internal. The point of this file is that when we
finally have proof to show, every piece of it is real and permitted.
