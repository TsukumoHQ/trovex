# trovex — private-beta waitlist drivers + public-launch HOLD index (DRAFT)

**Status:** DRAFT / copy only. Nothing posted. A human fires anything live.
**Owner:** launch-lead · **Reviewed against:** gtm-model, north-star (beta), voice, no-synergix-mention, copy-gate
**GTM now:** hybrid private beta. Landing trovex.dev PUBLIC, CTA = **request beta access**. Repo PRIVATE.
Primary conversion = **waitlist signup** (each = a qualified lead). Public OSS launch comes later.

---

## 0. The one rule that changes every draft

**The repo is private now.** Any public-facing copy must link **trovex.dev** (the waitlist), NOT
`github.com/Synergix-lab/trovex` — that link 404s for everyone without access and reads as broken.
So in beta-phase copy: drop the repo link, drop "install in a minute / uv run", and point at "request
beta access." The proof shifts from "go run it" to "here's what it does + the savings number + get on the list."

---

## 1. Public-launch kit — HOLD until the public OSS phase

These are DONE and ready, but **frozen** until cmo lifts the public-launch hold. Do not submit/post any of them.

| File | Channel | Status |
|---|---|---|
| mcp-registries.md | MCP Official Registry + checklists | **HOLD** — needs public repo + PyPI (post-beta) |
| registry-variants.md | Glama / mcp.so / awesome-mcp / PulseMCP | **HOLD** — post-beta |
| show-hn.md | Show HN | **HOLD** — one-shot, fire at public launch, weekday AM |
| product-hunt.md | Product Hunt | **HOLD** — one-shot, post-beta |
| outreach.md | newsletters / Discords | **HOLD** for the public version; beta-tease variant below |
| community-plan.md | subreddits / Discords | **REFRAME** — beta variant below |
| faq-bank.md | reply bank | keep — still valid; add beta Q's (§4) |
| .github/workflows/publish-mcp.yml (PR #52) | registry publish | **HOLD/UNFIRED** — do not merge til public phase |

When the hold lifts: these need one scrub pass (re-enable the repo link, flip "request access" back to
"install"), then fire in the sequence in mcp-registries.md §0.

---

## 2. Beta narrative (the honest framing)

Not "exclusive early access" hype. The plain version:

> I'm building trovex — a tool that stops coding agents rereading your repo's docs and burning tokens.
> It's in private beta while I work with the first handful of teams. If the token-cost problem is yours,
> request access and I'll get you in.

Rules: no fake scarcity ("only 50 spots!"), no countdown gimmicks, no invented testimonials (beta hasn't
run yet). The pull is the real problem + the ~60% number + a genuine "I want early users' feedback."

---

## 3. Reframed community seed drafts (beta → waitlist)

> Same value-first rules as community-plan.md (contribute >> promote, read venue rules, no copy-paste).
> Link trovex.dev, not the repo. A human posts, after reading rules.

### r/mcp — building-in-beta intro
```
Been building an MCP server for my own repos and opening a private beta: trovex. It indexes a repo's
markdown and serves my coding agent the one current doc (path:line + a freshness marker: canonical /
stale / duplicate) instead of rereading a stack of .md files each session. Local-first, no cloud.
~60% fewer tokens on my doc-heavy repos. Working with a few early teams before a public release — if
that problem's yours, access is at trovex.dev. Happy to talk routing/freshness here either way.
```

### r/ChatGPTCoding — value-first post (beta CTA at the end, soft)
```
Title: I measured what my coding agent spends just rereading .md docs each session

Body: [same measurement method + a real before/after number — the post stands alone]. The fix for me was
routing the lookup to one current doc and reading only that section. I've built that into a tool I'm
running a private beta of (trovex, trovex.dev) — but the measurement approach works whatever you use.
Curious how others keep agents on the current doc.
```

### Discord (MCP / client servers) — answer-first, beta mention only when it fits
```
[Genuinely useful answer to their actual question.] FWIW I'm building a small MCP server for exactly this
(trovex — routes the lookup to one canonical doc + freshness; private beta at trovex.dev). The
measurement idea works whatever you use though.
```

---

## 4. Beta-specific Q&A (append to faq-bank.md when posting in beta phase)

**Q: Why private beta / where's the repo?**
> It's closed while I work with the first few teams and get the rough edges off. Public open-source release
> comes after. Request access at trovex.dev and I'll get you in.

**Q: What do I get as a beta user?**
> Early access to the tool, a direct line to me for bugs/requests, and you shape what ships before the
> public release. No cost.

**Q: Is it paid?**
> No. The tool's free; I do consulting for teams running agents at scale. Beta's about feedback, not sales.

**Q: When's the public / open-source launch?**
> *(Founder: give an honest "no fixed date / when the beta feedback says it's ready" — don't promise a date.)*

---

## 5. Beta-tease newsletter note (soft, optional — a human sends 1:1)

```
Subject: trovex (private beta) — cutting what coding agents spend rereading docs

Hi [name],

[One specific line on why it fits their readers.] I'm building trovex: it serves a coding agent the one
current doc for a query (path:line + freshness) instead of letting it reread the repo's .md every session.
Local-first, ~60% fewer tokens on doc-heavy repos. It's in private beta now, public OSS release later — if
it's worth a mention when it opens up, I'll keep you posted. Early access: trovex.dev.

[your name]
```
> Most newsletters want a usable/installable thing — for many, the real pitch waits for the public launch.
> Use this only where a "building it, beta now" note genuinely fits; otherwise hold the outreach.md version.

---

## 6. Guardrails (beta phase)

- Link **trovex.dev** (waitlist), never the private repo. No "install now / uv run" in public beta copy.
- No public registry/HN/PH posting (HOLD). No merging PR #52.
- No fake scarcity, no countdowns, no invented beta testimonials (beta hasn't run).
- No "Synergix" anywhere. Real ~60% only, repo-dependent, framed as measured.
- Consulting stays low-key ("working with a team? let's talk"), only when asked.
- Everything here is a draft for a human to post. Nothing fires automatically.

## 7. Handoff

- cmo: this freezes the public-launch kit and gives waitlist-driver variants. When you lift the public hold,
  I'll run the one scrub pass (re-enable repo link + install copy) and fire in sequence.
- Coordinate with social-lead (X/LinkedIn beta-tease) and content-lead (landing waitlist CTA copy) so the
  "building trovex, request access" line is consistent across surfaces.

*All copy above is a draft. Nothing has been posted or published.*
