# Launch T-minus timeline — one fire-order card (DRAFT)

**Status:** DRAFT / quick-reference card. Nothing fires until cmo signals go + owner fires each step.
**Owner:** launch-lead · **Reviewed against:** launch-day-runbook.md, launch-teardown-playbook.md, show-hn.md, product-hunt.md, wraith-registry-packages.md, directory-packages-top5.md, venue-final-posts.md, utm-launch-link-sheet.md, suite-positioning.md
**This is the condensed chronological card.** The detailed ops doc is `launch-day-runbook.md`; this merges HN + PH + registries + community + social into a single dated fire-order with the go-gates and the UTM sheet wired in. **wrai.th leads** (launchable now); trovex slots in when public.

---

## Gate (all green before T-0 — from runbook §7)
- [ ] tsukumo.ch live · trovex waitlist working · deploy verified · design assets ready
- [ ] cmo go + owner free 2–3h · platform account creds · beta proof for any proof claim
- [ ] **analytics-lead:** every `utm_source` + `launch*` campaigns mapped in `analytics.ts` (utm-launch-link-sheet §1) — **the attribution gate.**

---

## T-7 → T-3 — the shelf (compounding, reversible; owner fires, launch-lead [AUTO] where credentialed)
- [ ] **wrai.th registries** — Official MCP Registry (resolve the 2 eng gotchas first), then Glama → mcp.so → awesome-mcp PR. (`wraith-registry-packages.md`)
- [ ] **wrai.th Go ecosystem** — pkg.go.dev (auto on tag), GitHub Release, awesome-go (only if it qualifies).
- [ ] **Free directories** — AlternativeTo, DevHunt, etc. (`directory-packages-top5.md`), homepage links UTM'd.
- [ ] Confirm cold install runs from a clean clone (teardown rule #5). **Nothing ships on launch day.**

## T-2 → T-1 — arm
- [ ] Verify registry propagation started (PulseMCP/Docker/VS Code).
- [ ] Fill every `[bracketed]` real-tech answer in `show-hn.md §A` / `product-hunt.md §A`.
- [ ] Build PH gallery + demo from **real runs**; OG cards ready (design-lead).
- [ ] Assemble the PH supporter list (people who actually use it) — feedback-asks only.
- [ ] Stage the UTM links per surface (`utm-launch-link-sheet.md`); social drafts queued, not posted.
- [ ] Pick the weekday (Tue–Thu AM ET). Owner blocks 2–3h.

## T-0 — Show HN day (the lead one-shot: wrai.th)
- [ ] **Submit Show HN** — repo URL, title from `show-hn.md §A1`. ~9–11am ET.
- [ ] Paste the first comment immediately; secondary link = `…utm_source=hackernews…` (sheet).
- [ ] Founder in-thread 2–3h, fast + deep, limitation-first. **No vote-begging, no booster comments.**
- [ ] Community: r/mcp + MCP Discord #showcase value-first posts (`venue-final-posts.md`), spaced — not vote-pleas.
- [ ] Social: X + LinkedIn (`venue-final` / social-lead), UTM'd. Note submit/first-comment timestamps for analytics.

## T+1 → T+3 — Product Hunt day (separate day — don't stack)
- [ ] Launch 12:01am PT, non-stacked day. Maker first comment = personal story + use-case question (`product-hunt.md §A5`).
- [ ] Gallery = real runs. Notify supporters 1:1 (feedback, never upvotes). Answer every comment.
- [ ] r/ChatGPTCoding / Lobsters value-first posts (`venue-final-posts.md`), spaced.

## T+3 → T+7 — sustain + newsletters/earned media
- [ ] Newsletter notes 1:1, spaced (`outreach.md`); earned-media pitches (`earned-media-targets.md`), rung-5.
- [ ] Reply to late HN/PH comments ~48h; turn bugs into GitHub issues.

## T+48h → T+7 — measure (hand to analytics-lead)
- [ ] installs / index runs / waitlist signups / registry referrals / HN+PH → **activation by source** (UTM + referrer fallback).
- [ ] Watch the **consulting-lead door** (north star), not vanity rank. Re-publish Official Registry on next tag.

---

## Order rationale (one line)
Registries + free dirs first (reversible, compounding → the shelf is ready when traffic hits) → wrai.th Show HN (widest TOF one-shot) → Product Hunt (separate day) → community/social spaced + value-first → newsletters/earned media → measure by source. trovex flips public into this once its beta proof + repo are ready (`unfreeze-checklist` TROVEX TRACK).

*Quick-reference card. Nothing fires until cmo go + owner fires each step.*
