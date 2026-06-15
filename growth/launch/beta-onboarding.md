# trovex — beta-tester welcome + onboarding sequence (DRAFT)

**Status:** DRAFT / copy only. A human sends these to approved testers. Nothing sent here.
**Owner:** launch-lead · **Reviewed against:** gtm-model, north-star (beta), voice, no-synergix-mention, copy-gate
**Audience:** approved beta testers — they HAVE repo access, so install/repo links are fine in these
1:1 messages (unlike public beta copy, which links trovex.dev only).
**Goal:** turn a waitlist signup into an activated tester (sees a real savings number) and a feedback/proof source.

> Voice: plain, founder-to-dev, no hype. The aha is the tester's own savings number. Ask for feedback like a
> person, not a survey funnel. No fabricated anything.

---

## The activation moment to engineer

A tester is "activated" the first time they run `trovex index` on a real doc-heavy repo and see the savings
view show a real number. Everything below is built to get them there fast, then ask what they think.

Sequence: (1) welcome/access → (2) day-2 what-to-try nudge → (3) ~day-5 feedback ask → (4) inactive re-nudge.

---

## 1. Welcome / "you're in" (sent on approval)

```
Subject: you're in — trovex beta

Hi [name],

Thanks for requesting access. You're in the trovex beta.

Quick context: trovex indexes your repo's markdown and serves your coding agent the one current doc that
answers a query (a path:line pointer with a freshness marker), instead of letting it reread a pile of .md
files each session. On a doc-heavy repo that's ~60% fewer tokens per lookup — and it ships a savings view
so you see the real number on your own repo.

Get set up (2 minutes):
1. Access the repo: [github.com/Synergix-lab/trovex — invite sent to your GitHub handle]
2. Install + index a real repo:
     uv sync
     uv run trovex index /path/to/a/doc-heavy/repo
3. Start it and point your agent at it:
     uv run trovex serve        # MCP at /mcp, UI at /
   [one-line MCP client config + the exact stdio flag — confirm against the CLI before sending]
4. Open the savings view to watch what it's saving.

The whole point of the beta is your feedback, so tell me where it picks the wrong "canonical" doc or feels
off. I read everything. Reply straight to this email or [feedback channel].

— [founder]
```
> Brand check: no company name. Repo/install OK (recipient has access). Confirm the stdio config line with
> eng before this goes out — don't send a config that doesn't run.

---

## 2. Day-2 "what to try" nudge (only if they haven't activated)

```
Subject: trovex — the 2-minute thing to try

Hi [name],

If you haven't had a chance yet: the fastest way to see whether trovex earns its place is to index your
most doc-heavy repo (lots of overlapping runbooks/ADRs/READMEs) and run a few real lookups through your
agent, then check the savings view.

If it's a small or tidy doc set, you'll see a small number — that's expected, and worth knowing too.

Anything in the way of getting it running? Tell me and I'll unblock you.

— [founder]
```

---

## 3. ~Day-5 feedback ask (after they've used it)

```
Subject: what did trovex actually save you?

Hi [name],

Now that you've run it on a real repo — two questions:
1. What did the savings view show on your corpus? (rough number is fine)
2. Where did it get the routing or the "canonical" call wrong?

Both are gold for me. The second one especially — I'd rather hear where it's weak.

And if it's been useful: would you be ok with me quoting you (name + a line) when trovex goes public? Only
with your say-so, and you'd see the exact wording first.

— [founder]
```
> The quote ask is the proof/testimonial source for the public launch. Permission-first, real words only —
> never invent or paraphrase into something they didn't say.

---

## 4. Inactive re-nudge (~day-10, if never activated; send once, then stop)

```
Subject: trovex — still worth a look, or not the right fit?

Hi [name],

Haven't seen you index a repo yet — no pressure. If it's not the right fit (small doc set, different
workflow), just say so and I'll stop nudging. If something blocked you, tell me what and I'll fix it. Either
answer helps me.

— [founder]
```
> One re-nudge only. If no response, leave them be — chasing burns goodwill.

---

## 5. Feeding proof (the point of the beta)

- Log each tester's real savings number + any quote (with permission) into a proof bank for the public launch.
- A bug or a "wrong canonical doc" report → file an issue, fix, tell the tester it shipped. That loop earns
  the strongest testimonials.
- No fabricated metrics or quotes, ever. Only what a tester actually ran/said.

## Guardrails

- These are 1:1 to approved testers — repo/install links OK here (they have access). Do NOT reuse this copy
  publicly (public copy links trovex.dev, no install).
- No hype, no fake urgency. Real ~60%, repo-dependent. No "Synergix". Consulting only if they raise it.
- Confirm the install + MCP config actually run before any send.
- Drafts only — a human sends. No automated sequence wired without cmo's ok.

*All copy above is a draft. Nothing has been sent.*
