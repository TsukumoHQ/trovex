# UTM Launch-Link Audit (pre-launch)

*Owner: analytics-lead · Date: 2026-06-18 · Scope: every traffic-driving CTA link in the launch + social + registry drafts (both repos) → tsukumo.ch / trovex.dev / wrai.th / yoru.sh. Goal: no channel's ROI silently decays to `direct` on launch day.*

## Verdict: ✅ solid — ship as-is with two tiny polish items

Audited **~70 CTA links** across `growth/launch`, `growth/social`, `growth/agency/launch`
(trovex) and `content/social`, `content/launch-sequencing.md`, registry listings (tsukumo).
**Nearly all carry a correct `utm_source` from the closed map** — hackernews, producthunt,
reddit, lobsters, x, linkedin, discord, mcp-registry, newsletter, trovex, wraith, yoru. No
critical attribution leak: even the few untagged links sit on channels whose **referrer
fallback** (`HOST_SOURCE` in `analytics.ts`) still buckets them (HN/Reddit/X/LinkedIn →
`social`), so nothing goes fully dark.

## Items (minor)

| # | Where | Finding | Action |
|--:|-------|---------|--------|
| 1 | `content/social/reengagement-series.md` | used `utm_medium=dm` + `utm_campaign=reengage` — not previously in the convention | **Fixed:** added `dm` (medium) + `reengage` (campaign) to `utm-convention.md`. No link change needed; they were captured fine, just undocumented. |
| 2 | `growth/launch/show-hn.md` | body link "more at https://trovex.dev" is bare | **Recommend** `?utm_source=hackernews&utm_medium=social&utm_campaign=launch-hn` on the body link. Low severity — the HN referrer already buckets it as `social`; the tag just upgrades `social`→`hackernews`. (Do NOT tag the *submitted* HN URL — HN community dislikes tracking params; the referrer covers it.) → **launch-lead**. |
| 3 | `growth/launch/mcp-registries.md` | registry "Homepage:" field is bare `https://trovex.dev` | **Correct as-is** — registry homepage fields must be the clean canonical URL (some registries validate it). Track registry→site via the *listing* link's `utm_source=mcp-registry` instead (already done). No change. |
| 4 | tsukumo careers links (`/careers?...`) | missing `utm_source` | **Optional/low** — careers = hiring funnel, not the consulting north star. Tag only if you want hiring-source attribution. → careers/social. |
| 5 | `tsukumo.ch/guides/field-guide` (gated download CTA) | base URL bare in the repurpose notes | When a post shares it, append `utm_source=<channel>&utm_medium=social&utm_campaign=agency-launch&utm_content=field-guide`. → social-lead, as posts are finalized. |

## Reference — the correct tag per launch channel

| Channel | `utm_source` | `utm_medium` | `utm_campaign` |
|---------|-------------|--------------|----------------|
| Show HN | `hackernews` | `social` | `launch-hn` |
| Product Hunt | `producthunt` | `social` | `launch-ph` |
| MCP registry (listing link) | `mcp-registry` | `registry` | `agency-launch` |
| Reddit / Lobsters | `reddit` / `lobsters` | `community` | `agency-launch` |
| X / LinkedIn | `x` / `linkedin` | `social` | `agency-launch` |
| Discord seed | `discord` | `community` | `agency-launch` |
| Newsletter | `newsletter` | `email` | `agency-launch` |
| Suite crosslink (trovex/wraith/yoru → tsukumo) | `trovex`/`wraith`/`yoru` | `oss-suite` | `consulting` |

All `utm_source` values above are in the closed `analytics.ts` map (hardened in trovex PR #187),
so they resolve to a real `geo_source`/`channel` — no decay to `direct`.

## Routing

- **launch-lead:** item 2 (HN body link tag) — optional polish.
- **social-lead:** item 5 (field-guide CTA tag when posts finalize).
- **analytics-lead (me):** items 1 done (`dm`/`reengage` in the convention). The map already
  covers every launch source.

## Acceptance

- [x] Every launch/social/registry CTA link audited against the closed `utm_source` map.
- [x] Verdict: solid — no critical leak (referrer fallback covers untagged social links).
- [x] `dm`/`reengage` legitimized in `utm-convention.md`; per-channel correct-tag reference table.
- [x] Cross-lane polish items flagged to launch/social (not edited unilaterally).
