# Savings-receipt card visuals (DRAFT assets)

Shareable "savings receipt" cards — the dark-social atom. Drop into a post, a Discord/Slack
channel, or a DM; each reads with zero context. Generated via the OpenAI image API (gpt-image-1,
1536x1024). **DRAFT — a human posts.** Pairs with the copy spec in
`growth/social/savings-receipt-variants.md`.

| File | Use | Card |
|------|-----|------|
| `receipt-weekly-card.png` | default; X image / LinkedIn (matches variant A) | dashboard receipt: would-have-read vs actual bars, "~60% fewer tokens" |
| `receipt-before-after-card.png` | story / carousel (matches variant C) | BEFORE ~720 tokens vs AFTER ~280, "same answer" |
| `receipt-hero-card.png` | minimal hero / reply image | giant "~60% fewer tokens" |

## Honesty
- Only the real ~60% figure and the reconciled 720→280 example. No fabricated metrics.
- No Synergix. Lowercase `trovex`. Developer-honest, no hype.
- These are representative illustrations, not a specific customer's receipt. For a real post,
  prefer a screenshot of the user's own savings dashboard when available (see the variants spec).

## Regenerate
Script pattern in the PR; key loaded from `~/.config/trovex-growth/openai.env` (never committed).
The image model can garble small text — review every card before use; the numbers must be exact.
