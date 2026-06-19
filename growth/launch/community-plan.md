# trovex — 30-day community-seeding plan (DRAFT, nothing posted live)

**Status:** DRAFT / copy only. A human posts every item, after reading each venue's current rules.
**Owner:** launch-lead · **Reviewed against:** product-marketing-context.md, voice, no-synergix-mention, copy-gate, domain-research
**Repo:** github.com/Synergix-lab/trovex · **Landing:** trovex.dev

---

## Fire-readiness + execution layer (2026-06-19 — distribution phase)

**Go-state:** the funnel this seeds INTO is live — tsukumo.ch + /assessment operational, trovex
`/api/waitlist` returns 200 (cmo-tested), trovex repo public. So this plan is **fireable**; the only
per-item gate left is reading each venue's current rules at fire time (research gaps below). A human posts
every item — launch-lead stages + sequences, never posts.

**Suite sequencing (which tool seeds first):**
- **wrai.th leads.** It's public + v1.0 stable and the widest top-of-funnel — use the wrai.th seed drafts in
  `wraith-kit.md §3` (r/mcp, r/LocalLLaMA Go-binary angle, MCP/Cline/Continue/Cursor #showcase, r/golang,
  its own Discord). Pairs with the wrai.th-registries bucket firing in parallel (`wraith-registry-checklists.md`).
- **trovex follows** on the same value-first cadence (this plan). Don't seed the same person/venue BOTH tools
  the same week — that reads as a campaign, not a contributor.
- The suite cross-reference (trovex pairs with wrai.th) goes in a *reply when asked*, never the opening post.

**Per-post fire checklist (human runs, every single post):**
- [ ] Read the venue's rules + pinned posts RIGHT NOW (they change). If self-promo isn't allowed, don't.
- [ ] It's an answer to a real existing thread OR the sanctioned intro (r/mcp flair) — not a drive-by drop.
- [ ] Personalize the draft; never paste verbatim, never the same link across venues same-day.
- [ ] Post from a real, aged account (no alts). Honesty gate: only what you actually measured.
- [ ] Log it (venue / date / link) so the 9:1 contribute-to-promote ratio stays real.

**Research gaps to close before firing (the only blockers — a human verifies):**
- [ ] Exact self-promo rules for r/LocalLLaMA + r/ChatGPTCoding (sidebars/wiki, promo-day norms).
- [ ] Which MCP / Cline / Continue / Cursor Discords have a #showcase channel (share only there).
- [ ] Current newsletter submission forms (PulseMCP, TLDR, Console.dev, Cooperpress).

---

## The one rule that governs everything

Reddit (and most dev communities) define spam by **behavior, not intent**: a user whose history is
mostly links to something they benefit from is a spammer, full stop. So the whole plan is built around a
ratio, not a blast.

**Contribute >> promote.** Roughly 9 helpful, non-self-promoting actions for every 1 that mentions
trovex. Show up as a person who knows the problem, not an account that drops a link and leaves.

Corollaries:
- Read each venue's rules and pinned posts before posting anything. Rules differ and change.
- No copy-paste across venues. Same link in five subreddits on the same day is the fastest way to get
  banned and to look like exactly what we don't want to be.
- Lead with the problem and a useful answer. The tool is a footnote, often not mentioned at all.
- Never fake it: no alt accounts, no "has anyone tried trovex?" sockpuppets, no invented experience.

---

## Where to show up (venue map)

Intent runs high → low. Spend the most effort where the people already run coding agents.

