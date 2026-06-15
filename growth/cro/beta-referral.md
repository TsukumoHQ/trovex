# Spec — "invite a teammate to the beta" referral hook

*Owner: cro-lead · Conversion team. Spec + copy. Implementation is a follow-up.*

## Why

trovex's north star is qualified reach that surfaces consulting leads. The single
strongest consulting signal is **a whole team adopting it** — that's exactly who the
founder's consulting is for. So the one referral worth building during the private beta
is the one that pulls in a *teammate*, not a random new user. Team adoption is both the
product's best case (shared source of truth across agents + people) and the warmest
consulting lead we can manufacture.

Light, honest, no incentive gaming. The invite is useful on its own (your teammate's
agents share your store); it isn't a points scheme.

## The loop

1. A tester is **approved** into the beta (off the waitlist).
2. In their confirmation/welcome surface they see: *"trovex is better with your team on it
   — invite a teammate."* with 1–2 invite links.
3. The teammate clicks → lands on a short invite page (pre-vouched) → joins the beta
   **directly**, skipping the waitlist queue.
4. Two people on one team now share a store. That team is flagged as a **consulting
   signal** for the founder to (gently) follow up.

## Mechanic (kept deliberately small)

- Each approved tester gets a **small, fixed number of invites** (start: 2). Scarcity is
  honest here — the beta really is capacity-limited — and it makes the invite feel like
  something worth spending, not spam fuel.
- Invite = a unique link with an opaque token (`trovex.dev/beta?invite=<token>`), not an
  email blast we send. The tester shares it themselves (Slack/DM). We never email on
  their behalf without consent.
- Redeeming a token adds the teammate to the same **team/store grouping** as the
  inviter (so the SSOT value is real on day one) and records the inviter→invitee edge.
- One redemption per token; tokens expire (e.g. 14 days) so they don't leak forever.

## Copy

**Invite prompt (on the approved/welcome surface):**
> **trovex is better with your team on it.**
> One source of truth only works if your teammates' agents share it. You've got 2 beta
> invites — send one to whoever owns the most docs.
> `[ Copy invite link ]`

**Invite landing page (what the teammate sees):**
> **{inviter} invited you to the trovex beta.**
> trovex gives your coding agents one canonical doc per query instead of rereading the
> repo — about 60% fewer tokens, running locally. Join {inviter}'s store and your agents
> work from the same source of truth.
> `[ Join the beta ]`  ·  *takes about a minute, no card*

**After redeem:**
> You're in — you and {inviter} now share one store. Point your agent at it and go.

## Honesty / anti-patterns (refuse)

- No fake scarcity beyond the real cap; no "only 3 invites left!!" theatre.
- No rewards/points/leaderboards for inviting. The reward is the shared store working.
- We don't email a teammate on the tester's behalf without the teammate acting first.
- No exposing the inviter's email/PII to the invitee beyond a display name they consent to.
- Don't over-follow-up on the consulting signal — one quiet, well-timed note, the same
  low-key tone as the consulting CTA. A team adopting is an invitation to help, not a
  trigger to sell.

## How it feeds consulting

An inviter→invitee edge inside one org is the cleanest "this team is standardizing on
trovex" signal we get. Surface those clusters (2+ on a shared store) to the founder as
**warm consulting leads** — exactly the team-lead persona the consulting page targets.

## Build plan (follow-up tasks)

1. Token issue + redeem (serverless + the same first-party store as the waitlist; an
   `invites` set keyed by token → inviter). Cap 2/tester, single-use, 14-day expiry.
2. Invite prompt on the approved/welcome surface (needs the "approved" state to exist —
   depends on how the operator admits testers).
3. `/beta?invite=<token>` landing + redeem flow → team/store grouping.
4. Consulting-signal surfacing (cluster of 2+ on one store) for the founder.

## Instrumentation (coordinate with analytics-lead)

- Events (PII-free, source/counts only): `beta_invite_copied`, `beta_invite_landing_view`,
  `beta_invite_redeemed`. Watch invites-sent → redeemed → same-store-cluster as the loop's
  funnel. The metric that matters is **teams formed**, not raw invites.

## Status

Spec + copy only. No code, no tokens issued, nothing sent. Gated on the beta "approved"
state + the operator's go-ahead.
