# trovex — Product Hunt launch kit (DRAFT, do not launch)

**Status:** DRAFT / copy only. A human schedules and launches. Nothing submitted live.
**Owner:** launch-lead · **Reviewed against:** product-marketing-context.md, voice, no-synergix-mention, copy-gate, domain-research
**Repo:** github.com/Synergix-lab/trovex · **Landing:** trovex.dev

> What wins on PH for a dev/infra tool (from research): a simple demo, a before/after, and copy that
> carries one problem, one promise, one proof. What loses: complicated positioning, broad claims,
> features with no use case. So this kit keeps to one story: agents reread your docs and burn tokens;
> trovex serves the one current doc instead; here's the savings number.

---

## 1. Name + tagline

**Name:** `trovex`

**Tagline (≤60 chars — PH hard limit). Pick one:**
1. **`One canonical doc for your coding agents, ~60% fewer tokens`** (57)  *(recommended)*
2. `Stop your coding agents rereading your repo's docs` (49)
3. `The source-of-truth doc store for AI coding agents` (50)

#1 carries the promise + the proof in the limit. #2 leads with the pain if we'd rather hook on the problem.

---

## 2. Description (the short pitch under the tagline)

> One problem, one promise, one proof. No hype, no feature list.

```
Your coding agents reread a repo's .md files every session to figure out which doc is canonical,
burning tokens each time — and sometimes they still pick the stale one. trovex indexes your
markdown and serves the agent the single current doc that answers a query: a path:line pointer
with a freshness marker, so it reads one section instead of six files. Local-first, runs on your
machine, no API keys. ~60% fewer tokens per lookup, with a savings view so you can check the number
on your own repo.
```

---

## 3. Topics / categories (PH tags)

Pick 3 most-relevant (PH allows a few):
- Developer Tools
- Artificial Intelligence
- GitHub / Open Source
- (secondary if available) AI Infrastructure, Productivity

Reasoning: "Developer Tools" + "Artificial Intelligence" is where the coding-agent audience browses;
"Open Source" signals self-hostable and frames the no-lock-in story.

---

## 4. Gallery spec (the visuals — this is where PH is won or lost)

PH ranks the demo. Lead with the before/after, end with the savings receipt. Spec for design/eng to build:

**Slide 1 — the hook (first image, must read in 2 seconds):**
- Split before/after. Left: an agent reading 6 .md files (a stack, token counter ticking up).
  Right: trovex returning one `path:line` + a green "canonical" marker.
- One line of text on the image: "one current doc, not a repo reread."

**Slide 2 — the savings receipt (the proof):**
- Screenshot of the savings view: would-have-read vs. actual tokens on a real sample repo, ~60% less.
- This is the single most persuasive asset. Use a real run, not a mockup with invented numbers.

**Slide 3 — how it works (10-second read):**
- Three steps as a simple diagram: `index your repo` → `agent asks trovex(q)` → `gets one doc + freshness`.

**Slide 4 — the write path / SSOT (the depth):**
- Two agents (or a teammate) reading/writing through one trovex store, so nobody re-derives. Caption:
  "one source of truth across your agents and your team."

**Slide 5 — local + open (the trust close):**
- "runs on your machine · SQLite + on-device embeddings · no cloud, no API keys · AGPL core / MIT CLI."

**Optional Slide 0 — a short looping GIF/video (≤30s):** terminal `trovex index` → agent query → one-doc
result → the savings view. A real screen capture beats a polished motion graphic here.

> Asset honesty gate: every number on every slide must come from a real run. No fabricated metrics,
> no invented logos/testimonials, no "trusted by." Pre-launch means the savings number is the only proof.

---

## 5. Maker's first comment (post the moment it goes live)

```
Hi everyone. I build tools for teams running AI coding agents, and trovex is one I use daily.

The itch behind it: on a repo with a lot of docs, my agent spent a big slice of every session
rereading .md files just to decide which one was current, and it still sometimes grabbed a stale
note. So trovex indexes the markdown and gives the agent one answer: a path:line pointer with a
freshness marker (canonical / stale / duplicate), and the agent reads just that section. There's
also a write path so agents and teammates share one store instead of re-deriving the same things.

It's local: SQLite for vectors, on-device embeddings, no cloud or keys. The ~60% fewer tokens is
measured on my own repos for .md lookups, and the tool ships a savings view so you can check it on
yours rather than trust my number. On a small doc set it won't save much, and I'd rather say that.

It's open source (AGPL core, MIT CLI). I'd love feedback on the routing — where it picks the wrong
"canonical" doc, and what freshness signals you'd actually trust. Repo and quickstart:
github.com/Synergix-lab/trovex
```

> Brand check: no company name. "I build tools for teams running AI coding agents" is the only
> consulting context, and it stays a background fact, not a pitch.

---

## 6. Maker comment replies (have these ready for the day)

Reuse the Show HN answer bank (see show-hn.md §5) — the questions are the same on PH: vs. CLAUDE.md,
"isn't this RAG", privacy/local, AGPL, measurement, which clients. Keep PH replies a touch warmer and
shorter than HN, but just as honest. Concede limits; thank people for bugs and link the issue.

---

## 7. Hunter / launch-day note

- **Self-hunt is fine in 2026.** A bigger-name hunter is not required and a borrowed audience that
  doesn't care about dev infra doesn't convert. If a credible dev-tool hunter is genuinely enthusiastic,
  great; do not cold-spam hunters for a favor.
- **Pre-launch audience quality decides the day** more than launch mechanics. Before launching:
  line up the handful of people who already tried trovex (from the community plan / HN thread) and simply
  tell them the date so they can show up if they want. Do **not** ask for upvotes or planted comments —
  PH penalizes vote manipulation just like HN.
- **Timing:** launch 12:01am PT; pick a day with no giant competing launch if you can. Maker free all day
  to answer comments.
- **Launch day is the first checkpoint, not the finish line.** The win is people who click → install →
  see their own savings number. Track that, not the rank.

---

## 8. Pre-flight checklist (human runs before scheduling)

- [ ] Tagline chosen (≤60 chars verified). Recommend #1.
- [ ] Description fits PH's field; reads in one breath; one problem/promise/proof.
- [ ] Gallery slides built from REAL runs — savings receipt uses true numbers.
- [ ] Quickstart in the README works from a clean clone; the install line is one a PH visitor can follow.
- [ ] First comment ready to paste at 12:01am PT.
- [ ] No "Synergix" on any slide, in the description, or on the landing a visitor reaches. Repo URL only.
- [ ] Landing (trovex.dev) handles a PH traffic spike and has a clear "index your repo" next step.
- [ ] No upvote/comment solicitation. None.

## 9. Success definition (so we don't optimize the wrong thing)

- Primary: clicks that turn into installs + a visible savings number (activation), and GitHub issues from
  real users.
- Secondary: a consulting conversation or two from team leads who saw it.
- Rank/badge is a nice-to-have. A modest launch that sends 50 devs who actually install beats a top-5 day
  that bounces.

*All copy above is a draft. Nothing has been submitted to Product Hunt.*
