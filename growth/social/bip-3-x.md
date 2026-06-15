# Build-in-public update #3 — X (DRAFT)

> **Status: DRAFT — do not post. Founder fires this.** A small honest design-decision note —
> the kind devs respect. Distinct from the others. No company name, no fabricated metrics.
> Only ~60% if used. Lowercase `trovex`.

---

## Post (short micro-thread, 2 posts)

**1/**
> small design decision in trovex that took longer than it should have:
>
> when the agent asks a question, do you return the best chunk, or the *current* doc? those
> aren't the same. the best-matching chunk might be in a stale file someone forgot to delete.

**2/**
> so every result carries a freshness marker (canonical / stale / duplicate) and the
> reranker uses it. the agent gets one current answer instead of a confident-looking old one.
>
> "right and current" beats "high similarity score" every time you're spending real tokens.

## Alt (single post)

> honest build note: the hard part of doc retrieval for agents isn't finding a match. it's
> not handing the agent a confident, stale answer.
>
> trovex marks every result canonical / stale / duplicate so "current" wins over "looks
> relevant". boring, but it's the whole game.

---

## Self-audit
- [x] Dev-honest design-decision note; distinct from launch thread / other BIP posts.
- [x] No number needed; if used, ~60% only. No company name, no fabricated metrics.
- [x] No banned words. Lowercase `trovex`. Single-idea posts.
