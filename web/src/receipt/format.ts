/** Display formatting for the savings receipt. Pure, so it's unit-tested. */

export function humanTokens(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '0'
  if (n >= 1e9) return `${(n / 1e9).toFixed(1).replace(/\.0$/, '')}B`
  if (n >= 1e6) return `${(n / 1e6).toFixed(1).replace(/\.0$/, '')}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1).replace(/\.0$/, '')}k`
  return String(Math.round(n))
}

export function pct(ratio: number): number {
  if (!Number.isFinite(ratio)) return 0
  return Math.round(ratio * 100)
}

/**
 * Format a USD saving. Under-claims by construction: sub-cent rounds to $0.00
 * (never invents a number), cents shown below $10 where they matter, whole
 * comma-grouped dollars above. No "$0" hiding a real fraction, no inflation.
 */
export function money(usd: number): string {
  if (!Number.isFinite(usd) || usd <= 0) return '$0.00'
  if (usd < 10) return `$${usd.toFixed(2)}`
  if (usd < 1000) return `$${Math.round(usd)}`
  return `$${Math.round(usd).toLocaleString('en-US')}`
}

/** One-line provenance for the $ figure: which rate priced it. */
export function pricingNote(p: { model: string; input_per_mtok: number; source: string }): string {
  const rate = `$${p.input_per_mtok.toFixed(2)}/M input tokens`
  return `priced at ${rate} · ${p.model} (${p.source})`
}

/**
 * The $ layer is strictly additive. A payload only shows dollars when it carries
 * BOTH a finite `saved_usd` and a `pricing` block; otherwise the UI renders the
 * token figure alone rather than fake a $0.00 or crash `pricingNote` on an
 * undefined block. Shared by every $-rendering site so the guard can't drift —
 * a 200 response with a malformed/partial committed JSON never blanks the page.
 */
export function hasDollarFigure(x: {
  saved_usd?: number
  pricing?: { input_per_mtok: number } | null
}): boolean {
  return Number.isFinite(x.saved_usd) && x.pricing != null
}

/** o200k_base → shown as-is; the "chars/4" fallback labelled as an approximation. */
export function tokenizerLabel(tokenizer: string): string {
  const t = (tokenizer || '').trim()
  if (!t) return 'unknown tokenizer'
  if (/chars?\s*\/\s*4|char\b|approx/i.test(t)) return `${t} (approximate)`
  return t
}

/** Relative time from an epoch-seconds timestamp (server uses seconds). */
export function relativeTime(epochSeconds: number, nowMs = Date.now()): string {
  if (!Number.isFinite(epochSeconds) || epochSeconds <= 0) return '—'
  const secs = Math.max(0, nowMs / 1000 - epochSeconds)
  if (secs < 60) return 'just now'
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}
