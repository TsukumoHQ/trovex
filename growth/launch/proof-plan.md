# trovex — beta-proof capture plan (DRAFT)

**Status:** DRAFT / plan only. Proof is captured from real beta testers; nothing fabricated, nothing public yet.
**Owner:** launch-lead · **Reviewed against:** gtm-model, north-star (beta), voice, no-synergix-mention, copy-gate
**Goal:** systematically turn beta usage into honest, permissioned proof (savings numbers + quotes + case
studies) that powers the public launch. Pairs with content-lead's case-study template.

> The whole reason for a private beta is to walk into the public launch with real proof instead of an
> unsupported claim. Capture it on the way, with consent. Never invent or embellish.

---

## What counts as proof (in priority order)

1. **A real savings number** from a tester's own repo (the savings view: would-have-read vs. actual). The
   strongest asset because it's the ~60% claim, verified on someone else's corpus.
2. **A short quote** in the tester's own words (a sentence on what it fixed). Permission-first.
3. **A mini case study**: tester's context (repo size / doc-heaviness / agent setup) → number → quote.
4. **A bug-fixed loop**: they reported X, it shipped, they confirmed. Earns the most credible testimonials.

What does NOT count: anything you paraphrase into something they didn't say, a number you didn't see, a logo
you weren't given permission to use. Pre-launch = zero fabricated proof, always.

---

## Where it gets captured (light, no heavy tooling)

The capture points are already in the onboarding flow (beta-onboarding.md) — this plan just makes them
deliberate:
- **Day-5 feedback email** asks the two questions (savings number + where routing was wrong) + the quote ask.
- **In-product**: if feasible, a one-click "share this savings number" from the savings view (hand the event
  to analytics-lead; a screenshot the tester sends is fine for v1).
- **Bug/feature threads**: when a report is shipped, ask "ok to quote you on this when we go public?"

Store everything in one place: a simple **proof bank** (a doc/sheet), one row per tester.

### Proof bank fields (one row per tester)
```
tester (handle/first name) | repo context (size, doc-heavy?) | savings number (real) | quote (verbatim) |
consent: none / quote-anon / quote-named / logo | source (email/Discord/issue) | date | used-where
```
- **Consent is a field, not an afterthought.** Default to none; only use what each tester explicitly granted,
  at the granularity they granted (anonymous vs. named vs. company/logo).

---

## Consent (the rule that keeps it honest + safe)

- Always ask before using anything publicly. The day-5 email already asks; record the answer.
- Offer levels: (a) anonymous ("a beta user on a large docs repo"), (b) first name + role, (c) name + company,
  (d) logo. Use the lowest level granted, never higher.
- Show the exact wording before it goes live; let them edit or pull it.
- Someone can revoke later — keep proof revocable (don't hard-bake a quote you can't pull back).

---

## Where the proof gets used (at public launch, per unfreeze-checklist.md step 4)

- **PH gallery + maker comment**: a real savings number + a quote (the strongest slide).
- **Show HN first comment / answers**: "measured on beta users' repos too, not just mine" — folds into the
  faq-bank.md "does it really save 60%" answer.
- **Landing**: a proof strip (numbers + quotes) once there's consent — hand to content-lead/cro-lead.
- **Case studies**: 1–2 fuller write-ups with content-lead's template, for the doc-heavy-team ICP.

---

## Hand-offs

- **content-lead**: owns the case-study template + the landing proof strip; I feed the proof bank rows.
- **analytics-lead**: the in-product "share savings" event + activation tracking.
- **cro-lead**: where proof sits in the waitlist/landing conversion path.
- **cmo**: decides when there's enough proof to lift the public hold (unfreeze-checklist.md §0 gate).

## Guardrails

- Permission-first, verbatim quotes, real numbers only. No fabrication, no logos without grant.
- Proof is repo-dependent — keep the "on a doc-heavy repo" qualifier with every number.
- No "Synergix". Drafts/plan only — capturing proof in beta is fine; publishing it waits for the public phase.

*This is a plan. No proof has been published.*
