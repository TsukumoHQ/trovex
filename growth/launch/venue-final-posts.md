# Venue-final community seed posts (DRAFT, ready-to-fire)

**Status:** DRAFT / ready-to-paste. A human (owner) posts each, after reading the venue's current rules. Nothing live.
**Owner:** launch-lead · **Reviewed against:** community-plan.md, community-participation-playbook.md, wraith-kit.md, show-hn.md, utm-launch-link-sheet.md, voice, no-synergix-mention, north-star
**Repos:** wrai.th → github.com/Synergix-lab/WRAI.TH (public v1.0) · trovex → github.com/Synergix-lab/trovex (private beta)

> Venue-FINAL versions of the `community-plan.md` drafts: **wrai.th leads** (it's the launchable one), each tuned
> to its venue's norms, UTM'd per `utm-launch-link-sheet.md`. The governing rule still holds — **contribute ≫
> promote (~9:1)**, one showcase post per venue ever, everything else is answering. The owner posts; launch-lead
> drafts. Don't paste the same text across venues (spam) — each below is already differentiated.

---

## 0. Before posting (per venue, every time)

- Read the venue's rules + pinned posts; confirm a showcase/self-promo channel exists.
- Be a useful member first (the 9:1 ratio) — these posts are the rare "1," earned by the "9."
- Use the venue's own UTM link (below); never a repo link with a UTM (stripped — see the sheet).
- lowercase wordmarks; no "Synergix"; no consulting pitch; real facts only (wrai.th v1.0 stable; trovex ~60% repo-dependent).
- Reply to everyone; concede limits; turn bugs into GitHub issues.

---

## 1. r/mcp — showcase post (wrai.th)

**Venue norms:** MCP builders; author flair exists (request `mcp-server-authors` from mods first). Showcase tolerated if substantive.
**Link:** `https://trovex.dev/?utm_source=reddit&utm_medium=community&utm_campaign=launch-hn&utm_content=rmcp-post` *(or the wrai.th repo for a code-first crowd — repo = referrer fallback, no UTM)*

```
Title: wrai.th — a local MCP server for running a *fleet* of coding agents (memory, messaging, tasks)

Been running more than one coding agent lately and hit the wall everyone hits: they don't share
memory, they re-derive each other's work, and there's no single view of what they did. So I built
wrai.th — a local Go binary (the `agent-relay` MCP server) that gives a fleet of agents persistent
cross-session memory, inter-agent messaging, and a shared task board, with a dashboard over the lot.

- one binary, one SQLite file, 58 MCP tools, zero required config
- 100% local by default (no cloud, no telemetry); optional API key makes it a shared team server
- any MCP client plugs in (Claude Code, Cursor, Windsurf)

It's open source (AGPL), v1.0. I'd really like feedback on the coordination model — where it breaks
with more agents, and what you'd want from the memory layer. Repo: github.com/Synergix-lab/WRAI.TH

(mods — happy to grab the mcp-server-authors flair if that's the norm here.)
```
> If trovex fits a reply (someone asks about context/token cost), mention it then — don't stack both in the OP.

---

## 2. r/ChatGPTCoding — value-first post (problem-led, tool is a footnote)

**Venue norms:** devs coding with AI; promo tolerated only if it leads with real value. **Lead with the problem + data, not the tool.**
**Link:** `https://trovex.dev/?utm_source=reddit&utm_medium=community&utm_campaign=launch-hn&utm_content=rchatgptcoding-post`

```
Title: Running more than one coding agent — how do you keep them from re-doing each other's work?

Once I went past a single agent, the cost wasn't the model — it was coordination. No shared memory,
so each agent re-derived what another already figured out; no shared task list, so they overlapped;
and I had no view of what ran overnight. Curious how people here handle this.

What worked for me: giving the agents one shared store (persistent memory + a task board they claim
from) so context survives across agents and sessions instead of each starting from zero. I ended up
writing a small local tool for it (wrai.th, open source) but I'm more interested in how others solve
the coordination problem — hand-rolled scripts? a framework? Curious what's holding up for you.
```
> The tool is one line near the end. The post stands on its own as a genuine question.

---

## 3. MCP Discord — #showcase (short, one-time)

**Venue norms:** post once in #showcase only; then answer in help channels. Request server-author flair if offered.
**Link:** `https://trovex.dev/?utm_source=discord&utm_medium=community&utm_campaign=launch-hn&utm_content=mcp-showcase` *(or repo)*

```
Built a local MCP server for running a fleet of coding agents: wrai.th. One Go binary — persistent
cross-session memory, inter-agent messaging, a shared task board, dashboard over the fleet. 58 MCP
tools, zero config, 100% local (optional key for a shared team server). Any MCP client plugs in.
Open source, v1.0. Feedback on the coordination model very welcome: github.com/Synergix-lab/WRAI.TH
```

---

## 4. Lobsters — story submission (only if genuinely show-worthy)

**Venue norms:** senior eng, very low promo tolerance; needs an invite + the `show` tag; story over pitch. **Submit the repo as the story link** (repo = referrer fallback, no UTM).
**Story URL:** `github.com/Synergix-lab/WRAI.TH` · **Tags:** `show`, `go`, `ai`

**Comment to post under it (where the trovex.dev UTM link can go):**
```
Author here. wrai.th is a local Go binary for coordinating multiple AI coding agents — persistent
memory, inter-agent messaging, a shared task board, one dashboard, all over MCP. One binary, one
SQLite file, no cloud. I built it because one agent is fine but several is chaos: no shared memory,
no shared task list, no view of the work.

Honest limitation: [founder — state it plainly, e.g. current multi-machine story / verified clients].
Happy to go deep on the coordination + memory design. Repo in the link; more context:
https://trovex.dev/?utm_source=lobsters&utm_medium=community&utm_campaign=launch-hn&utm_content=lobsters
```
> Only submit if it clears Lobsters' bar; if unsure, don't. Never ask for upvotes.

---

## 5. HN Show — see `show-hn.md` §A (don't duplicate here)

The full HN Show kit (wrai.th-leads) is in `show-hn.md §A` — title variants, 7-beat first comment, Q&A, who-posts.
**Pre-flight here only:** the HN first-comment's secondary link is the UTM'd trovex.dev cross-link:
`https://trovex.dev/?utm_source=hackernews&utm_medium=social&utm_campaign=launch-hn&utm_content=hn-firstcomment` (the submission URL stays the bare repo).

---

## 6. trovex variants (when trovex is public)

When trovex flips public, the same venues get a **trovex** showcase (context/token angle) — reuse the
`community-plan.md` trovex drafts, UTM'd via the sheet (`utm_content=…-trovex`). Until then trovex appears
only as a *reply* when context/token cost comes up, never a second OP. (suite-positioning: wrai.th leads.)

---

## 7. Cadence + guardrails (unchanged from the playbook)

- One showcase post per venue, ever; spaced (not all the same day); everything else is answering.
- ~9:1 contribute:promote. No alt accounts, no upvote-asks, no planted questions, no identical copy across venues.
- No consulting pitch; if asked about team help: "I do that kind of consulting, happy to talk — DM me," only when asked.
- No "Synergix" in any post/profile; no fabricated proof; real facts only.
- Track each post (venue, utm_content, date, response) for the north-star report.

*All posts above are drafts. Nothing has been posted to any community.*
