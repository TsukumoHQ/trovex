# LinkedIn #3 — the savings receipt (DRAFT)

> **Status: DRAFT — do not post. A human (the founder) fires this.**
> Short, number-led, screenshot-driven. The savings receipt IS the post. Attach the
> dashboard screenshot (would-have-read vs actual). Link in first comment. Use the real
> number — ~60%, or your own measured receipt. Never invent it.

---

## Post

Here's a screenshot I didn't expect to find satisfying.

[attach: trovex savings dashboard — "would have read vs actual read", ~60% reduction]

It's the doc-lookup token spend for a coding agent, before and after I routed its reads
through one canonical store instead of letting it reread the repo to guess which `.md` was
current.

Same answers. About ~60% fewer tokens on those lookups.

Two things I took from it:

1. The waste was invisible until I measured it. The agent never complained — it just quietly
   reread three files to answer something it already knew. You don't feel it per call; you
   feel it on the bill.

2. The fix was boring in the best way: return the one current doc (with a freshness marker),
   not a pile of candidates. No bigger model, no bigger window.

The tool that produces this receipt (trovex) runs locally, and it's in a small private beta
right now. If you run agents daily, this is the kind of waste worth measuring on your own repo
— request access in the comments and you can run the receipt yourself. You'll probably be
annoyed by what you find too.

(If it's a whole team's worth of agents quietly doing this, that's the scale where it stops
being an afternoon and starts being worth a conversation — which is part of what I do.)

---

## Posting notes
- The SCREENSHOT carries this post — make it legible, real numbers only, no mockup-as-real.
- Link → trovex.dev beta (UTM) first comment, NOT the repo (private during beta):
  `https://trovex.dev/?utm_source=linkedin&utm_medium=social&utm_campaign=beta-waitlist`
- Keep it short on LinkedIn; the image + the number do the work.

## Self-audit
- [x] Number-led but honest: ~60% scoped to "those lookups", receipt = real screenshot only.
- [x] Consulting in a parenthetical at the very end — lowest-key of the three.
- [x] No fabricated proof. No banned words. Lowercase `trovex`.
