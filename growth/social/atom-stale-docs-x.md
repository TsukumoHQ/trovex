# X thread — repurpose: why agents pick the stale doc (DRAFT)

> **Status: DRAFT — do not post. Human fires this.** Repurposed from cornerstone
> `growth/blog/why-agents-pick-stale-docs.md`. Sharp contrarian insight angle. Beta CTA, UTM
> #waitlist link in a reply. Only ~60% if used. No install-now/repo link. Lowercase `trovex`.
> Passed copy-gate.

## Links (in the CTA reply)
- beta: `https://trovex.dev/?utm_source=x&utm_medium=social&utm_campaign=beta-waitlist#waitlist`
- full write-up: `trovex.dev/blog/why-agents-pick-stale-docs`

---

## Thread

**1/ hook**
> your coding agent keeps citing the old runbook. it's not dumb — it's doing exactly what
> retrieval tells it to.
>
> similarity search ranks by "most relevant", not "most current". and a stale doc is just as
> relevant as the live one 👇

**2/**
> `wiki/old-deploy.md` and `deploy/runbook.md` are about the same topic. to a vector store or
> grep, they score about the same. nothing in plain RAG knows which one is authoritative.

**3/ the twist**
> the stale one often scores *higher*. abandoned docs tend to be longer and more keyword-dense
> — they accreted edits before everyone moved on. so "most similar" lands on the corpse.

**4/ the fix isn't a better embedding**
> no embedding model knows your runbook moved. the fix is a freshness signal attached to each
> doc — canonical / stale / duplicate — so the superseded copy gets skipped, not ranked.

**5/**
> that's the piece i kept missing building retrieval for agents: relevance and currency are
> different questions. you have to answer the second one explicitly.

**6/ CTA (links in this reply)**
> i built this into trovex (freshness-marked canonical answers, ~60% fewer tokens per lookup
> as a side effect). it's in private beta — request access. write-up explains the ranking.
> [links in reply]

---

## Self-audit
- [x] Insight-led (stale scores higher), distinct from comparison/flagship threads.
- [x] Beta CTA + UTM #waitlist; no install-now/repo link. Only ~60%. Faithful to cornerstone.
- [x] No banned words. Lowercase `trovex`. No Synergix.
