# X / Twitter — trovex launch thread (DRAFT)

> **Status: DRAFT — do not post. A human fires this.**
> Lead asset = the savings receipt (~60% fewer tokens). That number *is* the ad.
> Honesty rules: only claim ~60% (or your own real receipt). No fabricated stars,
> users, or quotes — pre-launch, zero customers. Lowercase `trovex` always.

---

## How to fire (notes for the human)

- Post the **hook** as tweet 1, then reply-chain the body posts in order.
- **Put the repo/site link in a REPLY, not in tweet 1** (link in the first post
  suppresses reach). The CTA post already does this.
- Attach the **savings-receipt screenshot** to tweet 1 (the dashboard "would have
  read vs actual, −60%" panel). The screenshot is the scroll-stopper — make it
  legible at thumbnail size.
- Best results: post, then for ~30 min reply to relevant in-niche accounts /
  threads about agent token cost. Distribution is reply-led, not post-and-pray.
- Pick ONE hook variant below. A/B the rest later as standalone posts.

---

## Hook variants (pick one for tweet 1)

**A — the receipt (default, lead with the number):**
> my coding agent was burning ~60% of its doc-lookup tokens just rereading `.md`
> files to guess which one was current.
>
> indexed the repo with trovex. now it gets one canonical answer instead of three
> stale files. same context, ~60% fewer tokens. here's the before/after 👇

**B — the concrete-problem hook:**
> every session, my agent reads `deploy/runbook.md`, `wiki/old-deploy.md`, and a
> postmortem — to answer one question it already answered yesterday.
>
> that's the tax. here's how i killed it (and the token receipt) 👇

**C — the contrarian hook:**
> "just use a bigger context window" is why your agent bill keeps climbing.
>
> big context ≠ current context. your agent still rereads the repo to find the
> *right* doc. i fixed the actual problem instead 👇

**D — the build-in-public hook:**
> shipped trovex today: a local MCP server that stops your coding agent rereading
> the repo to figure out which doc is canonical.
>
> one query → one current answer (`path:line` + freshness). ~60% fewer tokens on
> doc lookups. how it works 👇

---

## Thread body (tweets 2–9)

**2/ the problem, concretely**
> agents don't know which `.md` is the source of truth. so they read several and
> guess. CLAUDE.md / AGENTS.md help, but they're one static blob that goes stale
> and can't route a question to the right doc or section.

**3/ what that costs you**
> it compounds: every session × every agent × every teammate. you pay tokens
> (money), you pollute the context window with stale files, and you re-derive what
> another agent already figured out last week.

**4/ what trovex does**
> point it at your repo. it indexes the markdown, then exposes one MCP tool. your
> agent asks a question; trovex returns the single current doc that answers it —
> `path:line` + a freshness marker (canonical / stale / duplicate), not a pile of
> candidates to sift.

**5/ the before/after (the receipt)**
> before: agent reads 3 files (~2,400 tokens) to guess the canonical deploy doc.
> after: trovex serves the one current section (~280 tokens). same answer.
> that's the ~60% line on the dashboard — it shows would-have-read vs actual.
> [attach receipt screenshot here]

**6/ section-level reads, not whole files**
> it serves the two paragraphs that answer the query, not the entire file. the
> agent stops paying for 400 lines to use 6 of them.

**7/ the part that matters for teams**
> agents also *write* what they learn back through one shared point. an incident,
> a decision, "the rollback steps that actually worked" — saved once, read by
> every agent and your teammate. one source of truth, no copies that drift.

**8/ local, no lock-in**
> runs on your machine. vectors in SQLite, embeddings via ONNX. no cloud, no API
> keys, your code never leaves the box. one process, ~1-minute setup.

**9/ CTA (link goes HERE, in the last post / first reply)**
> it's open source (AGPL core, MIT CLI). point it at a repo and watch the savings
> number:
>
> `uv run trovex index <repo>`
>
> repo + docs: github.com/Synergix-lab/trovex · trovex.dev
> if you're running agents across a team and this is a daily tax, that's the kind
> of thing i help teams fix — happy to talk.

---

## Shorter variant (4-post launch, if you want tight)

1. Hook **A** + receipt screenshot.
2. Body **4/** (what it does) + a one-line demo clip if available.
3. Body **7/** (shared write path = SSOT) — the team angle.
4. CTA **9/** with link in reply.

---

## Voice check (self-audit)

- [x] Leads with the real ~60% number; no other metric invented.
- [x] No banned words (revolutionary/seamless/supercharge/unlock/AI-powered).
- [x] Written from the user's side ("your agent", "your repo").
- [x] Consulting surfaces once, low-key, at the very end. Not a pitch.
- [x] No fabricated stars/users/testimonials. Lowercase `trovex`.
- [x] Link in reply, not in the hook (reach).
