# trovex — deepened public-launch kit (DRAFT, FROZEN until hold lifts)

**Status:** DRAFT / for the LATER public OSS phase. Do NOT submit/post any of this now (gtm-model = private beta).
**Owner:** launch-lead · **Reviewed against:** mcp-registries.md, registry-variants.md, community-plan.md, unfreeze-checklist.md, voice, no-synergix-mention, copy-gate
**Prereqs (all in unfreeze-checklist.md):** repo public + PyPI + Official Registry live before firing any of this.

> Expands the public kit with: the full registry target list, community seed targets with each venue's rules,
> and an hour-by-hour launch-day runbook. Honest, no thin filler, no fabricated proof. Links flip to repo/install
> at un-freeze (today they'd 404).

---

## 1. Full MCP registry / directory target list

Tiered by impact. Tier 1 = do first; the rest batch after. Master copy in registry-variants.md; mechanics in mcp-registries.md.

### Tier 1 — keystone + high-traffic
| Registry | Submit | Gate / note |
|---|---|---|
| Official MCP Registry (registry.modelcontextprotocol.io) | `mcp-publisher` + OIDC (PR #52) | keystone; auto-feeds PulseMCP/Docker/GitHub-MCP/Anthropic |
| PulseMCP | auto-ingest (weekly) | no submit; editorial-note lever |
| Glama | web form, build-validated | gates the awesome-mcp PR; grab badge |
| awesome-mcp-servers (punkpeye) | GitHub PR | needs Glama listing first; match emoji legend |
| mcp.so | web form + GitHub | renders README preview |

### Tier 2 — client + ecosystem directories (high intent; these users run agents)
| Registry | Submit | Note |
|---|---|---|
| Smithery | web form | needs hosted HTTP endpoint → brand-neutral host first, else skip |
| mcpservers.org | web form / PR | ~4k listings |
| Cline MCP Marketplace | per Cline repo docs | in-client discovery |
| Continue hub/registry | per Continue docs | in-client |
| Cursor MCP directory | per Cursor docs | in-client |
| Docker MCP Catalog (Hub) | auto from Official | confirm propagation, no dup submit |
| VS Code / GitHub MCP Registry | auto from Official | renders in Extensions view |

### Tier 3 — aggregators / long tail (batch, same master copy, one afternoon)
| Registry | Submit | Note |
|---|---|---|
| mcp-get.com | CLI/registry | inherits where applicable |
| Goose / Block extensions | per docs | if relevant |
| Awesome lists (awesome-ai-devtools, awesome-claude) | PR | only where genuinely on-topic |
| Pieces / Raycast / other catalogs | per catalog | only if a real fit; no spammy mass-listing |

**Rule:** don't list the same thing in 30 places for vanity. Tier 1 + Tier 2 = real discovery; Tier 3 only where the audience actually fits. Log each (registry, URL, date, live y/n).

---

## 2. Community seed targets (with each venue's rule that matters)

Same governing rule as community-plan.md: **contribute >> promote**, read each venue's rules first, no copy-paste, problem-first.

| Venue | Rule that bites | trovex angle |
|---|---|---|
| r/mcp | self-promo tolerated if you're a member; tag mods for author flair | core fit; building-in-public intro |
| r/ChatGPTCoding | check pinned promo rules; often a weekly self-promo thread | token-cost + stale-doc pain |
| r/LocalLLaMA | strict; prefer in-thread answers over standalone promo | local-first / on-device embeddings |
| r/LLMDevs, r/AI_Agents | newer, read sidebar | agent context cost |
| r/programming, r/devtools | very low promo tolerance; only truly notable | only the public-launch milestone, framed as a story |
| Lobsters | needs invite + `show` tag; senior, anti-marketing | only when genuinely show-worthy |
| Official MCP Discord | #showcase channel only | one post, then answer |
| Cline / Continue / Cursor Discords | their #showcase / #share | where agent-users live |
| Hacker News | Show HN (show-hn.md); no booster comments | the one-shot |
| dev.to / Hashnode | own-blog cross-post ok | the cornerstone post, canonical to trovex.dev |

> Verify each subreddit's current self-promo rules + which Discords have a showcase channel before any post.
> Per-sub rules drift — this table is a starting map, not a license to post.

---

## 3. Launch-day hour-by-hour runbook (public phase)

Assumes registries already live (Tier 1–2) and the repo public. Two one-shots: Show HN and Product Hunt.
**Do not stack them the same day.** This runbook = the Show HN day; run PH on a separate day, same shape.

**Timezone:** anchor to US ET for HN. Founder blocks the full morning/early afternoon to reply.

| Time (ET) | Action | Owner |
|---|---|---|
| T-1 day | Final pre-flight (show-hn.md §6): install works from clean clone, first comment ready, repo presentable | launch-lead + founder |
| T-1 day | Re-run anti-ai-slop on the flipped (install-mode) copy; confirm no Synergix, green #22c55e on assets | launch-lead |
| 8:00 | Submit Show HN with repo link. Paste the founder first comment immediately | founder |
| 8:00–8:15 | Confirm it's live, title/link correct, first comment posted | founder |
| 8:15–11:00 | Founder answers every substantive comment within minutes. Use faq-bank.md. NO booster comments | founder |
| 9:00 | Soft signal to the warm network it's live (no upvote ask — just "it's up if you're curious") | founder |
| 9:00–12:00 | Monitor for bugs/issues; file + link them in-thread (becomes social proof) | founder + eng |
| 12:00 | Mid-day check: keep replying; share one substantive follow-up if a good question thread emerged | founder |
| Afternoon | Keep answering as long as the thread is active; don't argue, concede real limits | founder |
| EOD | Capture: what questions recurred (feed faq-bank), what broke (issues), any consulting DMs | launch-lead |
| T+1 | Retro: what drove qualified installs? Decide PH day | launch-lead + cmo |

**Product Hunt day (separate):** 12:01am PT submit, gallery from real runs + beta proof, maker first comment ready (product-hunt.md), founder free all day. Same no-vote-manipulation rule.

**Hard rules (both days):** no booster comments / no upvote solicitation (flagged + can kill the post); no fabricated proof; repo/install links only after un-freeze; consulting stays low-key.

---

## 4. Sequencing across the week (so it compounds, not collides)

1. **Day -3 to -1:** registries live + propagating; un-freeze copy scrub done; assets ready.
2. **Day 0:** Show HN (one-shot).
3. **Day +2:** Product Hunt (one-shot).
4. **Day 0 → +14:** community seeding (value-first, per the table) + newsletter notes (outreach.md), spaced.
5. **Throughout:** measure installs/activation + the consulting door (analytics-lead), not vanity rank.

*All of this is frozen. Nothing fires until cmo lifts the public hold (unfreeze-checklist.md §0 gate).*
