# Show HN — trovex (DRAFT, do not submit)

**Status:** DRAFT / copy only. A human submits this. Nothing is posted live.
**Owner:** launch-lead · **Reviewed against:** product-marketing-context.md, voice, no-synergix-mention, domain-research
**Repo:** github.com/Synergix-lab/trovex · **Landing:** trovex.dev

> HN rule reminders baked into this draft (from research): no superlatives, link the repo, the
> founder answers questions in their own voice, and **no booster comments from friends/employees**
> (vote rings get flagged and can kill the post). Our "seeding kit" below is pre-written *founder*
> answers to likely questions — not sockpuppets.

---

## 1. Title (pick ONE)

HN titles are short, plain, no hype, no superlatives. Candidates, ranked:

1. **`Show HN: Trovex – stop coding agents rereading your repo's docs every session`**  *(recommended)*
2. `Show HN: Trovex – serve coding agents one canonical doc instead of a repo reread`
3. `Show HN: Trovex – an MCP server that routes agent doc lookups, ~60% fewer tokens`
4. `Show HN: Trovex – local MCP server that gives agents the one current .md, not six`

Notes:
- #1 leads with the pain, not the product — strongest for a cold HN audience.
- HN allows a number if it's concrete and defensible; #3 uses ~60% but a skeptic will ask how it's
  measured — only use it if the first comment shows the measurement (it does, §3).
- Keep "Trovex" capitalized in the title per HN convention; lowercase `trovex` everywhere in prose.

---

## 2. Post type & link

- Submit as **Show HN** with the URL pointing to the **GitHub repo** (`github.com/Synergix-lab/trovex`),
  not the landing page. HN's dev audience trusts a repo (runnable, self-hostable) over a marketing site.
- Put the landing (trovex.dev) as a secondary link inside the first comment, not as the submission URL.

---

## 3. First comment (the founder posts this immediately after submitting)

> Follows the HN-admin structure: who you are → one sentence → problem → backstory → solution with
> technical detail → what's different → invite feedback. Written in a plain founder voice, no pitch.

```
Hi HN. I build tools for teams running AI coding agents, and trovex is one of them.

What it does, in one sentence: it indexes your repo's markdown and gives your coding agent the
single doc that answers a query (a path:line pointer with a freshness marker), instead of letting
it reread a pile of .md files every session to guess which one is current.

The problem I kept hitting: on a repo with a lot of docs (runbooks, ADRs, READMEs, half-stale
notes), the agent burns thousands of tokens each session re-reading files just to figure out which
one is canonical. Across many sessions and a couple of teammates' agents, you pay for the same
lookup over and over, and it still sometimes grabs the stale doc.

How it works:
- One MCP tool, trovex(q), routes a query to the right on-disk .md and returns minimal pointers
  (path:line + a freshness marker: canonical / stale / duplicate). The agent then reads only the
  relevant section, not the whole file.
- There's also a write path (trovex_write / trovex_read): agents can store a decision/record
  inside trovex and read it back later, so a second agent (or a teammate) doesn't re-derive it.
  One shared store = one source of truth.
- It's local: vectors in SQLite (sqlite-vec), local ONNX embeddings via fastembed, no cloud and no
  API keys. FastAPI serves the MCP endpoint and a small web UI to read the docs at /doc/{id}.

On the ~60% number: it's tokens spent on .md reads for a lookup. Serving one section plus pointers,
versus the agent reading the top candidate files to decide which is canonical. It's a measured
reduction on my repos, not a benchmark I'm asking you to take on faith; the tool ships a savings view
so you can see would-have-read vs. actual on your own corpus. Your mileage depends on how doc-heavy
your repo is. On a tiny doc set it won't save much, and I'd rather say that than oversell it.

How it compares to what people already use:
- CLAUDE.md / AGENTS.md / .cursorrules: one static blob — great until it goes stale and can't route a
  query to the right doc/section.
- repomix / dumping files: floods the context window with everything, which is the opposite of what I
  wanted.
- plain RAG/context servers: hand back a pile of candidate chunks to rank; trovex returns the one
  canonical doc with a freshness marker and closes the write loop.

It's open source (AGPL-3.0 core, MIT CLI). Install + index is a couple of commands (in the README).
I'd genuinely like feedback on the routing — where it picks the wrong "canonical" doc, and what
freshness signals you'd trust. Repo: https://github.com/Synergix-lab/trovex · more at https://trovex.dev
```

> Brand check: this comment never names a company. "I build tools for teams running AI coding agents"
> carries the consulting context without a sales pitch and without naming anything.

---

## 4. Comment-seeding plan (the honest kind)

**The only "seeding" we do is the founder being present and substantive.** No booster comments, no
asking friends to upvote or plant praise — HN detects vote rings and will flag/kill the post, and it's
against the rules. Research point (Fly.io launch): the founder personally answered ~53 comments; that
engagement *is* the seeding.

