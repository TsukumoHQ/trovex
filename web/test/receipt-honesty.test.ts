/**
 * Honesty-rule guard for the savings receipt view.
 *
 * The receipt's whole value is that its number is trustworthy, so the rules that
 * qualify it (CTO brief) are pinned here, not just asserted by eye in JSX:
 *   - precision=null  → lead with RAW saved, carry a caveat, NEVER surface
 *     saved_at_precision;
 *   - precision set   → lead with saved_at_precision, raw is secondary, no caveat;
 *   - the backend caveat string is preferred over the local fallback (SSOT).
 */
import { describe, expect, it } from 'vitest'
import { type SavingsTotals, resolveHeadline, showAtPrecision } from '../src/receipt/api'
import { humanTokens, pct, relativeTime, tokenizerLabel } from '../src/receipt/format'

const base: SavingsTotals = {
  queries: 100,
  would_have_read: 1_000_000,
  actual_read: 400_000,
  response_tokens: 20_000,
  saved: 600_000,
  ratio: 0.6,
  tokenizer: 'o200k_base',
  precision: null,
  precision_measured_at: null,
  saved_at_precision: null,
  assumption: 'top-3 triage baseline',
  caveat: null,
}

describe('resolveHeadline — honesty rule #2', () => {
  it('precision=null leads with raw saved and carries a caveat, never at-precision', () => {
    const h = resolveHeadline({ ...base, precision: null, saved_at_precision: null })
    expect(h.verified).toBe(false)
    expect(h.saved).toBe(600_000) // raw
    expect(h.secondary).toBeNull()
    expect(h.caveat).toBeTruthy()
  })

  it('prefers the backend-authored caveat string (SSOT)', () => {
    const h = resolveHeadline({ ...base, caveat: 'BACKEND SAYS UNVERIFIED' })
    expect(h.caveat).toBe('BACKEND SAYS UNVERIFIED')
  })

  it('precision set leads with at-precision, raw is secondary, no caveat', () => {
    const h = resolveHeadline({
      ...base,
      precision: 0.82,
      precision_measured_at: 1_700_000_000,
      saved_at_precision: 492_000,
    })
    expect(h.verified).toBe(true)
    expect(h.saved).toBe(492_000) // at-precision leads
    expect(h.secondary?.saved).toBe(600_000) // raw demoted
    expect(h.caveat).toBeNull()
  })

  it('at-precision rows are gated on the run precision', () => {
    expect(showAtPrecision({ ...base, precision: null })).toBe(false)
    expect(showAtPrecision({ ...base, precision: 0.9 })).toBe(true)
  })
})

describe('format', () => {
  it('humanTokens', () => {
    expect(humanTokens(0)).toBe('0')
    expect(humanTokens(-5)).toBe('0')
    expect(humanTokens(950)).toBe('950')
    expect(humanTokens(1500)).toBe('1.5k')
    expect(humanTokens(2_000_000)).toBe('2M')
    expect(humanTokens(3_400_000_000)).toBe('3.4B')
  })

  it('pct rounds and tolerates junk', () => {
    expect(pct(0.6)).toBe(60)
    expect(pct(Number.NaN)).toBe(0)
  })

  it('tokenizerLabel flags the chars/4 fallback as approximate', () => {
    expect(tokenizerLabel('o200k_base')).toBe('o200k_base')
    expect(tokenizerLabel('chars/4')).toMatch(/approximate/)
    expect(tokenizerLabel('')).toBe('unknown tokenizer')
  })

  it('relativeTime buckets from a fixed now', () => {
    const now = 1_700_000_000_000 // ms
    const nowS = now / 1000
    expect(relativeTime(nowS - 10, now)).toBe('just now')
    expect(relativeTime(nowS - 120, now)).toBe('2m ago')
    expect(relativeTime(nowS - 7200, now)).toBe('2h ago')
    expect(relativeTime(0, now)).toBe('—')
  })
})
