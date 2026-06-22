/**
 * Drift guard for the savings triple-mirror.
 *
 * The model lives in three places by necessity (different runtimes):
 *   - web/src/savings/Savings.tsx  — the client calculator
 *   - web/api/_savings.js          — the server mirror (OG card + meta)
 *   - src/trovex/savings.py        — the product's own number
 *
 * Nothing at runtime keeps them in lockstep, so this test does: it parses the
 * constants out of Savings.tsx and asserts the server mirror matches. If someone
 * changes a default / the pointer size / the honesty gate in one file and not the
 * other, a shared link would show a different number than the calculator — this
 * fails the build before that ships.
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { BOUNDS as BOUNDS_DOC, DEFAULTS, POINTER_TOKENS, QS, RECEIPT_MIN_RATIO } from '../api/_savings.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const TSX = readFileSync(join(HERE, '../src/savings/Savings.tsx'), 'utf8')

const num = (re) => {
  const m = TSX.match(re)
  if (!m) throw new Error(`Savings.tsx parity: pattern not found: ${re}`)
  return Number(m[1])
}

describe('Savings.tsx ↔ api/_savings.js parity', () => {
  it('shares the same pointer size and honesty gate', () => {
    expect(num(/POINTER_TOKENS\s*=\s*(\d+)/)).toBe(POINTER_TOKENS)
    expect(num(/RECEIPT_MIN_RATIO\s*=\s*([\d.]+)/)).toBe(RECEIPT_MIN_RATIO)
  })

  it('shares the same defaults', () => {
    for (const [field, val] of Object.entries(DEFAULTS)) {
      expect(num(new RegExp(`${field}:\\s*([\\d.]+)`))).toBe(val)
    }
  })

  it('shares the same querystring keys', () => {
    for (const [field, key] of Object.entries(QS)) {
      const m = TSX.match(new RegExp(`${field}:\\s*'([a-z])'`))
      expect(m && m[1]).toBe(key)
    }
  })

  it('shares the same input bounds', () => {
    // Savings.tsx: num('field', DEFAULTS.field, lo, hi)
    for (const [field, [lo, hi]] of Object.entries(BOUNDS_DOC)) {
      const m = TSX.match(new RegExp(`num\\('${field}',[^,]+,\\s*([\\d.]+),\\s*([\\d.]+)\\)`))
      expect(m, `bounds for ${field}`).toBeTruthy()
      expect([Number(m[1]), Number(m[2])]).toEqual([lo, hi])
    }
  })
})
