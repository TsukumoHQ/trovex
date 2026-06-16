# LinkedIn #1 — build-in-public / ship announcement (DRAFT)

> **Status: DRAFT — do not post. A human (the founder) fires this.**
> Founder voice, first person, plain. Consulting surfaces ONCE, subtly, at the end.
> **Put the link in the FIRST COMMENT, not the post body** (a link in the caption
> tanks LinkedIn reach ~60%). Note added at the bottom. Only number claimed: ~60%.

---

## Post

I've been building a small tool, and the reason it exists is a number that annoyed me.

When you run AI coding agents on a real repo, a surprising share of their tokens goes to one
dumb task: rereading `.md` files to figure out which one is actually current. Runbooks, ADRs,
six READMEs — every session, every agent, the same lookup. The agent isn't reasoning. It's
re-finding.

So I built trovex. You point it at a repo; it indexes the markdown; then your agent asks a
question and gets back the one current doc that answers it — a `path:line` and a freshness
marker (canonical / stale / duplicate), not a pile of files to sift. On the lookups I
measured, that's about ~60% fewer tokens for the same answer.

It runs locally — SQLite, ONNX embeddings, no cloud, no API keys — because the people who
have this problem are also the people who don't want their repo leaving the machine.

The honest version: this isn't magic, it's retrieval done with some care (route to one answer
instead of dumping the repo). But the cost it removes is real, and it compounds — every
session, every agent, every teammate.

It's in a small private beta right now. If your team is running agents across a bunch of repos
and the token bill (and the drift between everyone's docs) is starting to hurt, request access
in the comments — that messier version is exactly the kind of thing I help teams sort out.

---

## Posting notes
- Link → trovex.dev beta (UTM) in **first comment**, not body:
  `https://trovex.dev/?utm_source=linkedin&utm_medium=social&utm_campaign=beta-waitlist#waitlist`
  Do NOT link the github repo — it's private during the beta.
- Best window: weekday morning; reply to early comments fast (reach is reply-weighted).
- No hashtag spam; 2-3 relevant tags max if any (#aiagents #devtools).
- Consulting line is the LAST paragraph only — never reorder it earlier.

## Self-audit
- [x] Founder first-person, build-in-public. Only ~60% claimed, scoped honestly.
- [x] Consulting once, at the end, framed as "help teams sort out", not a pitch.
- [x] No banned words. Lowercase `trovex`. Link-in-comment instruction included.
