# Lobsters — seed submission (DRAFT)

> **Status: DRAFT — do not post. A human fires this.**
> Lobsters is the strictest community here and the least tolerant of marketing.
> The ONLY honest way in: submit a genuinely technical write-up, tag it, and check
> **"authored by submitter"** (mandatory if you're involved). Do NOT submit the
> landing page or a product announcement — that reads as a write-only promo channel,
> which is explicitly against the norms. Self-promo must stay a small fraction of
> your activity. See `forum-seed-posting-notes.md`.

---

## What to actually submit

A **technical blog post**, not the product. Lobsters wants the engineering, not the pitch.
The post should stand on its own as a RAG/retrieval write-up; trovex is the worked example.

Suggested post (to be written by content-lead / founder, then submitted here):

**Working title:** `Returning one canonical doc instead of a candidate list: hybrid retrieval for coding agents`

**Tags:** `ai`, `practices` (or `programming`) — pick from the live tag list at submit time.

**Why it fits Lobsters:** it's about a concrete retrieval design with real tradeoffs —
- structure-aware markdown chunking (split on headings, keep the heading breadcrumb in the
  embedded text) vs fixed-window chunking, and why the breadcrumb prefix is the main quality
  lever;
- hybrid dense + BM25 (FTS5) fused with reciprocal rank fusion (k=60) so exact tokens —
  function names, IDs, error codes — survive that pure embeddings blur;
- a status-aware reranking step that marks results canonical / stale / duplicate so the agent
  gets one current answer with a freshness signal instead of a pile to sift;
- the honest part: most of these (RRF, small-to-big, listwise rerank) are folklore from
  libraries/blogs, not single-paper inventions — the post says so rather than over-citing.

That last point matters on Lobsters: the audience rewards intellectual honesty and punishes
overselling. The post links the implementation (github.com/Synergix-lab/trovex) once, as the
reference, not as a CTA.

---

## If submitting the repo directly instead (less ideal)

Only if there's no write-up yet. Submit the GitHub repo, tag `ai` + `release` (or
`show`-equivalent per current tags), check **authored by submitter**, and write a plain
one-paragraph text describing what it does and the one real number (~60% fewer tokens on doc
lookups) — no superlatives. Expect tougher scrutiny than a write-up; the comment section is
the value, so be present to answer technical questions honestly.

---

## Comment-reply seeds (for when questions land)

- *"How is this different from plain RAG?"* → RAG returns ranked candidate chunks to sift;
  this returns the single canonical doc/section with a freshness marker, and closes the write
  loop (agent saves a record once, all agents read it back). One point of passage = SSOT.
- *"Why not just a bigger context window?"* → Cost compounds across sessions/agents, and a big
  window isn't a current one — you still need to route to the *right* doc.
- *"Is it local?"* → Yes; SQLite + ONNX embeddings, no cloud or API keys, code stays on the
  machine.

---

## Self-audit
- [x] Submission is a technical write-up, not the product/landing — respects Lobsters norms.
- [x] "Authored by submitter" flagged as mandatory. Self-promo-ratio rule cited.
- [x] Only number: ~60%, scoped to doc lookups. Honesty about folklore vs citations baked in.
- [x] No banned words. Lowercase `trovex`. Link appears once, as reference.
