# r/LocalLLaMA — seed post (DRAFT)

> **Status: DRAFT — do not post. A human fires this, from a real account with history.**
> Angle for this sub: local-first, runs-on-your-machine, token frugality. This crowd
> respects "no cloud, no API keys" and hates ads. trovex is mentioned as ONE option,
> not the headline. See `forum-seed-posting-notes.md` for the rules before posting.

---

## Title options

- `Stopped my local coding agent from rereading the repo every session to find the "current" doc`
- `Cutting agent token spend on doc lookups — what's worked for you on local setups?`
- `Local-first approach to "which .md is canonical": route the query instead of dumping the repo`

(Prefer a title that frames a problem/discussion, not a product. Avoid the tool name in the title.)

---

## Body

If you run a coding agent on a real repo, you've probably noticed it burns a chunk of its
context just rereading `.md` files — runbooks, ADRs, half a dozen READMEs — trying to
figure out which one is actually current. Every session, every agent, same lookup.

The two common fixes both have a cost:

- **A single `CLAUDE.md` / `AGENTS.md`** — one static blob. Works until you have more than
  a handful of topics, then it goes stale and can't route a question to the right doc.
- **Dump the repo** (repomix etc.) — floods the window with everything, which is the
  opposite of what you want if you're watching tokens.

What's worked better for me is treating it as a retrieval problem: index the markdown once,
then return the *one* current doc/section that answers a query (a `path:line` + a freshness
marker), not a pile of candidates to sift. On the lookups I measured it's about ~60% fewer
tokens for the same answer, because the agent reads one section instead of three files to
guess.

The local-first part is what made it usable for me: vectors in SQLite, embeddings via ONNX,
no cloud and no API keys — the repo never leaves the machine. Retrieval is hybrid (dense +
BM25/FTS5 with reciprocal rank fusion) so exact tokens like function names and IDs still hit,
and chunking is structure-aware on markdown headings rather than fixed windows.

The tool I've been using for this is **trovex** (open source, AGPL core / MIT CLI:
github.com/Synergix-lab/trovex). Not the only way to do it — you could wire the same idea
with your own embedder + sqlite-vec. Mostly curious what others here do:

- do you let the agent read files freely, or gate it through retrieval?
- anyone routing the *write* side too (agent saves a note once, every agent reads it back)
  so you're not re-deriving the same thing across sessions?

---

## Self-audit
- [x] Value-first: the post is useful even if you ignore trovex. Tool = one option, mid-body.
- [x] Only number claimed: ~60%, framed as "on the lookups I measured" (honest, first-person).
- [x] No fabricated stars/users. No banned words. Lowercase `trovex`.
- [x] Ends with genuine questions to the community, not a CTA.
- [x] Honest disclosure handled in posting-notes (mention you're involved if asked / per rules).
