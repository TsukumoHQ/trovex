# Product Hunt launch kit (DRAFT, do not launch)

**Status:** DRAFT / copy only. A human (owner) schedules + launches. Nothing submitted live.
**Owner:** launch-lead · **Reviewed against:** launch-teardown-playbook.md (#162), suite-positioning.md, launch-day-runbook.md, show-hn.md, product-marketing-context.md, voice, no-synergix-mention, autonomy-rules
**Repos:** wrai.th → github.com/Synergix-lab/WRAI.TH (public, v1.0) · trovex → github.com/Synergix-lab/trovex (private beta)

> **Refreshed against the teardown (#162).** PH-specific rules baked in: ranking is **quality-weighted, not raw votes** (PH clears votes from new/low-engagement/same-IP accounts ~every 2h) → keep inflow diverse + under ~100/hr, **never** ask for upvotes; pre-seed 100–300 genuinely-engaged people 3+ weeks out asking for *feedback*; maker first comment = the **personal-problem story ending in a use-case question** (use-case-tagged comments get higher algorithmic weight); **AI-generated comments are detected + discounted**; visuals (real-run gallery) matter more than on HN. One-shot — fire per `launch-day-runbook` §3, not ad-hoc.

---

## 0. Which tool leads — and when

- **wrai.th can launch now** (public v1.0, cold-installable) — §A. It's the widest TOF (suite-positioning).
- **trovex is private beta** — its PH kit (§B) is HOLD until repo + PyPI public + real beta proof for the gallery; launching a locked install fails the teardown "nothing ships broken" rule.
- **Agency is never the PH pitch.** tsukumo stays the low-key footnote only.
- **Don't stack with the Show HN day** — space the one-shots (launch-day-runbook).

---

# §A — wrai.th Product Hunt kit (launchable now)

## A1. Name + tagline (≤60 chars, PH hard limit)
1. **`Run a fleet of AI coding agents from one control plane`** (54) *(recommended)*
2. `Orchestration for AI coding agents: memory, messaging, tasks` (59)
3. `Mission control for your AI coding agents — local, open source` (60)

#1 leads with the job. No fake number — wrai.th's pitch is capability, not a benchmark.

## A2. Description (one problem / one promise / one proof)
```
One coding agent is easy; running several is where it breaks — they don't share memory, they
re-derive each other's work, and you have no view of who did what. wrai.th is a local control plane
for an agent fleet: persistent memory, inter-agent messaging, a shared task board, one dashboard.
Point your MCP agents at it. Open source, self-hostable, no cloud lock-in.
```

## A3. Topics (pick 3)
- Developer Tools · Artificial Intelligence · Open Source  *(secondary: Productivity)*

## A4. Gallery spec (real runs only — PH is won here)
- **Slide 1 (hook, reads in 2s):** the dashboard — several agents, their tasks, live. One line: "mission control for your agent fleet."
- **Slide 2 (the depth):** inter-agent messaging + shared task board (claim → start → complete) across agents.
- **Slide 3 (memory):** the persistent memory store agents read/write — context surviving across agents/sessions.
- **Slide 4 (how it works, 10s):** `register agents → they coordinate over MCP → one dashboard`.
- **Slide 5 (trust close):** "local · self-hostable · MCP-native · AGPL · no cloud lock-in."
- **Optional Slide 0 (≤30s screen capture):** spin up 2–3 agents → watch them claim tasks + share memory live.
> Honesty gate: real screens only. No fabricated metrics/logos/"trusted by." [design/eng build from real runs.]

> **Built assets (design, #209) → `growth/assets/launch/wraith/`** (wrai.th brand: dark `#0a0c10` + emerald
> `#4ade80`, NOT tsukumo acid; verbatim copy from the gallery spec). DONE: slide-4 (how-it-works), slide-5
> (trust), `og-card.png` (1200×630 — also the show-hn link unfurl), `thumbnail-240.png`. PENDING: slides 1–3
> are **real /v2/ dashboard captures** — a human grabs them per `CAPTURE-BRIEF.md` (live colony, honesty gate),
> drops `raw-slide-1..3.png`, design composites into 1270×760 frames. Tracked as a human task. Gallery is
> complete once those 3 land — then the one-shots need only owner go.

## A5. Maker first comment (post at launch — personal story + use-case question)
```
Hi PH. I build tools for teams running AI coding agents; wrai.th is the one that coordinates them.

It started because one agent was fine but three was chaos — no shared memory, stepping on each
other, no view of what they did overnight. wrai.th is the control plane I wanted: agents register and
talk over MCP, claim tasks off a shared board, and read/write one persistent memory, with a dashboard
over the whole fleet. Local, self-hostable, open source.

[One honest limitation — founder fills: e.g. current multi-machine state / which clients are verified.]

What's the first thing you'd point a fleet of agents at? Repo + quickstart: github.com/Synergix-lab/WRAI.TH
```
> Ends on a use-case question (algorithmic weight). Never names a company. Suite (trovex/yoru) only in a reply if asked.

## A6. Launch-day mechanics
- **12:01am PT**, a day with no giant competing launch; maker free all day.
- **Pre-seed 3+ weeks out:** tell the handful who already use wrai.th the date — ask for *feedback*, never upvotes.
- Keep vote inflow diverse + organic (PH clears clustered/same-IP/new-account votes; vote-begging can go net-negative).
- Self-hunt is fine; a borrowed-audience hunter who doesn't care about dev infra doesn't convert.
- Answer every comment in your own voice (no AI-generated comments — PH discounts them).

## A7. Q&A — reuse show-hn.md §A5 (wrai.th bank), warmer + shorter for PH.

---

# §B — trovex Product Hunt kit (HOLD until trovex is public)

> Fire only after repo + PyPI public + a real savings-receipt gallery (unfreeze-checklist TROVEX TRACK). Space from wrai.th's day.

## B1. Tagline (≤60)
1. **`One canonical doc for your coding agents, ~60% fewer tokens`** (57) *(recommended)*
2. `Stop your coding agents rereading your repo's docs` (49)
3. `The source-of-truth doc store for AI coding agents` (50)

## B2. Description (one problem / promise / proof)
```
Your coding agents reread a repo's .md files every session to figure out which doc is canonical,
burning tokens — and sometimes still pick the stale one. trovex indexes your markdown and serves the
single current doc that answers a query: a path:line pointer with a freshness marker, so it reads one
section instead of six files. Local-first, runs on your machine, no API keys. ~60% fewer tokens per
lookup, with a savings view so you can check the number on your own repo.
```

## B3. Topics: Developer Tools · Artificial Intelligence · Open Source (secondary: AI Infra, Productivity)

## B4. Gallery spec (real runs — the savings receipt is the most persuasive asset)
- **Slide 1 (hook):** split before/after — agent reading 6 .md (token counter ticking) vs trovex returning one `path:line` + green "canonical". Text: "one current doc, not a repo reread."
- **Slide 2 (proof):** the savings view — would-have-read vs actual, ~60% less, **real run**.
- **Slide 3 (how, 10s):** `index your repo → agent asks trovex(q) → one doc + freshness`.
- **Slide 4 (depth):** write path / SSOT — two agents through one store. "one source of truth across your agents and team."
- **Slide 5 (trust):** "runs on your machine · SQLite + on-device embeddings · no cloud/keys · AGPL core / MIT CLI."
- **Optional Slide 0 (≤30s):** `trovex index` → query → one-doc result → savings view.
> Honesty gate: every number from a real run. No invented metrics/logos/testimonials. Pre-launch = the savings number is the only proof.

## B5. Maker first comment (personal story + use-case question)
```
Hi PH. I build tools for teams running AI coding agents, and trovex is one I use daily.

The itch: on a doc-heavy repo my agent spent a big slice of every session rereading .md just to
decide which was current — and still sometimes grabbed a stale note. trovex gives it one answer: a
path:line pointer + a freshness marker (canonical / stale / duplicate), and it reads just that
section. There's a write path so agents and teammates share one store instead of re-deriving.

Local: SQLite, on-device embeddings, no cloud or keys. The ~60% fewer tokens is measured on my repos
for .md lookups; the tool ships a savings view so you can check it on yours. Small doc set → it won't
save much, and I'd rather say that.

What repo would you point it at first? Open source (AGPL core, MIT CLI): github.com/Synergix-lab/trovex
```

## B6. Q&A — reuse show-hn.md §B4 (trovex bank), warmer + shorter.

---

## §C — Who fires + pre-flight (both tracks)

- **Owner launches** from a real PH account (autonomy-rules: platform posts need owner creds; launch-lead drafts, never submits).
- [ ] Tagline chosen (≤60 verified). Description reads in one breath (one problem/promise/proof).
- [ ] Gallery built from **real runs**; any number is true.
- [ ] Quickstart works from a clean clone; the install line is one a PH visitor can follow (teardown #5).
- [ ] First comment ready to paste at 12:01am PT; ends in a use-case question.
- [ ] Pre-seeded feedback list ready; **no upvote/comment solicitation, no AI-generated comments.**
- [ ] No "Synergix" on any slide/description/landing a visitor reaches (repo URL only).
- [ ] Landing handles the traffic spike + has a clear next step; maker free all day.

## §D — Success (not vanity)
- Primary: clicks → installs → wrai.th fleet running / trovex savings number seen (activation) + real GitHub issues.
- Secondary: a consulting conversation or two from team leads (north star).
- Rank/badge is nice-to-have. A modest launch sending 50 devs who actually install beats a top-5 day that bounces.

*All copy above is a draft. Nothing has been submitted to Product Hunt.*
