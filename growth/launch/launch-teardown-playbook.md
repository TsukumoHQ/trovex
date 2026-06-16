# Top-1% launch teardown → applied playbook (DRAFT)

**Status:** DRAFT / playbook. Informs how we fire the one-shots; nothing here goes live.
**Owner:** launch-lead · **Reviewed against:** show-hn.md, product-hunt.md, launch-day-runbook.md, voice, north-star
**Method:** teardown of the best-performing OSS/dev-tool launches (2023–2026) → reusable rules, then applied to trovex (a token-efficiency, local-first OSS dev tool with a skeptical audience).

> Use this to pressure-test `show-hn.md` / `product-hunt.md` before firing. It's the *why behind the rules* — the evidence that the patterns in those kits actually worked, plus the anti-patterns that sank others.

---

## 0. The five rules that won every time (TL;DR)

1. **One reproducible number beats every adjective.** uv won with "38s → 3s on the same install," not "blazing fast."
2. **Link the repo, not a landing page.** A runnable README + zero signup = the HN/dev sweet spot; let them verify the claim themselves.
3. **Be in the thread, fast and deep.** Fly.io's founder answered 53 comments. Momentum dies in the first hour without the founder present.
4. **State a real limitation up front.** For a skeptical crowd, an honest weakness buys more trust than any feature.
5. **Nothing ships on launch day.** Everything lands a week prior (Supabase rule). The launch is the announcement, not the deploy — a broken install on the day writes your obituary in the top comment.

---

## 1. Case evidence (what they actually did)

| Launch | What won | The transferable rule |
|---|---|---|
| **Supabase** ("open-source Firebase alternative") | Front page for days; ~10x hosted DBs overnight. Repeatable "Launch Week": one ship/day, minute-by-minute schedule, **nothing ships on launch day**, channel matched to feature, mandatory retro. | Comparison-to-incumbent positioning + ship-ahead discipline + a repeatable cadence. |
| **PostHog** ("open-source product analytics") | Pre-stated *modest* goals ("happy with 500 stars"); hit 800+ stars / 200+ signups on ~$1K. Fixed repo tags, rode GitHub Trending. | Modest honest goals read as credible; repo discoverability (tags/topics) is free reach. |
| **Astral — ruff & uv** | "10–100x faster," shown as reproducible benchmarks; drop-in replacement. 85k+ stars. | A *defensible* number + drop-in framing. |
| **Fly.io / Fig / Lago (Launch HN)** | Concrete titles that name the tech; Fly.io founder answered 53 comments. | Title formula + relentless founder presence. |
| **Tailscale** | Won a skeptical crowd with *honesty content* — "how our free plan stays free," "what Tailscale isn't," public security posture. | Transparency content converts skeptics without a benchmark. |
| **PH #1s** (Corbado, Arc, v0, Cursor) | Repeat launches, strong visuals, pre-seeded community. | PH rewards visuals + a warmed community + repeat at-bats. |

---

## 2. Applied to trovex — Show HN

**Title** — `Show HN: trovex – <concrete value, name the tech>`. Candidates to A/B in `show-hn.md`:
- `Show HN: trovex – an MCP server that gives coding agents one canonical doc (~60% fewer tokens)`
- `Show HN: trovex – stop your coding agent rereading the repo to find the current doc`
- No superlatives. The *only* number allowed is the defensible ~60%, framed as a measurement, not a boast.

**First comment (post immediately, 7 beats):** who I am → one line on what it does → the problem (agents reread `.md` every session, burn tokens, sometimes grab the stale one) → why I built it → how it works (canonical doc + `path:line` + freshness, section reads, shared write path) → what's different (one canonical answer w/ freshness vs a candidate pile or a static CLAUDE.md) → **ask for feedback, not upvotes** + **one honest limitation** (e.g. "on a tiny doc set it won't save much; savings are repo-dependent").

**The number, uv-style:** show "tokens before / after on a named real repo + task" (the savings receipt) — reproducible, the reader can run it on theirs. This is the single highest-leverage asset.

**Link target:** the **repo** (runnable README, `uvx trovex` quickstart, zero signup) — not trovex.dev. Local-first means they can verify the savings themselves: lead with "nothing leaves your machine, run it and check the number."

