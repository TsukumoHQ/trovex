/**
 * Rate-limit fallback (no KV configured → in-memory sliding window). The durable
 * KV path needs a live backend; here we pin the local fail-safe behaviour that
 * protects the form when KV is absent. See api/_rate-limit.js.
 */
import { describe, expect, it } from 'vitest'
import { rateLimited } from '../api/_rate-limit.js'

describe('rateLimited (in-memory fallback)', () => {
  it('blocks only after the cap is exceeded within the window', async () => {
    const ip = '203.0.113.10' // unique per test → own mem bucket
    const hit = () => rateLimited({ scope: 'test-cap', ip, max: 3, windowMs: 60_000 })
    expect(await hit()).toBe(false) // 1
    expect(await hit()).toBe(false) // 2
    expect(await hit()).toBe(false) // 3 (== max, not over)
    expect(await hit()).toBe(true) // 4 → over
  })

  it('does not block when there is no client identifier', async () => {
    expect(await rateLimited({ scope: 'test-noid', max: 1 })).toBe(false)
    expect(await rateLimited({ scope: 'test-noid', max: 1 })).toBe(false)
  })

  it('keys are independent per identifier', async () => {
    const opts = (ip) => ({ scope: 'test-iso', ip, max: 1, windowMs: 60_000 })
    expect(await rateLimited(opts('203.0.113.20'))).toBe(false)
    expect(await rateLimited(opts('203.0.113.21'))).toBe(false) // different ip, fresh count
    expect(await rateLimited(opts('203.0.113.20'))).toBe(true) // first ip now over
  })
})
