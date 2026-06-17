# Show HN kit (DRAFT, do not submit)

**Status:** DRAFT / copy only. A human (owner) submits. Nothing posted live.
**Owner:** launch-lead · **Reviewed against:** launch-teardown-playbook.md (#162), suite-positioning.md, launch-day-runbook.md, product-marketing-context.md, voice, no-synergix-mention, autonomy-rules
**Repos:** wrai.th → github.com/Synergix-lab/WRAI.TH (public, v1.0) · trovex → github.com/Synergix-lab/trovex (private beta)

> **Refreshed against the launch teardown (#162).** The five rules that won every studied launch are baked in:
> (1) one reproducible number, not an adjective · (2) link the **repo**, not a landing page · (3) founder in the
> thread, fast + deep · (4) state a real limitation up front · (5) **nothing ships on launch day** (last code lands
> ≥1 week prior). No superlatives, no vote-begging, no booster comments (HN flags vote rings).

---

## 0. Which tool leads the Show HN — and why

**wrai.th leads. Not trovex (yet), and never the agency.**

- **wrai.th is the launchable one:** public, v1.0 stable, real cold install — exactly what HN runs (`git clone` / one binary, no signup). It's also the widest top-of-funnel of the suite (suite-positioning).
- **trovex is private beta** — it fails teardown rule #5 (a stranger can't cold-install it cleanly yet). Launching it on HN now would put a broken/locked install in the top comment. Its Show HN kit is kept ready in **§B** for when the repo + PyPI go public (unfreeze-checklist TROVEX TRACK).
- **The agency is never the Show HN.** tsukumo appears only as the low-key "who builds this" footnote in the repo (oss-agency-bridge.md), never as the HN pitch. HN punishes a consulting pitch dressed as a Show HN.

So: **§A = wrai.th Show HN (fire first).** §B = trovex Show HN (when public). Don't stack them; space the launches (launch-day-runbook).

---

# §A — wrai.th Show HN (the lead one-shot)

## A1. Title (pick ONE — plain, names the tech, no superlatives)

1. **`Show HN: wrai.th – run a fleet of AI coding agents from one control plane`**  *(recommended — concrete, names the job)*
2. `Show HN: wrai.th – orchestration for AI coding agents: shared memory, messaging, tasks`
3. `Show HN: wrai.th – one binary to coordinate multiple coding agents (MCP, local)`
4. `Show HN: wrai.th – mission control for AI agents (persistent memory + a shared task board)`

Notes:
- #1 leads with the *job* (run a fleet), strongest for a cold HN audience; #2/#4 spell out the mechanism for the skeptic.
- Capitalize at sentence start per HN convention; lowercase `wrai.th` in prose.
- No number in the title — wrai.th's pitch is capability, not a single benchmark (unlike trovex's ~60%). Don't fake one.

## A2. Post type & link

- **Show HN**, URL → the **repo** (`github.com/Synergix-lab/WRAI.TH`), not a landing page. A runnable, self-hostable repo is the HN trust signal.
- Any site link goes in the first comment as secondary.

## A3. First comment (founder posts immediately — the 7 beats from #162)

> who you are → one sentence → the problem → backstory → how it works (technical) → what's different → ask for feedback (+ one honest limitation). Plain founder voice, no pitch.

```
Hi HN. I build tools for teams running AI coding agents; wrai.th is the one that coordinates them.

One sentence: wrai.th is a local control plane for a fleet of coding agents — persistent memory,
inter-agent messaging, a shared task board, and one dashboard — so multiple agents (and your
teammates') work together instead of each in its own silo.

The problem I kept hitting: one coding agent is easy; running several is where it falls apart. They
don't share memory, they re-derive what another already figured out, they step on each other, and you
have no single view of who's doing what or what they did overnight. I wanted mission control, not a
pile of terminals.

How it works:
- Agents register and talk over MCP: messaging, a shared task board (claim/start/complete), and a
  persistent memory store they all read/write, so context survives across agents and sessions.
- [Founder/eng: the real coordination mechanism — how tasks are claimed without clobbering, how memory
  scope works. Fill with accurate detail; don't hand-wave on HN.]
- It's local and [one binary / zero-config — confirm exact run story]; AGPL, self-hostable, no cloud
  lock-in.

What's different from [orchestration frameworks people know]: [Founder: the honest one-liner — wrai.th
is the run-it control plane (memory + messaging + tasks + dashboard), not a code framework you wire by
hand. Keep it fair, name the real alternative.]

One honest limitation: [Founder: state it plainly — e.g. early on multi-machine, or which clients are
verified. A real weakness up front buys more trust here than any feature.]

It's open source (AGPL). Install + run is in the README. I'd genuinely like feedback on the coordination
model — where it breaks with more agents, and what you'd want from the memory layer.
Repo: https://github.com/Synergix-lab/WRAI.TH
```

> Brand check: never names a company. "I build tools for teams running AI coding agents" carries the
> consulting context without a pitch. The suite (trovex/yoru) can be mentioned in a *reply* if asked,
> not in the opening comment.

## A4. Founder engagement (the only "seeding" — no booster comments)

- Be at a keyboard the first **2–3h**; reply to every substantive comment within minutes (Fly.io founder answered ~53 — that *is* the seeding).
- Answer the hardest technical critic first and most generously; agree-then-respond.
- Concede real limits plainly. Never argue, never hype, never paste the same line twice.
- Bug found → thank, file an issue, link it. That thread becomes the social proof.
- **No vote-begging, no friends planting praise** — HN detects vote rings and kills the post.

## A5. Likely-question answer bank (founder posts as replies when asked)

**Q: How is this different from LangGraph / CrewAI / an agent framework?**
> [Founder: honest answer — those are frameworks you write your orchestration in; wrai.th is a running
> control plane (memory + messaging + shared tasks + dashboard) you point existing MCP agents at. Name
> the real tool, be fair, don't trash it.]

**Q: Does it work with Claude Code / Cursor / my agent?**
> Anything that speaks MCP. Config is in the README. *(Confirm exact client config before launch.)*

**Q: Local or cloud? Privacy?**
> Local-first, self-hostable, no cloud lock-in. [Confirm what (if anything) leaves the machine.] You can read the code.

**Q: How does it stop two agents clobbering the same task / shared state?**
> *(Founder/eng: the real mechanism — task claim, memory scope/locks. Accurate detail; don't hand-wave.)*

**Q: AGPL — that kills it for my company.**
> Core is AGPL; self-host + modify freely; AGPL only bites if you run a *modified* version as a network
> service and don't share changes. A team that needs to embed/host it privately without that, reach out —
> happy to talk. *(Low-key commercial/consulting door. Keep it casual; do not pitch.)*

**Q: Is this maintained or a weekend project? Roadmap?**
> *(Founder: one honest sentence on commitment + what's next. Don't overpromise.)*

**Q: Does it pair with anything for context/observability?**
> Yes — trovex (one canonical doc per query, fewer tokens) and yoru (see what the fleet did). Use wrai.th
> alone or add those layers. *(Only if asked — the suite is a reply, not the pitch.)*

## A6. Pre-flight checklist (owner runs before submitting)

- [ ] README has a copy-paste install + run that **works from a clean clone** (teardown #5).
- [ ] The exact client/MCP config in the README is verified to run.
- [ ] **Nothing ships on launch day** — last code landed ≥1 week prior; the build is stable.
- [ ] Fill the [bracketed] technical answers in A3/A5 with real detail — HN will probe them.
- [ ] GitHub topics/tags set (PostHog lesson → Trending eligibility); CONTRIBUTING + issues on.
- [ ] No "Synergix" in any prose a visitor lands on (README/site); URL org identifier is fine.
- [ ] Owner free **2–3h** after submit; first comment (A3) ready to paste the second it lands.
- [ ] Timing: US weekday AM ET (Tue–Thu ~9–11am) — a minor lever, not the strategy. Submit, then post A3.
- [ ] **Do NOT** ask anyone to upvote or post supportive comments.

---

# §B — trovex Show HN (HOLD until trovex is public)

> Fire only after the trovex repo + PyPI are public and a stranger can `uvx trovex index/serve` cleanly
> (unfreeze-checklist TROVEX TRACK). Space it from the wrai.th day. Until then this is held.

## B1. Title (pick ONE)
1. **`Show HN: trovex – stop coding agents rereading your repo's docs every session`** *(recommended)*
2. `Show HN: trovex – serve coding agents one canonical doc instead of a repo reread`
3. `Show HN: trovex – an MCP server that routes agent doc lookups, ~60% fewer tokens`
4. `Show HN: trovex – local MCP server that gives agents the one current .md, not six`

- #1 leads with the pain. #3 uses ~60% — only if the first comment shows the measurement (it does, B3). Capitalize at sentence start; lowercase `trovex` in prose.

## B2. Post type & link
- Show HN → the **repo** (`github.com/Synergix-lab/trovex`); landing (trovex.dev) secondary, in the first comment.

## B3. First comment (founder posts immediately — 7 beats)
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
so you can see would-have-read vs. actual on your own corpus. On a tiny doc set it won't save much,
and I'd rather say that than oversell it.

How it compares to what people already use:
- CLAUDE.md / AGENTS.md / .cursorrules: one static blob — great until it goes stale and can't route a
  query to the right doc/section.
- repomix / dumping files: floods the context window with everything, the opposite of what I wanted.
- plain RAG/context servers: hand back a pile of candidate chunks to rank; trovex returns the one
  canonical doc with a freshness marker and closes the write loop.

It's open source (AGPL-3.0 core, MIT CLI). Install + index is a couple of commands (in the README).
I'd genuinely like feedback on the routing — where it picks the wrong "canonical" doc, and what
freshness signals you'd trust. Repo: https://github.com/Synergix-lab/trovex · more at https://trovex.dev
```

## B4. trovex Q&A bank
*(Unchanged from the prior kit — still valid. Key answers:)*

**Q: Different from CLAUDE.md / AGENTS.md?** One static file that goes stale + can't route per query; trovex keeps many docs and serves the current one with a freshness marker.
**Q: Just RAG with extra steps?** Uses embeddings, but returns the one canonical doc (path:line + freshness) + a write path, not a candidate pile.
**Q: Why not a bigger context window?** Cost compounds (session × agent × teammate); big context ≠ *current* context. Right doc cheaply, not more doc.
**Q: How is ~60% measured?** Tokens on .md reads: one section + pointers vs reading top candidates; the savings view shows would-have-read vs actual on your repo. Repo-dependent.
**Q: Embeddings / phone home?** Local only — fastembed/ONNX on-device, sqlite-vec, no cloud/keys.
**Q: Which clients?** Anything MCP (Claude Code, Cursor…); config in README. *(Confirm stdio invocation before launch.)*
**Q: AGPL kills it for my company?** Core AGPL / CLI MIT; only bites on modified network service. Want to embed privately? reach out — happy to talk. *(Low-key door; don't pitch.)*
**Q: Write path / how is "canonical" decided?** *(Founder/eng: real mechanism — single point of passage, duplicate/stale flagging. Accurate detail before launch.)*
**Q: Hosted / try without installing?** Local-first by design, no signup. *(Do NOT mention any internal prod host — brand rule.)*

## B5. trovex pre-flight
- [ ] Repo public + PyPI live; `uvx trovex index/serve` works from a clean machine.
- [ ] Client config verified; savings view shows a real number on a sample repo.
- [ ] Beta proof folded in if available (real numbers + permissioned quote).
- [ ] Same founder-presence + no-vote-begging rules as A4/A6.

---

## §C — Who posts (both tracks)

- **The owner posts** from a real, aged HN account (autonomy-rules: platform posts need owner creds; launch-lead drafts, never submits).
- One human voice in the thread — the founder. No team members posting as independent "users."
- launch-lead's job ends at "ready-to-paste": title chosen, first comment + Q&A filled with real technical detail, pre-flight green. The owner fires.

## §D — What success looks like (not vanity)

- **Primary:** qualified devs install + run it (activation) — wrai.th fleet running / trovex savings number seen — and a few file issues or star because it solved a real annoyance.
- **Secondary:** one or two "a team lead reached out" conversations from the AGPL/consulting door — the north star, not front-page rank.
- A smaller thread of high-intent users who actually install beats a hype spike that bounces.

*All copy above is a draft. Nothing has been submitted to Hacker News.*
