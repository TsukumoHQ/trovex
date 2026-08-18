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
