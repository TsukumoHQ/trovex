# Traffic Hygiene — clean reads before launch

*Owner: analytics-lead · Status: convention (settings + harness rule, no app code) · Applies to every Plausible read (dashboard, digest, blog-performance).*

Today's baselines (the "2 visitors", 8/30 posts, 19 pageviews) are **100% crawler + our own
verification traffic** — zero organic. Without hygiene they'd masquerade as real the instant
anyone reads the dashboard post-launch. This makes every read trustworthy with no asterisks.

## 1. Bots — already filtered

The real pa- client tag (`pa-jilb7PdthxKosl9rmJW-s`) **ignores bot/headless traffic** by
default (UA + automation checks; confirmed in the script source — it logs `Ignoring Event:`
and honors `localStorage.plausible_ignore` + localhost). Keep **Bot filtering = ON** in the
Plausible dashboard (default). No action beyond confirming the toggle.

> Caveat that bit us: a **UA-spoofed headless** browser (our e2e verification) *bypasses* the
> bot filter and looks human — which is exactly why our test events landed. §3 fixes that.

## 2. Internal / team browsers — exclude with one flag

The pa- script honors `localStorage.plausible_ignore`. Each team member runs this **once** in
the browser devtools console on `https://tsukumo.ch`:

```js
localStorage.plausible_ignore = "true"   // this browser is never counted again
```

Anyone regularly hitting the live site (founder, leads doing QA) should set it. No build change.

## 3. Verification harness — MUST self-exclude (the rule)

Any Playwright/headless check against **prod** must set the ignore flag so it never pollutes
analytics. Add to the browser context before navigating:

```js
await ctx.addInitScript(() => { try { localStorage.setItem("plausible_ignore", "true"); } catch {} });
```

This runs before page scripts on each origin, so `window.plausible(...)` no-ops for that
session. **Every future e2e event-verification uses this** — verify the wiring without
inflating the dashboard. (Past verification events can't be deleted via the API; §4 handles
the already-dirty window.)

## 4. Data handling — start real reads at launch

Plausible has no delete-event API, so the pre-launch window can't be scrubbed. Instead:

- **All reads start at the distribution/launch date.** Pre-launch (through ~2026-06-17) is
  labeled **baseline-noise (crawler + verification), not organic** — never reported as real.
- The runners already pull **explicit custom date ranges** — set the start to launch day once
  distribution begins; everything before is annotated, not counted.
- The first "real" organic read = first window that starts after launch *and* after §2/§3 are
  in effect.

## 5. Acceptance

- [x] Bot filtering confirmed on (pa- script default) + the UA-spoof caveat documented.
- [x] `localStorage.plausible_ignore` convention for internal/team browsers.
- [x] Verification-harness self-exclude rule (addInitScript flag) — no future e2e pollution.
- [x] Data-handling: reads start at launch date; pre-launch = annotated baseline-noise, no scrub-API.
