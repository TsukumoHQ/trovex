# social queue tooling — the 20/80 deterministic layer

Owner rule `20-80-deterministic-first`: anything scriptable MUST be a script (free, reliable, no
token burn). The lead spends tokens only on the creative 20% — **angles + copy + review**. The
mechanical 80% — slotting, spacing, collision-avoidance, UTM stamping, anti-slop grep — is this
script.

## `queue_plan.mjs`
Turns a **content pool** into a **ready-to-schedule plan** for the Metricool queue. Deterministic,
pure, no credentials, **does not post**.

```
node growth/social/_tools/queue_plan.mjs --from 2026-06-24 --days 3 [--queue export.json] [--out plan.json]
```

What it does each day, per brand × network:
- fills to the cadence **floor** (`social-cadence-daily` v4: founder 3 X / 3 Th / 2 LI, company 2 X / 1 Th / 1 LI)
- subtracts what's already in the live queue (`--queue` = a `getScheduledPosts` export) so it only fills gaps
- assigns a **staggered slot time** with no same-network-same-hour collision (vs the plan AND the live queue)
- picks pool items **round-robin by pillar** so a day isn't monothematic
- builds **carousel media URLs** from `carouselSlug` + `cards`
- stamps **UTM** (`utm_source` mapped from network → x/linkedin/threads, `utm_medium=social`, campaign, content slug)
- greps every string against the **anti-slop ban-list** and flags em-dash overuse
- flags **floor gaps** (pool too thin → that's the cue to write more angles)
- checks the **portfolio role ratio** per account per ISO-week against the locked
  **60% REACH / 30% ACTIVATION / 10% CONVERT** (brand-channel-direction v1.1, cmo chair-call #1)
  — the ladder applies at the WEEK level, not per post; off-target (±15pp, n≥5) is a violation

Output: `plan.json` (schedulable specs) + a console summary. **Exit code ≠ 0** if there are
violations or unfilled floor — so a human/agent reviews before anything is scheduled.

Pushing `plan.json` to Metricool stays a **reviewed step** (the agent runs the MCP `createScheduledPost`
calls from the plan) — we don't let a script fire posts unattended.

## the pool — `../pool/posts.pool.json`
The creative asset. One object per reusable post:

| field | notes |
|---|---|
| `id` | unique; also the default `utm_content` slug |
| `brand` | `founder` (6430128, builder, trovex.dev, NO consulting) / `company` (6430498, authority, /assessment OK) |
| `network` | `twitter` / `threads` / `linkedin` |
| `pillar` | `bip` / `proof` / `evidence` / `howto` / `authority` (drives round-robin variety) |
| `format` | `single` / `thread` / `carousel` |
| `text` | the post body (X/Threads keep the link in a reply, not the body) |
| `descendants` | optional extra tweets (link reply auto-added from `link`) |
| `firstComment` | LinkedIn only; `{{link}}` is replaced with the UTM'd link |
| `carouselSlug`, `cards` | carousel → media URLs `media/<property>/carousel/<slug>/portrait-NN-*.png` |
| `link`, `utmCampaign`, `utmContentSlug` | UTM stamped by the script |
| `retired` | set `true` to drop an item from rotation |

Guardrails the pool must respect (the script greps the obvious ones; the rest are on the writer):
public-beta framing, only first-party `~60%`/real receipt, no client names, lowercase wordmarks,
founder = no consulting. LinkedIn items must carry a visual (the script flags a naked-text LI).
