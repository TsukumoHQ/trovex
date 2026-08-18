---
name: review-frontend
description: Domain review checklist for the trovex web/ surface — the Vite/React/TypeScript landing + savings-calculator app AND the Vercel serverless API functions (web/api/*.js) behind it (lead capture, Twenty-CRM mirror, inbound webhook, OG-card/badge generators). Applies to a diff under web/. Ordered highest-weight first: the public serverless surface (secrets, webhook auth, abuse, cache-poisoning, injection) leads; parity/honesty and analytics-privacy follow; typing/build hygiene trail. Each item is a judgment call the build's check-* guards, eslint, tsc, and vitest do NOT already make.
paths: web/, web/api/, web/src/, web/scripts/, web/public/, web/vercel.json
---

# review-frontend — trovex web/ review gate

`web/` is two surfaces in one tree: a **public serverless backend** (`web/api/*.js` — unauthenticated lead capture, a CRM mirror, an inbound webhook, cached OG/badge generators) and a **React landing app** (`web/src` — the savings calculator + analytics). The real judgment risk lives in the serverless half; that's where this checklist leans.

**Scope — CODE, not copy.** This gate reviews plumbing, render, endpoints, config, JSON-LD structure, analytics wiring, and the *structural* honesty of claims (a mock labeled as a mock; a live claim keeping its methodology). The **words** themselves — hero lines, FAQ prose, microcopy — are marketing-owned and pass the fleet's non-author content gate; do not self-grade prose here.

**Already covered by the build gate — do NOT re-flag** (they fail `npm run build` mechanically): `check-brand` (synergix leak), `check-no-client-secrets` (known secret idents + `VITE_*` inlining), `check-pii-openai`, `check-analytics`, `check-voice`, `check-no-blog`, `check-sitemap`, `check-internal-links`, `check-silo-schema`, `check-install-cta`, `eslint`, `tsc -b` / `typecheck:api`, and the `vitest` suite (rate-limit, savings-parity/model/meta, savings-badge PII+CORS, twenty-webhook auth, waitlist). If the only issue is one of those, it's a tooling job. The judgment items below are the ones those guards **can't** make.

Work the branches **in order**. The public-surface security concerns lead; hygiene trails.

---

## 1. Serverless secrets & webhook auth — the sharpest edge

`web/api/*.js` holds RLS-bypass and third-party credentials and one inbound mutation path. `check-no-client-secrets` blocks the *known* secret names from the client bundle; it does not verify a *new* secret is server-only, nor that a webhook actually authenticates.

- **A new server secret is read only in `web/api/`, never in `web/src`, and its name is added to `check-no-client-secrets`' `SECRET_IDENTS`.** Vite inlines every `import.meta.env.VITE_*` into the shipped bundle, so a secret read under a `VITE_` name — or any secret referenced from `src/` — is published to every browser. The guard only knows the idents already in its list; a freshly-introduced secret it's never heard of sails through until it's registered. Because a leaked `SUPABASE_SERVICE_ROLE_KEY` / `TWENTY_API_KEY` / `*_WEBHOOK_SECRET` is a full-write credential in public JS.
- **An inbound webhook verifies the RAW request body, constant-time, and refuses until its secret is set.** `twenty-webhook.js` is trustworthy only on its `?token=`/`x-webhook-secret` paths (both `timingSafeEqual`, length-checked first) and 503s when `TWENTY_WEBHOOK_SECRET` is unset — but its **HMAC path is unreliable**: it re-serializes the *parsed* body (`JSON.stringify(body)`, "matches Twenty's… closely enough") and `readJson` truncates at 65536 bytes, so a signature check can pass on a mismatch or fail on a large valid payload. A change that makes HMAC-over-reserialized-body the *only* auth, or a new webhook that skips the constant-time token check, is a spoofable mutation path into the CRM. Because a forged webhook writes real records.
- **Secret comparison is constant-time.** Webhook/token checks use `timingSafeEqual` (via `safeEqual`, length-guarded), never `===`. A `===` on a secret is a timing oracle. Because the secret is the only thing gating an external mutation.

## 2. Public-endpoint abuse defense

The lead-capture endpoints are **unauthenticated by design** — a honeypot, rate-limit, and strict validation are the *entire* defense. Any weakening is a direct hole.

- **A public POST rate-limits and validates BEFORE it does work, and writes only an explicit allowlist of fields.** `waitlist.js` gates `rateLimited()` ahead of validation, drops honeypot (`company`) hits with a fake 200, caps the body at 4096 bytes, and coerces attribution through a **closed** `ATTRIBUTION_KEYS` allowlist (each value string-coerced, sliced to 64). A new endpoint or field that spreads arbitrary body keys into storage columns, skips the body cap, or does DB work before the rate-limit is an injection/DoS surface on an anonymous write. Because there is no auth behind it — the allowlist *is* the schema boundary.
- **No client-settable value may gate a privileged server side-effect.** `waitlist.js`'s `channel === 'healthcheck'` bypass lets a caller set one attribution field to suppress owner-notify + CRM creation while still persisting a row. Any new client-controlled field that flips server behavior (skip a notification, skip a sync, change routing) is an abuse vector — the client controls it, so treat it as attacker-controlled. Because "one field turns off the alarms" is exactly what an abuser wants.
- **The durable (KV) rate-limit stays the real defense; the in-memory fallback is not one.** `_rate-limit.js` fails **open** — KV unreachable → per-warm-Lambda `Map`, which a distributed flood defeats. A change that removes or bypasses the KV path, or leans on the in-memory fallback as the throttle, leaves anonymous writes effectively uncapped across instances. Because serverless has no shared memory; only the KV window sees the whole flood.

## 3. Host-header → cache poisoning

- **A CDN-cached response must not reflect a request header (`Host`/`X-Forwarded-Host`) into its body without an origin allowlist.** `savings.js` builds its origin from `x-forwarded-host`/`host` and injects it into `og:image`/`og:url` on an `s-maxage=86400` response — a spoofed host poisons the shared cache entry and points every subsequent visitor's share card at an attacker origin. Attribute-escaping (`setMeta`) stops a markup breakout but **not** host substitution. Any new cached endpoint that derives a URL from an inbound header must pin it to a fixed/allowlisted origin. Because one poisoned cache key is served to everyone until it expires.

## 4. XSS / injection / info-disclosure in rendered output

- **New interpolation into a hand-built HTML/SVG/OG string goes through the escape helper.** `src/` is currently clean of `dangerouslySetInnerHTML`/`innerHTML`/`eval`; the SVG/OG builders (`savings/receiptCard.ts` `esc()`, `savings-card.js`, `savings.js` `setMeta`) escape `& < > "` and today only aggregate *numbers* reach them. A new string field (a title, a name, a referrer) concatenated into that markup without the escape helper breaks out of the attribute/element — and a new `dangerouslySetInnerHTML` rendering querystring/external data is a stored/reflected XSS. Because the builders assume their inputs are pre-escaped numerics; a raw string voids that assumption silently.
- **A catch handler never returns an internal error string or stack to the client.** `savings-card.js` currently answers a layout failure with `200 "card unavailable: ${e.message}"` — a new handler that widens this (paths, stack, SQL, upstream error bodies) is information disclosure. Because internal detail on the wire is reconnaissance for an attacker.

## 5. Savings parity & honest numbers — the public claim's integrity

- **The savings math stays byte-parity across its client and server copies.** `Savings.tsx` (client calculator) and `_savings.js` (server OG/badge) are two implementations of one model, locked by `savings-parity.test.js`; the honesty gate (`RECEIPT_MIN_RATIO`, and no-input → a generic `~60%` card, never the computed `~64%`) keeps a share card from overstating. A change to one copy without the other diverges the shared receipt from what the user saw, and a change that renders a *computed* figure for empty input breaks the honesty gate. Because a public savings receipt that claims more than was measured is a credibility defect on a shareable artifact — verify the parity test still pins both sides.
- **Illustrative figures stay visibly illustrative; the load-bearing claim keeps its methodology.** The hero dashboard (`App.tsx` `HeroWindow`: `saved=1,240,000`, `docs=842`, `canon=96%`…) is a stylized *mock*, and the real public claim ships *with* its method ("~60% fewer tokens… median 69%, range 41–81%, n=26, LLM-judged"). A change that presents fabricated dashboard numbers as live/measured data, or strips the methodology from the ~60% claim, crosses from illustration into a false metric. Because the honest-measurement framing is the product's credibility; a bare `Nx`/`%` with no basis is the thing to catch (the *wording* is marketing-gated, but "is this presented as real data" is a code/structure call).

## 6. Analytics privacy

- **A new `track()` event carries no PII and no free-form value.** `analytics.ts` is no-PII *by construction*: referrer reduced to host (`referrerHost()`), closed `GeoSource`/`Channel` enums, UTM values sliced to 64, savings ratio bucketed (`pctBucket`), email never in any event, and `track()` is a no-op unless `window.plausible` exists. A new event that passes email, a raw referrer/URL, or an unbounded string breaks the contract the whole design upholds. Because the analytics premise is "measure without collecting PII" — one raw field voids it, and it ships to a third party.
- **Instrument each event once.** `trackSectionViews()` is currently mounted twice (`App.tsx` effect + `<SectionViews/>` in `main.tsx`), double-firing `section_viewed`; a new double-mounted observer/effect inflates the metric. Lower weight (data quality, not a breach) — but flag a duplicated mount because doubled counts quietly corrupt every funnel read off them.

## 7. Typing & build-gate hygiene (trailing)

- **Manually verify null/shape handling in `web/api/` — the serverless layer is only loosely typed.** `tsconfig.api.json` runs `strict:false` / `noImplicitAny:false`, so the *most* security-sensitive code (lead capture, webhook, CRM) is the *least* type-checked; `tsc` will not catch a missing null-guard or a wrong input shape on that path. A reviewer has to make the check the compiler isn't. Because an unguarded `undefined` on the anonymous-write path is a 500 at best and a bypass at worst.
- **A new public surface extends the guard that's meant to cover it.** The build chain is only as complete as its inputs: a new secret ident belongs in `check-no-client-secrets`, a new HTML page needs the Plausible loader (`check-analytics`) and a sitemap entry (`check-sitemap`), a new FastAPI-served template dir needs to be in `check-brand`'s scan set (the reason `../src/trovex/templates` was added after a live leak). Adding the surface without extending the guard means the guard passes it *silently*. Because a green build then certifies coverage it doesn't actually have.

---

## Verdict shape (for the Q&A gate)

Rank by branch order — a §1 secret/webhook hole or a §2 abuse bypass outranks a §6 double-count. For each finding name the `web/api/…:line` or `web/src/…:line`, the invariant broken, and the concrete exploit or silent corruption it enables (leaked service key / forged CRM write / poisoned cache / reflected string / overstated receipt / PII in an event). Note explicitly when a diff touches human-facing **copy** — that half routes to the marketing non-author gate, not this one.
