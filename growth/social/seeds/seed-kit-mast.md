# Off-site seed kit — Berkeley MAST (why multi-agent systems fail)

> **DRAFT seed kit. A HUMAN fires each, on its own cadence. Nothing auto-posted.**
> Lever: analytics 05fe46ee — 0/4 owned-domain citations; on-page is maxed, only
> OFF-SITE moves it (Perplexity/ChatGPT source Reddit + HN + Lobsters heavily).
> Source post: `tsukumo.ch/blog/why-multi-agent-ai-systems-fail` (Berkeley MAST).
>
> **Positioning = WAITLIST SOFT-LAUNCH.** Seeds point to the blog writeup (+ waitlist),
> NEVER "install now", NEVER pre-empt the orchestrated launch. The seed is a genuinely
> useful data point that happens to link our breakdown — not an ad.
>
> **Proof rule:** only first-party number is trovex ~60%; every MAST figure is attributed
> + verbatim. **Handle:** @tsukumohq. **Owner-title:** founder posts as a builder, not a
> tsukumo exec. anti-slop self-gate.

## The fact these seeds carry (attributed, verbatim)
UC Berkeley's MAST study hand-read **1,600+ failed traces across 7 multi-agent frameworks**
(Cohen's κ 0.88) and split the failures: **43.9% system design / specification, 32.2%
inter-agent coordination, 23.9% verification** — 14 failure modes in 3 categories. Roughly
three quarters are specification + coordination, **not the model**. Paper: "Why Do Multi-Agent
LLM Systems Fail?" (arXiv 2503.13657).

The operator takeaway (ours, honest): if your fleet underperforms, a bigger model rarely fixes
it; the orchestration around it does. Same model, better design, large measured gains.

---

## 1. Hacker News — link submission + first comment (founder, builder voice)
**Title (submit the paper, not our blog — HN prefers primary sources):**
`Why Do Multi-Agent LLM Systems Fail? (Berkeley MAST taxonomy)`
URL → the arXiv paper (`arxiv.org/abs/2503.13657`).

**First comment (post immediately after, this is the seed):**
> Spent a while with this one because it matched what we keep seeing running agent fleets.
> They hand-annotated 1,600+ failed traces across 7 frameworks and the failures aren't where
> people reach first: ~44% system design/spec, ~32% inter-agent coordination, ~24%
> verification. Only about a quarter is anything you'd fix with a bigger model.
>
> The part that stuck: same model, better-designed system, big jump. So the work is the
> orchestration, not the swap. I wrote up the operator angle (what each category looks like
> when it's your on-call) here if useful: tsukumo.ch/blog/why-multi-agent-ai-systems-fail
>
> Curious what others do for the coordination failures specifically — that's the one we find
> hardest to instrument.

*Notes: link our blog only in the comment, paper is the submission. Don't astroturf upvotes.
Reply to responses for the first hour. No "install" anything — there's nothing to install yet.*

---

## 2. Lobsters — `ai` tag, link + authored comment
**Submit:** the blog writeup is acceptable IF you author a real comment and your self-link
ratio stays under ~25%. Safer: submit the **paper**, comment with our breakdown.
**Comment seed:**
> Berkeley's MAST is the first real failure taxonomy I've seen for multi-agent LLM setups —
> 1,600+ traces, κ 0.88, so the annotation actually holds up. Failures land 43.9% design/spec,
> 32.2% coordination, 23.9% verification. We run agent fleets and pulled out what each
> category looks like in production: tsukumo.ch/blog/why-multi-agent-ai-systems-fail

*Notes: Lobsters punishes promo hard. One link, lots of substance, engage in replies.*

---

## 3. r/LocalLLaMA — text post (value-first), link in a comment
**Title:** `Berkeley read 1,600 multi-agent failure traces — most of it isn't the model`
**Body:**
> Came across the MAST study (UC Berkeley) and it reframed how I think about multi-agent
> setups. They hand-annotated 1,600+ failed traces across 7 frameworks and grouped them into
> 14 failure modes / 3 categories: ~44% system design + specification, ~32% inter-agent
> coordination, ~24% verification. So ~3/4 of failures are the wiring, not the model.
>
> Matches my experience running agents — adding a stronger model or more agents rarely fixes a
> coordination failure; it just adds another handoff to drop. The authors showed the same model
> in a better-designed system performing much better.
>
> Anyone here instrumenting coordination failures in local multi-agent stacks? That's the
> category I find hardest to catch before it ships.

**First comment (the link):**
> Paper: arxiv.org/abs/2503.13657 — and I wrote up the per-category operator view here:
> tsukumo.ch/blog/why-multi-agent-ai-systems-fail

*Notes: r/LocalLLaMA values local/self-hosted framing + real discussion. Link in comment, not
the body. Build account history first; respect ~9:1 give:promote.*

---

## 4. r/ChatGPTCoding — text post (operator angle)
**Title:** `If your multi-agent coding setup keeps failing, Berkeley says it's probably not the model`
**Body:**
> The MAST study hand-read 1,600+ failed multi-agent traces and the split was ~44% design/spec,
> ~32% coordination, ~24% verification. The reflex fix (bigger model, more agents) targets the
> ~24% and misses the 76%.
>
> For coding agents specifically the coordination one bites: two agents on one repo drift,
> assumptions misalign, a handoff drops. Practical takeaways I've found: keep one shared source
> of truth instead of synced copies, scope what each agent owns, and instrument the handoffs.
>
> Full per-category breakdown + the paper: tsukumo.ch/blog/why-multi-agent-ai-systems-fail

*Notes: lead with the dev's pain, not the brand. The trovex angle (one shared source of truth
cuts re-reading ~60%) stays implicit here — don't pitch; the blog carries it.*

---

## 5. MCP / agent Discords (informal share)
> If you build with multiple agents — Berkeley's MAST taxonomy is worth a read. 1,600+ failed
> traces, and ~3/4 of failures are spec + coordination, not the model. We pulled the operator
> view out of it: tsukumo.ch/blog/why-multi-agent-ai-systems-fail

*Notes: only drop in channels where a substantive link is welcome (e.g. #papers / #show).
Read the channel's promo rule first. One line, no pitch.*

---

## Posting discipline (all channels)
- **One human fires these**, staggered over days — never the same hour, never all five.
- Account history first. A cold account dropping a link reads as spam and can get the domain
  flagged (the opposite of the citation goal).
- Link the blog in a COMMENT, submit the PAPER where the community prefers primary sources.
- Engage replies for the first hour — that's where reach + citation-worthiness compound.
- WAITLIST framing only: trovex.dev/blog + waitlist. No "install now". No launch pre-empt.
- If a thread asks "what's trovex / can I try it" — answer honestly: public beta, here's the
  writeup + waitlist, point them to trovex.dev. Don't oversell.

## Coordinate
Aligns with tech-copywriter's earned-evidence seed-kit standard (MAST = #404). Same source post,
same waitlist frame — confirm no overlap on which communities each of us seeds before a human fires.