**Founder presence:** free 2–3h, reply fast for the first ~60 min, go deep, agree-then-respond to criticism, write as an engineer. (launch-day-runbook §2/§5.)

**Timing:** Tue–Thu ~9am–12pm ET — a minor lever, not the strategy. Don't over-optimize the slot.

---

## 3. Applied to trovex — Product Hunt

- **Ranking is quality-weighted, not raw votes.** PH clears votes from new/low-engagement/same-IP accounts (~every 2h). So: **never** ask for upvotes, never cluster same-city votes, keep inflow diverse and under ~100/hr.
- **Pre-seed 100–300 genuinely-engaged people 3+ weeks out** via personalized notes asking for *feedback*; that's the legit velocity. (Build the list per launch-day-runbook §1.)
- **Maker first comment = the personal-problem story** (not a feature list), ending with a use-case question ("what's the first repo you'd point it at?") — use-case-tagged comments get higher algorithmic weight.
- **Visuals matter more than on HN:** a strong gallery of *real runs* (index finishing, the savings receipt, a real `trovex(q)` result) + a short demo video. No mockups.
- **Hunter** only if it's a credible one who'll write an authentic comment — a hunter gets placement, not votes.
- **Timing:** 12:01am PT; for the weekly badge, Tue of a non-stacked week. Don't stack with the HN day.

---

## 4. Positioning for a skeptical, token-cost audience (the trovex-specific edge)

1. **One reproducible number, not an adjective** — mirror uv. The savings receipt is the whole pitch.
2. **Repo + runnable README + zero signup** — local-first/self-hostable is the HN sweet spot; verifiability is the trust.
3. **Position against a known mental model** — "the drop-in way to cut agent context cost" / "one canonical doc vs rereading the repo (or a stale CLAUDE.md)." Borrow the incumbent's framing (competitive-analysis: vs CLAUDE.md / repomix / context-hub).
4. **State the limitation first** — small doc sets save little; savings are repo-dependent. Saying it first beats having it said at you.
5. **Modest goals (PostHog) + honesty content (Tailscale)** — a "how trovex works / what it isn't / why local-first" writeup converts skeptics into advocates. Pairs with the consulting funnel staying low-key.
6. **Make "your docs/keys never leave the machine" explicit + verifiable** — the local-first differentiator this crowd rewards.

---

## 5. Anti-patterns (what reliably backfires — do not do)

- Superlatives / unbacked claims (fastest/best/first) → HN closes the tab.
- Vague marketing titles that hide what it is.
- **Vote-begging, vote-link sharing, friends posting booster comments as "users"** → HN voting-ring detection + PH vote-clearing, sometimes net-negative.
- Same-city/same-IP PH vote spikes → mass clearing.
- **AI-generated launch comments** → PH detects + discounts them; generic loses to use-case-specific.
- Fake/unreproducible benchmark → one debunk in-thread sinks credibility (the inverse of why uv won).
- Paywall / signup wall / no public repo → removes the "try it now" HN runs on.
- Founder absent from the thread → momentum dies in hour one.
- **Broken install / failing quickstart on launch day** → the top comment becomes your obituary. (Supabase: nothing ships on launch day.)

> Every one of these maps to a banned move already in `autonomy-rules`, `show-hn.md`, or `product-hunt.md` — this teardown is the evidence for *why* they're banned.

---

## 6. Pre-launch checklist this teardown adds to the runbook

- [ ] The savings receipt is reproducible on a **named public repo** a stranger can re-run.
- [ ] Repo README has a working `uvx trovex` quickstart + zero signup; cold-clone tested.
- [ ] GitHub topics/tags set for discoverability (PostHog lesson) → GitHub Trending eligibility.
- [ ] First comment drafted with the 7 beats **and** one honest limitation.
- [ ] One honesty-content post drafted ("how trovex works / what it isn't / why local-first").
- [ ] Nothing ships on launch day — last code lands ≥1 week prior (Supabase rule).
- [ ] Founder's 2–3h presence blocked; feedback-asks (never upvote-asks) ready.

*This is a playbook informing the launch kits. Nothing here is live.*
