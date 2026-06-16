# Launch-day runbook — consolidated (DRAFT)

**Status:** DRAFT / runbook. Nothing fires until **cmo signals go**. Today: staged, nothing live.
**Owner:** launch-lead · **Fired by:** owner (human) · **Reviewed against:** unfreeze-checklist.md, mcp-registries.md, show-hn.md, product-hunt.md, community-plan.md, outreach.md, voice, autonomy-rules, north-star
**Scope:** the day-of execution timeline across **directories + Show HN + Product Hunt + social + community**. This is the *operational* sheet — the dependency/blocker un-freeze lives in `unfreeze-checklist.md`; the *what-to-post* copy lives in the per-surface asset files. This runbook just sequences and times them, and marks every owner go-gate.

> Legend: **[GATE]** = a human/owner decision or credential needed before the step can run (never auto-fire). **[AUTO]** = launch-lead may execute when its gate is green (per autonomy-rules: registries when credentialed; reversible/compounding moves). **[HUMAN]** = a person must do it by hand (account creds / one-shot judgement).

---

## 0. Pre-flight gate (all true before anything in §2+ runs)

The master launch-readiness gate (mirrors unfreeze-checklist §0 — do not duplicate-decide, just confirm):

- [ ] **[GATE] tsukumo.ch live** — the consulting funnel destination exists; launch traffic has somewhere to convert.
- [ ] **[GATE] trovex waitlist working** — `/api/waitlist` off 503, storage env set by owner. Beta capture verified with a real submit.
- [ ] **[GATE] deploy verified live** — trovex.dev (+ wrai.th) load clean on a cold browser; no 500s, OG cards resolve.
- [ ] **[GATE] design assets ready** — OG cards + PH gallery + any thread images in the locked brand (green `#22c55e`, lowercase wordmarks).
- [ ] **[GATE] cmo signals go** + **owner free 2–3h** to staff the one-shot windows.

If any is red → stay frozen. Reversible registry seeding (§1) may still proceed ahead of the gate when the owner fires it.

---

## 1. T-minus (pre-launch window — compounding, reversible, ahead of the big day)

These build the shelf so traffic has somewhere to land. None is a one-shot; do them early.

