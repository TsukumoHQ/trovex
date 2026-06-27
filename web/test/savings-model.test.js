/**
 * The savings model is the number trovex puts its name on — on the calculator,
 * the shared receipt, and the OG card. These golden vectors pin the formula so a
 * refactor can't silently shift a published figure. See api/_savings.js.
 */
import { describe, expect, it } from 'vitest'
import {
  DEFAULTS,
  RECEIPT_MIN_RATIO,
  compute,
  hasInputs,
  humanTokens,
  isShareworthy,
  money,
  pct,
  readInputs,
} from '../api/_savings.js'

const params = (s) => new URLSearchParams(s)

describe('compute', () => {
  it('matches the model on the defaults (golden vector)', () => {
    const m = compute(DEFAULTS)
    // wouldHaveRead = 3 * 1200 = 3600 ; trovexRead = 1200 + 80 = 1280
    expect(m.wouldHaveRead).toBe(3600)
    expect(m.trovexRead).toBe(1280)
    expect(m.savedPerLookup).toBe(2320) // 3600 - 1280
    expect(m.ratio).toBeCloseTo(0.6444, 4)
    expect(m.lookupsPerDay).toBe(144) // 12 * 4 * 3
    expect(m.tokensPerMonth).toBe(2320 * 144 * 30) // 10,022,400
    expect(m.dollarsPerMonth).toBeCloseTo((m.tokensPerMonth / 1e6) * 3, 6)
  })

  it('never reports a negative saving (floored at 0)', () => {
    // candidates=1 → trovex reads MORE than the single doc (pointer overhead).
    const m = compute({ ...DEFAULTS, candidates: 1, avgDocTokens: 1000 })
    expect(m.savedPerLookup).toBe(0)
    expect(m.ratio).toBe(0)
    expect(m.tokensPerMonth).toBe(0)
    expect(m.dollarsPerMonth).toBe(0)
  })

  it('avoids div-by-zero when there is nothing to read', () => {
    const m = compute({ ...DEFAULTS, candidates: 1, avgDocTokens: 50 })
    expect(Number.isFinite(m.ratio)).toBe(true)
  })
})

describe('readInputs', () => {
  it('falls back to defaults when a field is absent', () => {
    expect(readInputs(params(''))).toEqual(DEFAULTS)
  })

  it('clamps out-of-range inputs to the UI bounds', () => {
    const inp = readInputs(params('a=9999&c=99&p=-5&d=10'))
    expect(inp.agents).toBe(500) // hi clamp
    expect(inp.candidates).toBe(10) // hi clamp
    expect(inp.price).toBe(0) // lo clamp
    expect(inp.avgDocTokens).toBe(50) // lo clamp
  })

  it('ignores non-numeric junk and uses the default', () => {
    expect(readInputs(params('a=abc')).agents).toBe(DEFAULTS.agents)
  })
})

describe('hasInputs', () => {
  it('is false for the bare page, true once any field is present', () => {
    expect(hasInputs(params(''))).toBe(false)
    expect(hasInputs(params('utm_source=x'))).toBe(false) // not a calculator field
    expect(hasInputs(params('a=3'))).toBe(true)
  })
})

describe('OG card honesty gate (no-input default must not overstate)', () => {
  // The savings-card handler builds: m = hasInputs(params) ? compute(readInputs(params)) : null.
  // A bare og:image (the /savings or /audit card with no querystring) → m = null → the
  // generic "~60%" claim, NOT the default scenario — which computes ~64%, above our
  // conservative public floor. The real figure shows only when the link carries inputs.
  it('a no-input card falls back to the generic claim, never the ~64% default scenario', () => {
    expect(hasInputs(params(''))).toBe(false) // → card(null) → headline "~60%"
    expect(pct(compute(readInputs(params(''))))).toBeGreaterThan(60) // why we must not render it bare
  })
  it("a shared link with the sharer's inputs shows their real, shareworthy number", () => {
    expect(hasInputs(params('c=3&d=1200'))).toBe(true)
    expect(isShareworthy(compute(readInputs(params('c=3&d=1200'))))).toBe(true)
  })
})

describe('isShareworthy (honesty gate)', () => {
  it('blocks a receipt below the ratio floor', () => {
    const weak = compute({ ...DEFAULTS, candidates: 2, avgDocTokens: 100 })
    expect(weak.ratio).toBeLessThan(RECEIPT_MIN_RATIO)
    expect(isShareworthy(weak)).toBe(false)
  })

  it('allows a receipt for a healthy saving', () => {
    expect(isShareworthy(compute(DEFAULTS))).toBe(true)
  })
})

describe('formatters', () => {
  it('humanTokens scales and trims trailing .0', () => {
    expect(humanTokens(999)).toBe('999')
    expect(humanTokens(1500)).toBe('1.5k')
    expect(humanTokens(2_000_000)).toBe('2M')
    expect(humanTokens(3_400_000_000)).toBe('3.4B')
  })

  it('money formats by magnitude', () => {
    expect(money(5)).toBe('$5.0')
    expect(money(42)).toBe('$42')
    expect(money(263)).toBe('$263')
    expect(money(1500)).toBe('$1,500')
  })

  it('pct rounds the ratio', () => {
    expect(pct(compute(DEFAULTS))).toBe(64)
  })
})