| Venue | Who's there | Self-promo tolerance | Our angle |
|---|---|---|---|
| r/mcp | MCP builders + users | Moderate, author flair exists | highest fit — get mcp-server-authors flair, be useful |
| MCP Discords (official MCP, client Discords: Cline, Continue, Cursor) | hands-on MCP devs | Channel-specific (often a #showcase) | answer config/routing questions; share in the right channel only |
| r/ChatGPTCoding | devs using AI to code | Moderate, Saturday-promo norms vary | token-cost + stale-doc pain is on-topic |
| r/LocalLLaMA | local-LLM crowd, privacy-minded | Low for promo, high for substance | local-first / on-device embeddings angle; **read sidebar — strict** |
| Lobsters | senior eng, low tolerance for marketing | Very low; needs an invite + `show` tag | only when genuinely show-worthy; story over pitch |
| Dev newsletters (PulseMCP, TLDR, Console.dev, Cooperpress) | broad dev reach | Editorial — you pitch the editor | short, honest, repo-led note when there's a real release |
| HN | covered separately (see show-hn.md) | — | not part of this plan |

> Verify before posting: exact self-promo rules for r/LocalLLaMA and r/ChatGPTCoding (sidebars/wiki),
> which MCP Discords have a #showcase channel, and current newsletter submission forms. Flagged as a
> research gap in domain-research.

---

## 30-day cadence

Four weeks. Week 1 is pure contribution (earn standing). Promotion stays rare and earned throughout.

### Week 1 — show up, contribute, zero promotion
- Join r/mcp, the MCP Discords, r/ChatGPTCoding, r/LocalLLaMA. Read rules + pinned posts.
- In r/mcp: post a short intro of what you built and tag mods to request the mcp-server-authors flair
  (this is the sanctioned path in, and opens author channels). This is the one Week-1 exception where
  naming the project is expected.
- Answer 5–10 real questions across venues about MCP setup, token cost, context, doc routing. No link
  to trovex unless it's a direct, honest answer to "is there a tool that does X" — and even then, mention
  it plainly and move on.
- Goal: be a recognizable helpful name before you ever ask for attention.

### Week 2 — one substantive contribution that happens to involve trovex
- Write one genuinely useful post that stands on its own even if trovex didn't exist. Candidates:
  - "How I measured what my coding agent spends rereading .md files (and how I cut it)" — method + numbers,
    trovex as the tool you happened to use, not the point of the post.
  - "Patterns for keeping a coding agent on the *current* doc, not the stale one" — share the freshness
    idea; link trovex once at the end.
- Post in the single best-fit venue (likely r/mcp or r/ChatGPTCoding). Not both same-day.
- Reply to every comment. Concede limits (small doc sets, repo-dependent savings).

### Week 3 — go where the question already exists
- Search each venue for live threads about token cost, agents rereading files, CLAUDE.md going stale,
  RAG-for-code. Answer them well. Mention trovex only where it's a direct, honest fit.
- In the relevant MCP Discord #showcase channel (if one exists), share trovex once with the savings framing.
- Optional: pitch ONE newsletter editor a short, honest note (template below) if there's a real release.

### Week 4 — consolidate, don't escalate
- Follow up on threads where people tried it; collect bugs/feedback into GitHub issues (that's real proof).
- A second value-first post only if Weeks 2–3 earned the standing. If engagement was thin, keep contributing
  and don't push.
- Write up what landed and what didn't; hand the next 30 days back to cmo.

---

## Per-venue seed drafts (a human posts, after reading rules)

> All drafts: lowercase `trovex`, no hype, no company name, real ~60% only. Each is a starting point to
> personalize — never paste verbatim across venues.

### r/mcp — intro + flair request (Week 1)
```
Built a small MCP server I've been using on my own repos: trovex. It indexes a repo's markdown and
serves my coding agent the one doc that answers a query (a path:line pointer + a freshness marker:
canonical / stale / duplicate) instead of letting it reread a pile of .md files each session to guess
which is current. Local-first — SQLite + on-device embeddings, no cloud.

Mods — could I get the mcp-server-authors flair? Happy to help in the author channels.
Repo: github.com/Synergix-lab/trovex
```

### r/ChatGPTCoding — value-first post (Week 2)
```
Title: I measured what my coding agent spends just rereading .md docs each session

Body: On a doc-heavy repo, my agent burned a chunk of every session rereading runbooks/ADRs/READMEs to
work out which doc was canonical — and sometimes still grabbed the stale one. I started logging the
tokens spent on those .md reads. Sharing the method in case it's useful: [method + a real before/after
number]. The thing that cut it for me was routing the lookup to one current doc + reading only the
relevant section instead of whole files. I'm using an MCP server I wrote (trovex) to do it, but the
measurement approach works whatever you use. Curious how others keep agents on the current doc.
```

### r/LocalLLaMA — only if it clears the sidebar; local-first angle (Week 3)
```
For folks running agents locally: trovex is a local-first MCP server that routes a coding agent's doc
lookups to the one canonical .md (path:line + freshness) instead of a full reread. Embeddings run
on-device (fastembed/ONNX), vectors in SQLite, no API keys, nothing leaves the machine. ~60% fewer
tokens on .md reads on my repos; it ships a view so you can check the number on yours. Feedback on the
routing welcome. Repo: github.com/Synergix-lab/trovex
```
> Post this ONLY if r/LocalLLaMA's rules allow a self-authored tool share, and ideally as an answer in an
> existing thread rather than a standalone promo. If unsure, don't.

### Dev newsletter editor pitch (Week 3, email/DM — not a public post)
```
Subject: trovex — open-source MCP server that cuts what coding agents spend rereading docs

Short version: coding agents reread a repo's .md files every session to find the canonical doc, burning
tokens. trovex indexes the markdown and serves the one current doc (path:line + freshness marker) so the
agent reads one section, not six files. Local-first, AGPL core / MIT CLI. ~60% fewer tokens on .md reads
on my repos, with a savings view to verify on your own. If it fits your readers: github.com/Synergix-lab/trovex
No rush, and happy to answer anything.
```

---

## What NOT to do (hard stops)

- No alt accounts, no asking anyone to upvote, no planted "anyone tried trovex?" questions.
- No same link dropped across multiple venues the same day.
- No DMing strangers cold with the link.
- No arguing with skeptics or getting defensive; concede real limits.
- No mentioning the consulting business by name and no sales pitch in any community surface. If someone
  asks about help running agents at scale, a plain "I do that kind of consulting, happy to talk — DM me"
  is the most it ever gets, and only when asked.
- No "Synergix" anywhere in any post or profile (brand rule). The repo URL identifier is the only place
  that string may appear.
- No fabricated experience or numbers. If you didn't measure it, don't claim it.

## How we'll know it worked (north-star aligned)

- Real installs/indexes from people who found us in a thread (activation), and bugs/feature requests filed
  as GitHub issues — that's the signal that beats upvotes.
- A standing reputation as a helpful contributor in r/mcp and the MCP Discords (future posts land warmer).
- The occasional "we run a team, can you help" DM — the consulting north star. One of those is worth more
  than a hundred upvotes that don't install.

*All copy above is a draft. Nothing has been posted to any community.*
