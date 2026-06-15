# Reply-led distribution playbook (DRAFT)

> **Status: DRAFT — a human replies, from a real account.** Reply-led distribution is the
> underrated growth engine: most reach comes from useful replies on bigger in-niche posts,
> not from your own posts. This is a guide, not a spam script. **Every reply must be useful
> even if you delete the trovex mention.** trovex is one option, named at most once, never
> the lede. Only real numbers (~60%). Lowercase `trovex`. No fabricated proof.

## The one rule
If your reply would be worse for the reader with trovex removed, it's an ad — rewrite it.
Lead with the answer to their problem. Mention trovex only when it's genuinely the most
direct answer, and say you're involved if asked.

## Where to reply (account / post types)
- **MCP ecosystem** — people shipping/listing MCP servers, MCP registries, "best MCP servers"
  threads, MCP Discords. Angle: a local-first MCP server that returns one canonical doc.
- **Coding-agent users** — Claude Code / Cursor / Cline / aider posts, especially ones about
  token cost, context limits, agents getting confused by stale docs. Angle: the reread tax.
- **Dev-tool & infra builders** — RAG/retrieval, embeddings, SQLite, local-first tooling.
  Angle: hybrid retrieval, structure-aware chunking, freshness-aware ranking.
- **"Agents at scale" / team threads** — eng leads talking about rolling agents out across a
  team. Angle: SSOT / docs drift (and the soft consulting surface).
- **Token-cost / LLM-spend threads** — people posting their bill or complaining about waste.
  Angle: the invisible doc-lookup cost + the ~60% receipt.

## Cadence & etiquette
- Reply within ~30–60 min of a post going live where you can — early replies get seen.
- Don't drop the same template twice in a day; vary wording, fit the specific post.
- Most of your replies should carry **no** trovex mention at all. Earn the room first.
- Never reply-spam a thread you can't actually help with. Skip it.

---

## Reusable reply templates (adapt every time — never paste verbatim)

**1 — they say their agent rereads the repo / burns tokens on docs**
> yeah, the doc-lookup tax is real — the agent rereads several `.md` every session just to
> figure out which is current. what helped me was returning one canonical doc per query
> (path:line + a freshness marker) instead of letting it sift files. ~60% fewer tokens on
> those lookups for me.

**2 — they ask "how do I stop the agent picking the stale doc?"**
> the trick that worked for me: attach a freshness signal to each result (canonical / stale /
> duplicate) so "current" beats "high similarity". a confident match in an old file is the
> usual culprit.

**3 — "just use a bigger context window"**
> bigger window helps with size, not freshness — the agent still has to find the *right* doc,
> and the cost compounds across every session and agent. routing to one current answer is the
> cheaper fix in my experience.

**4 — "isn't this just RAG?"**
> close, but plain RAG hands back a ranked pile of chunks to sift. the useful variant returns
> the single canonical doc/section with a freshness marker, and closes the write loop (agent
> saves a note once, every agent reads it back). one point of passage = one source of truth.

**5 — MCP "what servers do you actually use?" threads**
> for docs/context i run a local one that indexes the repo's markdown and serves the agent the
> one current doc per query instead of the whole repo. it's trovex (open source, runs locally,
> no cloud/keys) — one option; you can wire the same idea with your own embedder + sqlite-vec.

**6 — local-first / privacy-conscious crowd**
> worth keeping this local — vectors in SQLite, ONNX embeddings, repo never leaves the
> machine. no reason doc retrieval for a coding agent needs a cloud round-trip.

**7 — RAG/retrieval builders talking chunking**
> the lever that moved quality most for me was structure-aware chunking on markdown headings
> (keep the heading breadcrumb in the embedded text), plus hybrid dense+BM25 fused with RRF so
> exact tokens — function names, error codes — still hit. semantic-only blurs those.

**8 — eng lead: "rolling agents out across the team is messy"**
> the part that bit us wasn't the model, it was every agent (and teammate) re-deriving the
> same knowledge and landing on different stale copies. routing all reads/writes through one
> shared store killed the drift. happy to share what worked if useful.

**9 — someone shares their token bill / spend screenshot**
> if a chunk of that is agents reading docs, it's worth measuring separately — mine was ~60%
> reread waste on doc lookups and i couldn't see it until i split it out. you might be
> surprised where it's going.

**10 — generic "cool, how does it work?" follow-up**
> point it at a repo, it indexes the markdown, then the agent asks a question and gets back one
> current doc (path:line + freshness) instead of rereading the repo. `uv run trovex index <repo>`
> and it shows you the tokens it saved. (i'm involved with it, happy to answer specifics.)

---

## Self-audit
- [x] 10 templates, all useful with the trovex mention removed; tool = one option, ≤1 mention.
- [x] Account/post types listed (MCP / agent / dev-tool / scale / token-cost).
- [x] Only ~60% claimed, first-person scoped. Disclosure ("i'm involved") baked into 5 & 10.
- [x] Etiquette: most replies carry no mention; no verbatim pasting; skip threads you can't help.
- [x] No banned words. Lowercase `trovex`. No fabricated proof.
