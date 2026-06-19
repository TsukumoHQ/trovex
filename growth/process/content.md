# Content lane — process + veille (the repeatable machine)

*Owner: content-lead · how the content lane runs without micro-dispatch. Input → output →
cadence → quality gate, plus a veille loop that feeds the machine. Pairs with memory
`content-current-state` (live status) and `content-veille` (sources).*

---

## What this lane owns

Discovery + activation copy toward the north star (qualified reach → consulting leads):
- **Blog cornerstones** (tsukumo `content/blog/*.md`) + the **editorial calendar**.
- **/answers + /vs** copy on trovex (verdict leads + acceptedAnswer mirror).
- **Funnel-support copy**: /assessment sample-readout, post-booking confirmation, lead magnets.
- **Repurpose angles** for social (blog-atoms) + **earned-citation outreach** (newsletters,
  listicles, citation-seeds, founder guest-posts).
- **Bio/about pack** + canonical-blurb application on company surfaces (llms.txt, directories).
- **Anti-slop gate** on all human-facing copy.

NOT mine: channel strategy (cmo), money-page conversion copy + cases (tech-copy), social
posting/calendars (social), registry listings (launch), schema/llms.txt wiring (geo), visuals
(design), conversion structure (cro).

## The repeatable workflow (per piece)

1. **Trigger** → pick the skill: write/rewrite page → `copywriting`; cornerstone/calendar/
   repurpose → `content-strategy`; edit/tighten/voice → `copy-editing`; magnet → `lead-magnets`.
2. **Anti-cannibalization check (mandatory first):** does a live post / `/vs` page / another
   lead's file already own this? With 37 live posts, assume yes until proven. If owned → sharpen
   angle or skip. Coordinate boundaries in `team:leads` BEFORE writing (collisions cost more than
   a 2-line DM).
3. **Draft** in owner voice (see gate). Reuse the canonical `positioning-blurb` VERBATIM where a
   full company blurb is wanted; never re-paraphrase (that's pitch drift).
4. **Anti-slop gate (hard, every piece):** run the checks below. Fail → rewrite → re-run.
5. **PR** to the right repo (`Synergix-lab/tsukumo` for agency/blog content; `Synergix-lab/trovex`
   for trovex OSS surfaces). Clone isolation: own clone per agent (`/tmp/tsukumo-content-lead`).
6. **Self-merge** if low-risk + CI build green + no collision on another open PR's file
   (autonomy-rules). Else leave for cmo.
7. **Handoff** in `team:leads`: who fires/wires it (social posts, launch fires outreach, geo
   wires schema, cro/fullstack wire pages). A human fires all public posts.
8. **Record** state in memory if it changes the lane picture.

## Quality gate (the anti-slop + honesty checklist)

- Owner voice: founder first-person, contrarian thesis + warm delivery, patio11-dense, concrete.
- **Zero fabricated proof.** Only real number = trovex **~60% fewer tokens per lookup**; `~10x`
  is positioning, not a metric. No invented clients/quotes/logos/dates.
- Banned (grep): revolutionary, seamless, supercharge, unlock, leverage, robust, ensure, turnkey,
  game-changer, AI-powered, cutting-edge, best-in-class, foster, elevate, crucial, pivotal +
  owner's list (LLM tics, consultant hype).
- ≤1 em-dash per paragraph (prefer 0 in trovex house style; tsukumo blog allows sparing);
  no exclamation points; sentence-case headings; straight quotes; bursty rhythm.
- Lowercase `tsukumo`/`trovex`; EST 2026 Switzerland; no public prices; no "Synergix" on public
  surfaces; social handle `@tsukumohq` verbatim; OSS surfaces keep consulting to a low-key footnote.
- Verify internal links resolve; deep-link to the answering surface; UTM per `utm-taxonomy-contract`.

## Cadence

- **Reactive (event-driven):** cmo dispatch or a veille signal → produce within the day.
- **Daily veille scan** (below) → 1-2 reactive angles handed to social/positioning.
- **Weekly:** re-check editorial-calendar vs live inventory; refresh `dateModified` + tighten any
  `/answers` geo flags; prune dead handoffs.
- **Saturation rule:** blog is saturated (37 posts). Default to internal-linking, funnel-support,
  and repurpose over net-new cornerstones. Don't manufacture filler; if genuinely empty → HOLD +
  ping cmo with done + 2-3 concrete options (never idle silent, but no void-pings either).

---

## Veille loop (feeds the machine)

**Goal:** turn what's happening in AI-dev into reactive content angles + positioning input, daily.

**Sources (scan daily):**
- Model/news: Anthropic (Claude/Fable releases, pricing, context), major AI-coding-tool moves
  (Cursor, Copilot, repomix, MCP ecosystem). New capability or price = a token-cost/operator angle.
- CTO/eng-leadership discussion: HN front page + comments, r/ExperiencedDevs, r/ChatGPTCoding,
  r/mcp, Lobsters; dev newsletters (TLDR, Pointer, Console.dev, Pragmatic Engineer).
- Competitor/category: "best MCP tools" + alternatives roundups (trovex inclusion), AI-consulting
  positioning chatter (tsukumo differentiation).
- Our own signal: geo citation monitor (cited/uncited per query), analytics funnel (which content
  drives /assessment), social engagement (which threads land).

**Loop:** scan → spot a live thread/news with a tsukumo/trovex angle → check anti-cannibalization
→ draft the reactive atom/thread/answer (owner voice, real ~60% only) → post to `#veille` (Slack,
social owns) + memory + hand to social/launch to fire. Net-new cornerstone only if it's a real
GEO gap, not a hot-take.

**Output → where:** reactive social angles → social (`team:leads` + blog-atoms); positioning
shifts → flag tech-copy/cmo; recurring citable gap → editorial-calendar backlog. Honesty gate
always; a hot take that needs a fabricated number doesn't ship.

**Cadence:** daily light scan (~15min equivalent), reactive output as signals warrant. Don't
force a daily post; force a daily *scan*.

---

## Current state (snapshot — see memory `content-current-state` for live)

Funnel + content built and shipped (15 PRs merged 06-19): blog 37 posts (saturated), /answers+/vs
tightened + de-slopped, sample-readout + booking-confirmation, bio/about pack + `@tsukumohq` lock,
llms.txt aligned, editorial-calendar refreshed, blog-atoms 1-5 + X threads for the /assessment
cornerstones, earned-citation outreach mapped + handed to launch. Phase = DISTRIBUTION; drafts are
fire-ready, a human fires. Gates blocking more = owner (Resend, #285 CIL, wrai.th eng, registries).