### T-7 to T-3 — directories / registries (the shelf)
- [ ] **[HUMAN/eng] hard blockers cleared** — PyPI publish + `server.json` + repo public + history scrub. (unfreeze-checklist §1; mcp-registries.md blockers)
- [ ] **[AUTO] MCP Official Registry** submit (OIDC via CI, PR #52 path). Keystone — feeds PulseMCP / Docker / VS Code. (mcp-registries.md §2)
- [ ] **[HUMAN] Glama** web form (build-validated) → grab badge → README. (§4)
- [ ] **[HUMAN] mcp.so** web form. (§6)
- [ ] **[HUMAN] awesome-mcp-servers** PR (needs Glama first). (§5)
- [ ] **[HUMAN] AI/dev tool directories** — submit per `directory-submissions.md` (TAAFT, AlternativeTo, etc.), owner-gated copy.
- [ ] **[AUTO] verify propagation** — PulseMCP (auto, ~1wk), Docker, GitHub MCP Registry. Re-check at T-1.

### T-3 to T-1 — assets armed
- [ ] **[HUMAN] confirm every install line actually runs** from a cold clone / `uvx` (voice + mcp-registries §9). A broken install line kills a launch.
- [ ] **[GATE] beta proof folded in** (if trovex public) — real savings numbers + ≥1 permissioned quote into PH gallery + HN first comment + FAQ. No proof → no proof claims. (unfreeze-checklist §4)
- [ ] **[AUTO] anti-ai-slop gate** re-run on every flipped/public asset.
- [ ] **[HUMAN] pick the launch weekday** — Tue/Wed/Thu AM ET. Avoid Mon, Fri, holidays, major-conf days.
- [ ] **[HUMAN] social pre-warm** — social-lead drafts queued (X thread, LinkedIn) but **not posted**; teaser only if at all. (social-lead assets)
- [ ] **[HUMAN] DM/supporter list** assembled for PH (people who genuinely use it / asked) — no mass blast. (product-hunt.md)
- [ ] **[HUMAN] founder has 2–3h blocked** on launch morning to answer.

---

## 2. Launch day — Show HN (the lead one-shot, widest TOF)

> One shot, non-repeatable. Weekday **AM ET (~8–10am)**. Do NOT stack HN + PH same day.

- [ ] **[GATE] cmo final go** (morning-of).
- [ ] **[HUMAN] submit Show HN** — title + URL per `show-hn.md`. lowercase, no hype, "Show HN: trovex – …".
- [ ] **[HUMAN] paste the first comment immediately** (the founder context/why) — prepared text from `show-hn.md`. Within ~1 min of submit.
- [ ] **[HUMAN] founder answers in-thread for 2–3h** — honest, technical, fast. Use `faq-bank.md` for objection answers.
- [ ] **DO NOT** ask for upvotes, ring-vote, or seed booster comments — HN penalizes it and it's against the rules. (anti-pattern)
- [ ] **[HUMAN] if it gains traction** — keep answering; don't cross-post the HN link to communities asking for votes.
- [ ] **[AUTO] note timestamps** for analytics-lead (submit time, first-comment time) — hand to analytics.

---

## 3. Launch day +N — Product Hunt (separate day from HN)

> One shot. Goes live **12:01am PT**. Pick a different day than HN (spacing > stacking).

- [ ] **[GATE] cmo go for the PH day.**
- [ ] **[HUMAN] schedule/launch** at 12:01am PT — tagline, gallery, topics per `product-hunt.md`.
- [ ] **[HUMAN] maker first comment** posted at launch — the honest "why I built it" + the savings framing.
- [ ] **[HUMAN] gallery = real runs** (index finishing, savings receipt, a real `trovex(q)` result). No mockups, no fabricated metrics.
- [ ] **[HUMAN] notify supporters 1:1** from the prepared list — "it's live, take a look if useful," never "please upvote." (product-hunt.md DM template)
- [ ] **[HUMAN] answer every comment** through the day; founder present.
- [ ] **[AUTO] capture rank/referrals** for analytics — but the metric is activation, not rank. (north-star)

---

## 4. Launch day — social + community (amplify, value-first, spaced)

Runs alongside HN/PH but **does not beg for votes** and respects each venue's rules.

- [ ] **[HUMAN] X thread** — the build story + savings number, links repo (not "upvote my HN"). (social-lead)
- [ ] **[HUMAN] LinkedIn post** — same story, founder voice. (social-lead)
- [ ] **[HUMAN] Discord #showcase** — ONE post per server in the right channel, after being a useful member. (outreach.md §C)
- [ ] **[HUMAN] subreddit posts** — r/LocalLLaMA / r/mcp / r/ChatGPTCoding, value-first, per each sub's rules, spaced not same-minute. (community-plan.md)
- [ ] **[HUMAN] newsletter notes** — 1:1, personalized, spaced over days (PulseMCP, TLDR, Console.dev). NOT a batch. (outreach.md §B)
- [ ] **DO NOT** copy-paste identical copy across venues, or drop drive-by links. (anti-pattern)

---

## 5. During (the live hours — staffing rules)

- [ ] Founder is the single voice on HN/PH for the first 2–3h. Speed + honesty > polish.
- [ ] Answer the hard objection ("my context window is huge") straight, with the cost-compounds framing. (faq-bank.md)
- [ ] Keep the consulting angle low-key — if a team-lead engages, "working with a team? happy to talk," never a pitch in-thread. (north-star, voice)
- [ ] If something's broken (install fails, 500), say so plainly and fix it — don't spin. A visible honest fix beats silence.
- [ ] **[GATE]** any decision to pull/repost a one-shot = cmo + owner, not launch-lead.

---

## 6. Post (T+1 to T+7)

- [ ] **[HUMAN] reply to late comments** on HN/PH for ~48h; the long tail matters.
- [ ] **[AUTO] hand metrics to analytics-lead** — installs / index runs / waitlist signups / registry referrals / HN+PH → activation (savings number seen), per funnel-event-taxonomy. Watch the **consulting-lead door** (north star), not vanity rank.
- [ ] **[AUTO] verify registry propagation** completed (PulseMCP, Docker, VS Code MCP view).
- [ ] **[HUMAN] thank engaged people 1:1**; turn genuine fans into the (built-in) savings-receipt referral loop.
- [ ] **[HUMAN] write the retro** — what converted, what didn't; feed the next coordinated push.
- [ ] **[AUTO] re-publish Official Registry on the next release tag** so listings never go stale.

---

## 7. Owner go-gate summary (the only things that block, in one place)

| # | Gate | Who clears it | Blocks |
|---|------|---------------|--------|
| G1 | tsukumo.ch live + trovex waitlist working + deploy verified | owner/eng | everything in §2+ |
| G2 | design assets ready (OG/gallery) | design-lead → owner | HN/PH/social |
| G3 | cmo signals go + owner free 2–3h | cmo + owner | the one-shots |
| G4 | beta proof (real numbers + ≥1 quote) | owner | any proof claim in copy |
| G5 | platform account creds (HN/PH/X/LinkedIn/Reddit) | owner | the live posts (else: drafts handed off) |
| G6 | pull/repost a one-shot | cmo + owner | recovery actions |

**Rule:** launch-lead may run **[AUTO]** registry/reversible steps when their gate is green; everything **[GATE]/[HUMAN]** waits for the owner. Never fire a one-shot at night or before the funnel destination is live — the click must have somewhere to land.

*This is a held runbook. Nothing here runs until cmo lifts the hold and the owner fires each step.*
