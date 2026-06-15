# trovex — objection + FAQ answer bank (DRAFT)

**Status:** DRAFT / copy only. The founder posts these as replies; nothing posted live here.
**Owner:** launch-lead · **Reviewed against:** product-marketing-context.md, voice, no-synergix-mention, copy-gate
**Use:** the single source of truth for answering questions on HN, Product Hunt, r/mcp, MCP Discords,
and registry comment threads. show-hn.md §5 and product-hunt.md §6 point here. Personalize per thread;
never paste the same wording twice in the same venue.

> Voice: developer-honest, plain, concede real limits. The strongest answer admits where trovex doesn't
> help. No company name. Real ~60% only, always framed as measured-on-my-repos + check-it-yourself.

---

## A. "How is this different from X?"

**vs CLAUDE.md / AGENTS.md / .cursorrules**
> Those are one static file you maintain by hand. They work until the corpus grows: no per-query routing,
> no signal for which doc is current vs. stale, and they drift the moment someone forgets to update them.
> trovex keeps many docs and serves the one that answers the question, with a freshness marker, so the
> agent isn't treating a three-week-old note as gospel. You can use both — a short CLAUDE.md for rules,
> trovex for the doc corpus.

**vs repomix / files-to-prompt / "just dump the repo"**
> Dumping floods the context window with everything, which is the opposite of what I wanted. The point of
> trovex is to send one section, not the whole corpus. Big context isn't free and it isn't the same as
> the right context.

**vs plain RAG / a vector-search MCP server**
> Mechanically it's embeddings + vector search, yes. The difference is the output. Most RAG servers hand
> back N candidate chunks for the model to rank. trovex returns the single canonical doc (path:line +
> freshness) and lets the agent read just the section it needs, plus a write path so agents share one
> store. It's opinionated about giving one answer instead of a pile to sift.

**vs a bigger context window**
> Cost compounds: every session, every agent, every teammate pays to reread. And a bigger window still
> lets the agent pick the stale file. trovex is about the right doc cheaply, not more doc.

**"Isn't this just a glorified grep / ctags for markdown?"**
> grep finds matches; it doesn't tell you which of five matching docs is the current one. The freshness
> marker (canonical / stale / duplicate) is the part grep can't do, and the section-level read is what
> keeps the token cost down.

---

## B. "Does it really save ~60%?"

**How is the number measured?**
> It's tokens spent on .md reads for a lookup: serving one section plus pointers, versus the agent reading
> the top candidate files to decide which is canonical. Measured on my own repos, not a benchmark I'm
> asking you to take on faith. The tool ships a savings view so you can see would-have-read vs. actual on
> your corpus and check it yourself.

**"That sounds cherry-picked."**
> Fair. It's repo-dependent and I try to say so everywhere. On a doc-heavy repo with lots of overlapping
> markdown the saving is big; on a small or tidy doc set it's small, and the tool will show you a small
> number rather than flatter you. I'd rather under-promise than have you install it and feel lied to.

**"Token cost is tiny, why bother?"**
> For one dev on one session, sure. It adds up across a fleet of agents and a couple of teammates running
> all day. And the bigger win is often correctness, not dollars: stopping the agent from acting on the
> stale doc.

---

## C. "Why local? / privacy"

**Does it phone home? Where do my docs go?**
> Nowhere. Embeddings run on-device (fastembed, ONNX under the hood), vectors live in a local SQLite db
> (sqlite-vec). No cloud, no API keys, nothing leaves your machine. It's open source — you can read the
> code or run it air-gapped.

**Why not a hosted service?**
> Local-first is deliberate: your code's docs are sensitive, and a tool that pays for itself shouldn't add
> a per-seat bill or a data-egress question. You run it where the repo already is.

---

## D. License / business

**AGPL? That's a non-starter for my company.**
> The core is AGPL-3.0, the CLI is MIT. You can self-host and modify freely. AGPL only bites if you run a
> *modified* version as a network service and don't share your changes. If a team needs to embed or host it
> privately without that obligation, reach out and we'll sort it.

**What's the catch / how does this make money?**
> The tools are free and open. I do consulting for teams running AI coding agents at scale, and trovex is
> one of the tools I build and use. If you just want the OSS, take it — no upsell. If your team wants help
> running agents well, that conversation is open.
> *(Keep this casual. It's a door, not a pitch. Only expand if directly asked.)*

---

## E. Compatibility / setup

**Which agents/clients does it work with?**
> Anything that speaks MCP — it exposes a standard MCP server (Claude Code, Cursor, and other MCP clients).
> The config snippet is in the README. *(Confirm the exact stdio invocation against the CLI before this
> goes live — don't post a config that doesn't run.)*

**How hard is setup?**
> Index a repo and serve, a couple of commands (README has the copy-paste). No accounts, no keys.

**Does it watch the repo / stay fresh as docs change?**
> *(Founder/eng: answer with the real reindex behavior — on-demand vs. watch. Fill in accurate detail;
> don't guess in public.)*

**How does it decide which doc is "canonical"? What about the write path and two agents at once?**
> *(Founder/eng: describe the real mechanism — single point of passage, how duplicates/staleness are
> flagged, how concurrent writes are handled. This is the question a sharp HN reader will push on, so it
> needs an accurate, specific answer, not hand-waving.)*

**Does it handle non-markdown (code comments, PDFs, Notion)?**
> Today it's the repo's markdown corpus. *(State the real current scope; note roadmap only if true.)*

---

## F. Skeptic / hard questions (answer head-on, don't dodge)

**"This is a thin wrapper over sqlite-vec + an embedding model."**
> The retrieval is standard, on purpose — the value isn't a novel index, it's the opinionated output (one
> canonical doc + freshness) and the shared write path that keeps a fleet of agents on the same source of
> truth. If that's not a problem you have, it won't be interesting, and that's fine.

**"Why would I trust a freshness marker over my own judgment?"**
> You shouldn't blindly — it's a signal, not a verdict. It flags the doc the store considers current and
> marks likely-stale/duplicate ones so the agent stops defaulting to whatever it read first. You can always
> open the file.

**"Pre-launch, no users — why should I care?"**
> No reason to take it on reputation. It's open source and installs in a minute; run it on your own repo and
> look at the savings view. If the number's not worth it for your setup, walk away — I'd rather you decide
> on your repo than my claim.

**"Maintained, or a weekend project?"**
> *(Founder: one honest sentence on commitment + the next thing you're building, e.g. better freshness
> signals / more client configs. Don't overpromise a roadmap.)*

---

## G. Things to NEVER say (guardrails)

- No fabricated proof: no invented users, stars, "trusted by", testimonials, or made-up benchmarks.
- No superlatives, no hype words (revolutionary / seamless / supercharge / unlock / AI-powered).
- No "Synergix" — the business is never named in any answer. The repo URL is the only place that string appears.
- Never claim a fixed savings %; always "measured on my repos, repo-dependent, check it yourself."
- Don't surface the internal prod host. trovex is local-first; if a hosted demo is asked for, it needs a
  brand-neutral URL first.
- Don't get defensive or argue. Concede the real limit, thank the critic, move on.

*All copy above is a draft for the founder to use as replies. Nothing is posted.*
