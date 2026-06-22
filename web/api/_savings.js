/**
 * Shared savings math for the /savings OG share-card pipeline.
 *
 * This is the SERVER mirror of web/src/savings/Savings.tsx — same model, same
 * defaults, same honesty gate — so a shared link's OG card shows EXACTLY the
 * number the calculator showed the sharer. Keep the two in lockstep: if the
 * calculator's model changes, change it here too (both trace to src/trovex/savings.py).
 *
 * No PII, ever: the only inputs are the six numeric calculator fields from the
 * querystring (clamped to the same bounds as the UI). Nothing here reads a header,
 * a cookie, or anything user-identifying.
 */

export const POINTER_TOKENS = 80 // the trovex() pointer response size (small, constant)

// Honesty gate: below this ratio the saving isn't worth a receipt / a shared card.
// Mirrors RECEIPT_MIN_RATIO in Savings.tsx.
export const RECEIPT_MIN_RATIO = 0.2

// Short querystring keys ↔ input fields (must match QS in Savings.tsx).
export const QS = {
  agents: 'a',
  lookupsPerSession: 'l',
  sessionsPerDay: 's',
  candidates: 'c',
  avgDocTokens: 'd',
  price: 'p',
}

export const DEFAULTS = {
  agents: 3,
  lookupsPerSession: 12,
  sessionsPerDay: 4,
  candidates: 3,
  avgDocTokens: 1200,
  price: 3,
}

// [lo, hi] bounds per field — identical to the <Field> min/max in Savings.tsx.
// Exported (BOUNDS_DOC) so the parity test can assert lockstep with the calculator.
export const BOUNDS = {
  agents: [1, 500],
  lookupsPerSession: [1, 1000],
  sessionsPerDay: [1, 100],
  candidates: [1, 10],
  avgDocTokens: [50, 20000],
  price: [0, 100],
}

const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n))

/** True if the querystring carries at least one calculator field (i.e. it's a
 *  shared result, not the bare /savings page). */
export function hasInputs(params) {
  return Object.values(QS).some((k) => params.get(k) != null)
}

/** Parse + clamp the six inputs from a URLSearchParams. Missing/invalid → default. */
export function readInputs(params) {
  const out = {}
  for (const field of Object.keys(DEFAULTS)) {
    const [lo, hi] = BOUNDS[field]
    const raw = params.get(QS[field])
    const v = raw == null ? DEFAULTS[field] : Number(raw)
    out[field] = Number.isFinite(v) ? clamp(v, lo, hi) : DEFAULTS[field]
  }
  return out
}

/** The savings model (mirror of the useMemo in Savings.tsx). */
export function compute(inp) {
  const wouldHaveRead = inp.candidates * inp.avgDocTokens
  const trovexRead = inp.avgDocTokens + POINTER_TOKENS
  const savedPerLookup = Math.max(0, wouldHaveRead - trovexRead)
  const ratio = wouldHaveRead > 0 ? savedPerLookup / wouldHaveRead : 0
  const lookupsPerDay = inp.lookupsPerSession * inp.sessionsPerDay * inp.agents
  const tokensPerDay = savedPerLookup * lookupsPerDay
  const tokensPerMonth = tokensPerDay * 30
  const dollarsPerMonth = (tokensPerMonth / 1e6) * inp.price
  return { wouldHaveRead, trovexRead, savedPerLookup, ratio, lookupsPerDay, tokensPerMonth, dollarsPerMonth }
}

/** The same gate the page uses to decide whether to show the shareable receipt. */
export function isShareworthy(m) {
  return m.ratio >= RECEIPT_MIN_RATIO && m.tokensPerMonth > 0
}

// ── formatting (mirror of humanTokens / money in Savings.tsx) ────────────────

export function humanTokens(n) {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1).replace(/\.0$/, '')}B`
  if (n >= 1e6) return `${(n / 1e6).toFixed(1).replace(/\.0$/, '')}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1).replace(/\.0$/, '')}k`
  return String(Math.round(n))
}

export function money(n) {
  if (n >= 1000) return `$${Math.round(n).toLocaleString('en-US')}`
  if (n >= 100) return `$${Math.round(n)}`
  return `$${n.toFixed(n < 10 ? 1 : 0)}`
}

export function pct(m) {
  return Math.round(m.ratio * 100)
}
