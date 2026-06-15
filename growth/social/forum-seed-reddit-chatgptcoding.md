# r/ChatGPTCoding — seed post (DRAFT)

> **Status: DRAFT — do not post. A human fires this, from a real account with history.**
> Angle for this sub: people running Claude Code / Cursor / agents daily and feeling the
> token bill. Lead with the workflow pain. trovex = one option, not the headline.
> See `forum-seed-posting-notes.md` for rules + the 9:1 value-to-promo cadence.

---

## Title options

- `Anyone else's agent reread the whole repo every session just to find the right doc?`
- `How I cut my coding agent's token spend on doc lookups (~60% on those lookups)`
- `Stop your agent guessing which .md is canonical — route the query, don't dump the repo`

---

## Body

The thing that finally bugged me enough to fix: my agent (Claude Code) spends a real chunk
of every session rereading docs to figure out which one is the source of truth. Ask it "how
do we roll back a deploy?" and it opens `deploy/runbook.md`, an old `wiki/old-deploy.md`, and
a postmortem — to answer something it already answered last week. That's tokens (money) and a
context window full of stale files.

Things I tried:

1. **One big `CLAUDE.md`** — fine at first, then it goes stale and can't point at the right
   section once you have more than a few topics.
2. **Bigger context window** — doesn't help; a big window isn't a *current* one, and the
   agent still rereads to find the right doc. Cost just compounds across sessions and agents.
3. **Retrieval that returns one answer** — index the markdown, then on a query return the
   single current doc/section (`path:line` + a freshness marker: canonical / stale /
   duplicate), not a list of chunks to rank. This is what stuck.

On the lookups I measured, #3 is ~60% fewer tokens for the same answer — the agent reads one
section instead of three files. The other win is the write side: the agent saves an incident
or "the rollback steps that actually worked" once, and every other agent (and my teammate's
agent) reads it back instead of re-deriving it.

I've been doing this with **trovex** — open source, runs locally (SQLite + ONNX, no cloud or
keys), exposes it as an MCP tool so the agent just calls it. Repo:
github.com/Synergix-lab/trovex. It's one way to do it; the general move (route to one
canonical answer instead of dumping files) is the part worth stealing even if you roll your
own.

Curious how others handle this — do you gate doc reads through retrieval, keep a hand-tuned
instructions file, or just eat the cost?

---

## Self-audit
- [x] Leads with concrete workflow pain (the rollback example from the real landing demo).
- [x] Only number: ~60%, scoped to "lookups I measured". No invented metrics/users.
- [x] trovex mid-body as one option; ends on a question, not a pitch. Lowercase `trovex`.
- [x] No banned words. MCP angle fits the sub (they run agents).
