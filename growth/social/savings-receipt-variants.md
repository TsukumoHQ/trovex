# Savings-receipt variants — the dark-social atom (DRAFT spec)

> **Status: DRAFT spec — nothing posted.** This specs 4 copy-pasteable "savings receipt"
> variants (text + screenshot guidance) that any lead can drop into a post, a Discord/Slack
> channel, or a DM. The receipt is trovex's most shareable asset: it travels alone, with no
> context, and still lands. **Real numbers only** — the ~60% figure or the user's own measured
> receipt. Never mock up a fake number and present it as real.
>
> **Coordinate with cro-lead** (owns the actual savings-receipt dashboard/feature). When the
> dashboard's real labels/fields land, match this copy to them exactly. Until then these use
> the labels already visible on the landing demo: "would have read" vs "actual read (top-1)",
> "reduction vs no-trovex", "SAVED · LAST 7 DAYS".

## Design rules (apply to every variant)
- **Self-explanatory with zero context.** Someone who's never heard of trovex should get it
  from the image alone. One title line, the before/after, the percent, the wordmark.
- **Real numbers only.** If you don't have a real receipt yet, ship the variant with a
  `[your number]` placeholder and a note — don't invent one.
- **Legible at thumbnail size.** Big percent, high contrast. It gets reshared as a tiny image.
- Lowercase `trovex`. No hype words. The number does the persuading.

---

## Variant A — the weekly receipt (default, screenshot)
*Use: the dashboard screenshot itself, lightly framed. Best for X image post / LinkedIn.*

```
┌─────────────────────────────────────────┐
│  trovex · SAVED · LAST 7 DAYS            │
│                                          │
│  would have read   ████████████  ~X,XXX  │
│  actual read       ████          ~XXX    │
│                                          │
│             ~60% fewer tokens            │
│        same answers, on doc lookups      │
└─────────────────────────────────────────┘
```
Caption to pair: `my coding agent's doc-lookup spend, before/after trovex. real numbers.`

## Variant B — the one-line text receipt (copy-paste, no image)
*Use: dropping into a Discord/Slack thread, a reply, a DM. Travels as plain text.*

```
trovex receipt: agent doc lookups went from ~X,XXX → ~XXX tokens for the same answers.
~60% lighter. (one canonical doc instead of rereading the repo to guess which is current.)
```
Note: replace `~X,XXX → ~XXX` with your own dashboard numbers, or drop them and keep "~60%".

## Variant C — the before/after split (screenshot, story-friendly)
*Use: carousel slide / X image / blog inline. Shows the mechanism, not just the number.*

```
BEFORE                          AFTER
agent reads 3 candidate .md     trovex serves 1 current section
to guess the canonical doc      path:line + freshness marker
~720 tokens                     ~280 tokens
                ↓  ~60% fewer tokens, same answer  ↓
```
Caption: `the fix wasn't a bigger model. it was returning one current answer, not a pile.`

## Variant D — the "measure your own" receipt (utility, conversion-friendly)
*Use: invites the reader to generate THEIR receipt — best for activation. Private-beta phase:
gate it behind beta access (the public-OSS install-command version returns at public launch).*

```
want your own receipt?
  trovex is in private beta — request access.
  point it at your repo, run your agent a day,
  and it shows would-have-read vs actual.
~60% is what i saw on lookups. yours will differ — that's the point.
```
Caption: `i'm not asking you to trust my ~60%. get beta access and measure your own.`
Link with it: `https://trovex.dev/?utm_source=x&utm_medium=social&utm_campaign=beta-waitlist#waitlist`
(swap `utm_source=linkedin` on LinkedIn).

---

## Where each variant goes (cross-reference)
- `launch-thread-x.md` post 5/ and `linkedin-3-the-receipt.md` → **Variant A**.
- Forum replies / dark-social drops → **Variant B** (plain text, no image needed).
- Blog/flagship inline + carousels → **Variant C**.
- Activation CTAs / "measure your own" posts → **Variant D**.

## Self-audit
- [x] 4 copy-pasteable variants (2 screenshot-spec, 2 text); each works with zero context.
- [x] Real numbers only; placeholders flagged where a real receipt isn't available yet.
- [x] Only ~60% claimed; before/after (720→280) reconciles to ~60%. No fabricated proof.
- [x] Coordinate-with-cro-lead note for label parity. Lowercase `trovex`. No banned words.
