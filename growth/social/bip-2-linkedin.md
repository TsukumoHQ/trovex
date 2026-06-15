# Build-in-public update #2 — LinkedIn (DRAFT)

> **Status: DRAFT — do not post. Founder fires this.** LinkedIn build-in-public reflection,
> distinct from `linkedin-1/2/3`. Consulting one line, end. Link in first comment.
> No company name. No fabricated metrics. Only ~60%.

---

## Post

A thing I keep relearning while building in public: the costs that hurt most are the ones you
can't see.

I've been working on trovex — a small open-source tool that stops AI coding agents rereading
a repo's docs to guess which one is current. The whole reason it exists is a cost nobody puts
on a dashboard: every session, your agent quietly rereads the same `.md` files to re-answer
something it answered yesterday. No error, no warning. Just tokens, every time, across every
agent and teammate.

Once I actually measured it, the fix was almost boring: return the one current doc for a
query (with a freshness marker), not a pile of files to sift. About ~60% fewer tokens on those
lookups, same answers. The interesting part wasn't the retrieval. It was realizing how much
waste hides in "the agent is just reading files."

If your team runs agents daily, the most useful thing you can do this week is measure where
their tokens actually go. You'll probably be surprised. Helping teams find and fix that kind
of invisible waste is most of what I do. But you don't need me to start measuring.

---

## Posting notes
- Link to repo / trovex.dev → first comment only.
- Reply to early comments quickly; this format invites "how did you measure it?" questions.

## Self-audit
- [x] Build-in-public reflection, distinct angle (invisible cost) from prior LinkedIn posts.
- [x] Consulting one line, end-weighted, "you don't need me to start". Only ~60% claimed.
- [x] No company name, no fabricated metrics, no banned words. Lowercase `trovex`.
