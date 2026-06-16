# X thread — why a static CLAUDE.md fails at scale (DRAFT)

> **Status: DRAFT — do not post. Human fires this (no X creds in env).**
> Angle: the most common objection ("i already use CLAUDE.md"). Lead with concrete pain,
> show the fix, end on beta access. CTA link in a REPLY with UTM. Only ~60% claimed.
> Private-beta framing: "request access", no install-now, no private-repo link. Lowercase
> `trovex`. Passed copy-gate.

## UTM link (in the CTA reply)
`https://trovex.dev/?utm_source=x&utm_medium=social&utm_campaign=beta-waitlist#waitlist`

---

## Thread

**1/ hook (concrete pain)**
> your `CLAUDE.md` was perfect in week one. by month three it says the deploy runbook lives in
> `wiki/`, the wiki moved twice, and your agent confidently tells you the old rollback steps.
>
> a single static file can't keep up with a repo. here's what breaks 👇

**2/**
> a CLAUDE.md / AGENTS.md is one blob pinned into context. it's a sticky note, not an index.
> three things go wrong as the repo grows:

**3/ it goes stale**
> nothing tells the file it's wrong. you edited the real runbook; the CLAUDE.md pointer still
> aims at last quarter's doc. the agent trusts it, because it has no freshness signal.

**4/ it doesn't scale past a few topics**
> one file can hold a handful of rules. it can't hold "the canonical doc for every subsystem".
> past a certain size you're back to the agent rereading the repo to find the real answer.

**5/ it can't route**
> "how do we roll back a deploy?" needs the rollback section of one specific doc. a static blob
> can't point at a `path:line` and a section. it just dumps everything it knows and hopes.

**6/ the fix isn't a bigger CLAUDE.md**
> it's an index with a freshness signal. keep many docs canonical, and on a query return the
> one current doc/section — `path:line`, marked canonical / stale / duplicate — not a blob.

**7/ what that buys you**
> the agent stops rereading three files to guess, and stops answering from the stale one. same
> answers, about ~60% fewer tokens on doc lookups. keep your CLAUDE.md for high-level rules;
> let the index handle "which doc, which section, is it current".

**8/ CTA (link in this reply)**
> i'm building this as trovex and running a small private beta. if your CLAUDE.md has quietly
> gone stale on a real repo, request access: [trovex.dev beta link w/ UTM]

---

## Self-audit
- [x] Leads with concrete pain (stale CLAUDE.md → wrong rollback). Comparison, not a pitch.
- [x] Beta framing: "request access", no install-now, no private-repo link. UTM in CTA reply.
- [x] Only ~60% claimed; honest "keep your CLAUDE.md for high-level rules". No fabricated proof.
- [x] No banned words. Lowercase `trovex`. No Synergix. Distinct from prior threads.
