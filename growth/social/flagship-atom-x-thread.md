# X thread — flagship repurpose: the cost teardown (DRAFT)

> **Status: DRAFT — do not post. Human fires this.** Repurposed from the flagship blog post
> `growth/blog/the-token-cost-of-agents-rereading-docs.md`. Angle = the *arithmetic* (the
> guessing tax), which is what the blog adds over the launch thread. Lead with the number.
> Link to the blog in a REPLY, not the hook. Only real numbers (~60%, 720→280). Lowercase
> `trovex`. Passed copy-gate.

---

## Hook (tweet 1)
> i priced out what my coding agent spends just rereading docs to guess which one is current.
>
> one deploy-rollback lookup: ~720 tokens. ~440 of them went to reading two files it then
> threw away. the cost wasn't the answer. it was the guessing. 👇

## 2/
> why it happens: a real repo has overlapping markdown — a current runbook, an old
> `wiki/old-deploy.md`, a postmortem that mentions rollback. the agent has no freshness
> signal, so it opens the candidates and reads enough of each to decide which to trust.

## 3/
> and it does this from a cold start every session. the window doesn't persist, so the same
> lookup gets paid for again tomorrow, again by the next agent, again by your teammate's agent
> on the same repo.

## 4/ the math (this is the whole point)
> without an index, one lookup:
>   runbook (current)      ~280
>   old-deploy (stale)     ~240  ← discarded
>   postmortem (stale)     ~200  ← discarded
>   total                  ~720
> with one canonical answer served: ~280. same answer.
> 720 → 280 ≈ 61% fewer tokens on this lookup.

## 5/
> across a session of mixed lookups it averages ~60% off the doc-reread slice. honest caveat:
> that's the doc-lookup portion of the bill, not your whole bill. on a doc-heavy repo with a
> lot of agent traffic, that slice is big.

## 6/
> the fix isn't a bigger model or a bigger window. a bigger window doesn't make the reread
> cheaper, it makes it bigger — and it'll happily hold three conflicting docs and answer from
> the wrong one. you want the *right* doc, cheaply.

## 7/ CTA (link in this reply)
> trovex does this: index your repo's markdown, serve the agent one current doc per query
> (path:line + freshness), section-level. local, no cloud/keys.
>
> full teardown w/ the numbers: trovex.dev/blog/the-token-cost-of-agents-rereading-docs

---

## Self-audit
- [x] Distinct from launch-thread (this = cost arithmetic, not product overview).
- [x] Leads with the number; only real figures (720→280, ~60%); doc-slice caveat kept.
- [x] Link in reply. No banned words. Lowercase `trovex`. No Synergix prose (URL via trovex.dev).
