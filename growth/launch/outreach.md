# trovex — ecosystem outreach drafts (newsletters + Discords) (DRAFT)

**Status:** DRAFT / copy only. A human sends each, personalized. Nothing sent here.
**Owner:** launch-lead · **Reviewed against:** voice, no-synergix-mention, copy-gate, community-plan.md
**Repo:** github.com/Synergix-lab/trovex · **Landing:** trovex.dev

> Rule: outreach is a personalized 1:1 note, not a blast. One target, one tailored message, one reason it
> fits *their* audience. No BCC lists, no identical copy to five editors, no DM spam. If you can't say why
> it fits this specific venue, don't send. Pairs with the community plan's value-first ratio.

> **Scope / deconfliction (with content-lead):** this file = **launch-moment announce** outreach — a 1:1
> note to newsletters/Discords when there's a real release to announce. The **evergreen earned-citation**
> outreach (get trovex/tsukumo ADDED to listicles/roundups + cited by AI engines, tied to geo's target
> queries) is content-lead's `content/earned-citation-outreach.md` — different angle (announce vs get-cited);
> don't write competing newsletter pitches. The same newsletter can receive both, at different moments, with
> different messages.

---

## A. Targets (verify each is current + find the real submission path before sending)

**Newsletters / publications**
- PulseMCP newsletter — MCP-native audience, highest fit (also our registry editorial lever).
- TLDR (TLDR AI / TLDR Web Dev) — broad dev reach; has a "submit a tool" path.
- Console.dev — curates dev tools, OSS-friendly, exactly our reader.
- Cooperpress (JavaScript Weekly et al.) — only if/when there's a JS-relevant angle (weaker fit; low priority).
- Bytes / other AI-coding newsletters — research current ones; fit = "people paying for coding agents."

**Discords / communities (post in the right channel, after reading rules)**
- Official MCP / modelcontextprotocol Discord — #showcase or equivalent only.
- Client Discords: Cline, Continue, Cursor — where people already run agents; answer questions first.
- An "AI coding agents" Discord/Slack if an active one exists — research before joining.

> Flagged: confirm each newsletter's submission form/editor contact and each Discord's promo channel +
> rules before any send. Don't assume a contact email.

---

## B. Newsletter editor note (1:1 email — personalize the first line per venue)

```
Subject: trovex — open-source MCP server that cuts what coding agents spend rereading docs

Hi [name],

[One specific line on why it fits THEIR readers — e.g. "you've covered MCP servers and dev-tool token
cost, so this might fit."]

Short version: coding agents reread a repo's .md files every session to find the canonical doc, burning
tokens and sometimes still grabbing the stale one. trovex indexes the markdown and serves the agent one
current doc (a path:line pointer with a freshness marker), so it reads one section, not six files. It's
local-first (SQLite + on-device embeddings, no cloud or keys) and open source (AGPL core, MIT CLI).

The honest number: ~60% fewer tokens per .md lookup on doc-heavy repos, measured on my own repos, and the
tool ships a savings view so a reader can check it on theirs. On a small doc set it won't save much.

If it's a fit for an issue: github.com/Synergix-lab/trovex. Happy to answer anything or do a short writeup.
No rush either way.

[your name]
```
> Brand check: no company name. The "I" is the founder. One em-dash max in the body; keep it plain.

---

## C. Discord #showcase post (after you've been a useful member first)

```
Built a small local-first MCP server I use daily: trovex. It indexes a repo's markdown and serves my
coding agent the one current doc (path:line + freshness: canonical / stale / duplicate) instead of
rereading a stack of .md files each session. Reads one section, not the whole file; there's a write path
so agents share one store. ~60% fewer tokens on my doc-heavy repos, with a view to check it on yours.
Local, no keys. Feedback on the routing welcome: github.com/Synergix-lab/trovex
```
> Post once, in the showcase channel only. Then stick around and answer follow-ups. Use the faq-bank.md
> answers for replies.

---

## D. Discord question-answer template (the main mode — not promo)

Most Discord value is answering, not posting. When someone asks about token cost / agents rereading docs /
keeping agents on current docs, answer the question well first; mention trovex only if it's a direct, honest
fit, like:
```
[Genuinely useful answer to their actual question.] FWIW I wrote a small MCP server for exactly this
(trovex — routes the lookup to one canonical doc + freshness instead of a reread); the measurement idea
works whatever you use though.
```

---

## E. Cadence + guardrails

- Send newsletter notes one at a time, spaced out — not a batch on the same day.
- One Discord showcase post per server, ever; everything else is answering questions.
- Track each outreach (target, who, date, response) in a simple sheet for cmo.
- Never: buy placement framed as editorial, fake a personal connection, send identical copy to multiple
  editors, DM strangers cold, or post the link in a non-promo channel.
- No "Synergix" in any note or profile (brand rule). No fabricated proof. ~60% always repo-dependent + verify.
- Drafts only — a human reviews and sends. No automated sending.

## F. What success looks like

A handful of genuinely-fitting placements/mentions that send devs who install and index (activation), and
warmer standing in the MCP/agent communities for later. One good editor relationship beats ten cold blasts.

*All copy above is a draft. Nothing has been sent.*
