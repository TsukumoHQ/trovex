# LinkedIn — flagship repurpose: the reflection (DRAFT)

> **Status: DRAFT — do not post. Founder fires this.** Repurposed from the flagship blog post,
> distinct from the X thread (that one is the math; this is the reflection + the honesty
> caveat). Single post. Link to the blog in the FIRST COMMENT. Only real numbers. Lowercase
> `trovex`. Passed copy-gate.

---

## Post

I wrote up something I'd been hand-waving about: the actual token cost of coding agents
rereading your docs.

Here's the part that surprised me when I priced one lookup. Ask the agent "how do we roll back
a deploy?" and it reads three candidate files (the current runbook, an old duplicate, a
postmortem), about 720 tokens, to answer a question worth 280. Roughly 440 of those tokens
went to reading files it then discarded. You're not paying for the answer. You're paying for
the guessing. And you pay it again every session, every agent, every teammate, because the
window doesn't persist.

Serve the agent the one current doc instead (with a freshness marker, section-level), and that
lookup drops from ~720 to ~280 tokens. Across a session it averages about 60% off the
doc-reread slice.

Two honest things, because the number gets quoted without them:

1. That's the doc-lookup part of the bill, not the whole bill. Your agent also reads code and
   reasons. trovex cuts the markdown-rereading slice — big on a doc-heavy repo, small on a
   tiny one.
2. ~60% is representative, not a promise. The point of the savings dashboard is that you
   measure your own number instead of trusting mine.

If your team runs agents across a doc-heavy repo and that rereading tax is a daily line item,
that's the kind of thing we help teams fix. The write-up (with the full math) is in the
comments.

---

## Posting notes
- Link → first comment: trovex.dev/blog/the-token-cost-of-agents-rereading-docs
- Reply to early comments fast; the "how did you measure it?" question is the opening.

## Self-audit
- [x] Distinct from X thread (reflection + caveats) and from linkedin-1/2/3 (cost-math angle).
- [x] Real numbers only (720→280, ~60%); both honesty caveats kept; consulting one line, end.
- [x] Link in first comment. No banned words. Lowercase `trovex`. No Synergix prose.