**Founder game plan for launch day:**
- Be at a keyboard for the first 2–3 hours and reply to every substantive comment within minutes.
- Answer the technical critic first and most generously — HN rewards a founder who engages the
  hardest question head-on.
- Concede real limitations plainly (small doc sets, the ~60% being repo-dependent). Honesty out-performs
  defensiveness here.
- Never argue, never get hype-y, never paste the same canned line twice. Each reply in your own voice.
- If someone finds a bug, thank them, file an issue, link it. That thread becomes social proof on its own.

---

## 5. Likely-question answer bank (pre-written, founder posts as replies when asked)

**Q: How is this different from just putting everything in CLAUDE.md / AGENTS.md?**
> Those are one static file. They work until the corpus grows and they go stale — there's no per-query
> routing and no signal for "this doc is current vs. that one is outdated." trovex keeps many docs and
> serves the one that answers the question, with a freshness marker, so the agent isn't reading a
> three-week-old note as gospel.

**Q: Isn't this just RAG with extra steps?**
> Mechanically it uses embeddings + vector search, yes. The difference is the output: a RAG/context
> server usually returns N candidate chunks for the model to sift. trovex returns the single canonical
> doc (path:line + freshness) and lets the agent read just the section it needs — plus a write path so
> agents share one store instead of re-deriving. It's opinionated about giving one answer, not a pile.

**Q: Why not just use a bigger context window / let the agent read files?**
> Two reasons. Cost compounds — every session × every agent × every teammate pays for the same reread.
> And a big context window isn't the same as the *current* context; the agent can still pick the stale
> file. trovex is about the right doc cheaply, not more doc.

**Q: How do you measure the ~60%?**
> Tokens spent on .md reads for a lookup: serving one section + pointers vs. the agent reading the top
> candidate files to decide which is canonical. The tool shows would-have-read vs. actual on your own
> repo, so you can check it instead of trusting my number. On a small doc set it'll be much less — it's
> repo-dependent and I try not to oversell it.

**Q: What embeddings / does it phone home? Privacy?**
> Local only. Embeddings run on-device via fastembed (ONNX under the hood), vectors live in a local
> SQLite db (sqlite-vec). No cloud, no API keys, nothing leaves your machine. You can read the code.

**Q: Which agents/clients does it work with?**
> Anything that speaks MCP — it exposes a standard MCP server (Claude Code, Cursor, etc.). Config snippet
> is in the README. *(Confirm the exact stdio invocation against the CLI before this goes live.)*

**Q: AGPL? That kills it for my company.**
> The core is AGPL-3.0, the CLI is MIT. Self-host and modify freely; AGPL only bites if you run a
> *modified* version as a network service and don't share changes. If a team needs to embed/host it
> privately without that obligation, reach out and we'll sort it — happy to talk.
> *(This is the low-key consulting/commercial door. Keep it this casual; do not pitch.)*

**Q: How does the write path avoid two agents clobbering each other / how is "canonical" decided?**
> *(Founder/eng to answer with the real mechanism — single point of passage, how duplicates/staleness
> are flagged. Fill in accurate technical detail before launch; don't hand-wave on HN.)*

**Q: Is this hosted? Can I try it without installing?**
> It's local-first by design — you run it on your machine, no signup. Index a repo and serve in a couple
> of commands (README). *(Do NOT mention the internal prod host — brand rule. If a hosted demo is wanted
> later, it needs a brand-neutral URL first.)*

**Q: Roadmap / is this maintained or a weekend project?**
> *(Founder: one honest sentence on commitment + what's next — e.g. better freshness signals, more client
> configs. Don't overpromise.)*

---

## 6. Pre-flight checklist (human runs before submitting)

- [ ] README has a copy-paste install + index that actually works from a clean clone.
- [ ] The MCP client config in the README is verified to run (exact stdio flag confirmed).
- [ ] The savings view works and shows a real would-have-read vs. actual number on a sample repo.
- [ ] Repo has a clear license note (AGPL core / MIT CLI) and a CONTRIBUTING / issues enabled.
- [ ] No "Synergix" surfaced anywhere in repo prose that a visitor lands on (README, site). Technical
      org identifier in the URL is fine.
- [ ] Founder is free for 2–3 hours after submit to answer comments.
- [ ] Pick the title (recommend #1). Have the first comment (§3) ready to paste the second the post lands.
- [ ] Decide timing: research suggests a US weekday morning (Tue/Wed) ET — treat as a hypothesis, not a
      guarantee. Submit, then immediately post the first comment.
- [ ] Do NOT ask anyone to upvote or post supportive comments. None.

## 7. What success looks like (so we don't chase vanity)

- Primary: qualified devs install + index + see their own savings number (activation), and a few file
  issues / star because it solved a real annoyance.
- Secondary: one or two "a team lead reached out" conversations from the AGPL/consulting door — that's
  the north star, not front-page rank.
- Front page is nice but not the goal; a smaller thread of high-intent MCP users who actually install is
  worth more than a hype spike that bounces.

*All copy above is a draft. Nothing has been submitted to Hacker News.*
