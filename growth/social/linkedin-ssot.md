# LinkedIn — local-first / SSOT for a fleet of agents (DRAFT)

> **Status: DRAFT — do not post. Founder fires this (no LinkedIn creds in env).**
> Angle: SSOT-by-construction + local-first, distinct from the earlier agents-at-scale post
> (that one was about drift). Consulting surfaces once, end. Beta framing: "request access",
> no install-now, no private-repo link. Link → first comment with UTM. Only ~60% if used.
> Lowercase `trovex`. Passed copy-gate.

## UTM link (first comment)
`https://trovex.dev/?utm_source=linkedin&utm_medium=social&utm_campaign=beta-waitlist`

---

## Post

Run more than one coding agent on the same repo and you hit a problem that has nothing to do
with the model: they don't share a memory.

Agent A figures out the deploy rollback. Agent B, next session, re-derives it and maybe lands
on the stale doc. Your teammate's agent has a third version. Everyone's working from their own
copy, and the copies drift. The usual fixes paper over it: a shared doc that goes stale, a
wiki nobody updates, a CLAUDE.md that was right last quarter.

The thing I kept coming back to while building trovex: you don't fix drift by syncing copies.
You fix it by not having copies. If every read and every write goes through one store, there's
one source of truth by construction. An agent learns something, writes it once; every other
agent and every teammate reads the same thing back. Nothing to sync, nothing to reconcile.

Two design choices that made this usable for real teams:

1. The write path is the point. Retrieval alone wouldn't fix drift. Agents save incidents,
   decisions, "the rollback steps that actually worked" through one shared point, so knowledge
   accrues instead of evaporating at the end of a session.

2. It runs locally. Vectors in SQLite, embeddings via ONNX, no cloud and no keys. A shared
   source of truth for your agents shouldn't mean shipping your repo to someone else's server.

The token savings (about 60% fewer on doc lookups) are the easy thing to measure. The quieter
win is that your fleet stops contradicting itself.

I'm running a small private beta. If you've got a few people and a pile of agents working the
same repo, that consistency problem is exactly what I want to test against — and helping teams
get this right is most of what I do. Request access in the comments.

---

## Posting notes
- Link → first comment with the UTM above. Reply fast to early comments.
- Beta framing only: "request access", never install-now / repo link (repo private during beta).

## Self-audit
- [x] SSOT-by-construction + local-first angle; distinct from prior LinkedIn/BIP posts.
- [x] Consulting one line, end-weighted. Beta "request access" framing, UTM link in comment.
- [x] Only ~60% claimed; no fabricated proof. No banned words. Lowercase `trovex`. No Synergix.
