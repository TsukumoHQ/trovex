/**
 * /api/savings-badge — the dynamic shields.io endpoint badge (TSU-48).
 * Pins the shields endpoint contract, the honesty gate (no fabricated number
 * below the receipt threshold), and the no-PII guarantee (only the 6 numeric
 * inputs reach the math). See api/savings-badge.js + _savings.js.
 */
import { describe, expect, it } from 'vitest'

import handler, { badge } from '../api/savings-badge.js'

const qs = (s) => new URLSearchParams(s)

function mockRes() {
  return {
    statusCode: 0,
    headers: {},
    body: undefined,
    setHeader(k, v) {
      this.headers[k.toLowerCase()] = v
    },
    status(c) {
      this.statusCode = c
      return this
    },
    send(b) {
      this.body = b
      return this
    },
  }
}

describe('savings-badge endpoint', () => {
  it('worthy inputs → live shields endpoint payload with an "(est.)" %', () => {
    // defaults (c=3, d=1200) clear the gate: ratio ≈ 0.64.
    const b = badge(qs('a=3&l=12&s=4&c=3&d=1200&p=3'))
    expect(b.schemaVersion).toBe(1)
    expect(b.label).toBe('trovex')
    expect(b.message).toMatch(/^~\d+% fewer tokens \(est\.\)$/)
    expect(b.color).toBe('22c55e')
  })

  it('below the honesty gate → neutral message, NO fabricated number', () => {
    // c=1 → would-have-read (1200) < trovex read (1280) → ratio 0, not shareworthy.
    const b = badge(qs('a=3&l=12&s=4&c=1&d=1200&p=3'))
    expect(b.message).toBe('estimate your token savings')
    expect(b.message).not.toMatch(/\d/) // no number invented for a non-saving
    expect(b.color).toBe('9aa6b8')
  })

  it('no inputs → still falls back to the model defaults, never crashes', () => {
    const b = badge(qs(''))
    expect(b.schemaVersion).toBe(1)
    expect(typeof b.message).toBe('string')
  })

  it('message carries no PII even if junk PII-shaped params are passed', () => {
    // only the 6 numeric keys are read; extra params are ignored by readInputs.
    const b = badge(qs('a=3&l=12&s=4&c=3&d=1200&p=3&repo=secret/path&user=alice&q=how+do+we+deploy'))
    expect(b.message).not.toContain('secret')
    expect(b.message).not.toContain('alice')
    expect(b.message).not.toContain('deploy')
  })

  it('handler sets the shields content-type, CORS, and a 200', () => {
    const res = mockRes()
    handler({ url: '/api/savings-badge?a=3&l=12&s=4&c=3&d=1200&p=3' }, res)
    expect(res.statusCode).toBe(200)
    expect(res.headers['content-type']).toMatch(/application\/json/)
    expect(res.headers['access-control-allow-origin']).toBe('*')
    const parsed = JSON.parse(res.body)
    expect(parsed.schemaVersion).toBe(1)
  })

  it('handler does not throw on a malformed url', () => {
    const res = mockRes()
    expect(() => handler({ url: undefined }, res)).not.toThrow()
    expect(res.statusCode).toBe(200)
  })
})
