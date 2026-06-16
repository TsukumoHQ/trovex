# LinkedIn — repurpose: MCP context patterns (DRAFT)

> **Status: DRAFT — do not post. Founder fires this.** Repurposed from cornerstone
> `growth/blog/mcp-context-patterns-for-coding-agents.md`. Framework post (dump / retrieve /
> answer). Beta CTA, UTM #waitlist link in first comment. Only ~60%. No install-now/repo link.
> Lowercase `trovex`. Passed copy-gate.

## Link (first comment)
- beta: `https://trovex.dev/?utm_source=linkedin&utm_medium=social&utm_campaign=beta-waitlist#waitlist`
- full write-up: `trovex.dev/blog/mcp-context-patterns-for-coding-agents`

---

## Post

When you wire project knowledge into a coding agent over MCP, you're really picking one of
three patterns. Most teams pick by accident. It's worth picking on purpose.

1. Dump the repo. Return a big slab of code/docs (repomix, files-to-prompt). Simple, and it
   floods the window — you pay for the whole corpus to use a fraction of it.

2. Retrieve candidates. Return a handful of chunks ranked by similarity (plain RAG). Cheaper
   than dumping, but it hands the agent a pile to sift, with no signal for which chunk is
   current. A stale chunk and a live one look equally relevant to a score.

3. Answer. Return the single canonical doc that answers the query — a path:line with a
   freshness marker, section-level. The agent gets one current answer instead of a research
   task.

For a tiny repo, dumping is fine. For exploratory code search, retrieval fits. But for
doc-heavy, multi-session, multi-agent work, the answer pattern wins on both axes that matter:
about 60% fewer tokens per lookup, and you actually get the *current* doc instead of a
confident stale one.

I'm building the answer pattern as trovex (local, MCP, private beta right now). If you're
deciding how to feed your agents context, the write-up lays out the trade-offs — and if you
want to try the answer pattern on a real repo, request access in the comments.

---

## Posting notes
- Link → first comment with the beta UTM above; write-up link alongside. Not the post body.
- Reply fast; "which pattern are you using?" is a good comment prompt.

## Self-audit
- [x] Framework post (dump/retrieve/answer), faithful to cornerstone; distinct from prior posts.
- [x] Beta CTA + UTM #waitlist; no install-now/repo link. Only ~60%. Consulting-light, value-first.
- [x] No banned words. Lowercase `trovex`. No Synergix.
