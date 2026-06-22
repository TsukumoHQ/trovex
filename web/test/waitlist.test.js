/**
 * Waitlist capture is the one route that touches PII (an email) and writes to a
 * backend with a service-role key. These tests pin the gate logic that runs
 * BEFORE any storage: method allow, honeypot, email validation, and the honest
 * 503 when no backend is wired (no env in CI → that's the path under test).
 * The storage backends themselves need live services and are out of scope here.
 * See api/waitlist.js.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import handler from '../api/waitlist.js'

// Minimal Vercel-style req/res doubles. Passing `body` as an object makes
// readJson resolve synchronously (no stream).
function mkReq({ method = 'POST', body = {}, headers = {}, ip = '198.51.100.1' } = {}) {
  return { method, body, headers, socket: { remoteAddress: ip } }
}
function mkRes() {
  const res = { _status: 0, _json: null, _headers: {} }
  res.setHeader = (k, v) => {
    res._headers[k] = v
  }
  res.status = (c) => {
    res._status = c
    return res
  }
  res.json = (o) => {
    res._json = o
    return res
  }
  return res
}

// Ensure no storage backend is configured for the default-path tests.
const STORAGE_ENV = [
  'SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY',
  'WAITLIST_KV_REST_API_URL', 'WAITLIST_KV_REST_API_TOKEN',
  'KV_REST_API_URL', 'KV_REST_API_TOKEN',
  'WAITLIST_GITHUB_TOKEN', 'WAITLIST_GITHUB_REPO',
]
beforeEach(() => {
  for (const k of STORAGE_ENV) delete process.env[k]
  vi.restoreAllMocks()
})

describe('POST /api/waitlist — gate logic', () => {
  it('rejects non-POST with 405 + Allow header', async () => {
    const res = mkRes()
    await handler(mkReq({ method: 'GET' }), res)
    expect(res._status).toBe(405)
    expect(res._headers.Allow).toBe('POST')
  })

  it('honeypot hit → fake 200, stores nothing, makes no network call', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const res = mkRes()
    await handler(mkReq({ body: { email: 'a@b.co', company: 'bot inc' }, ip: '198.51.100.2' }), res)
    expect(res._status).toBe(200)
    expect(res._json).toEqual({ ok: true })
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('invalid email → 400, before any storage', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const res = mkRes()
    await handler(mkReq({ body: { email: 'not-an-email' }, ip: '198.51.100.3' }), res)
    expect(res._status).toBe(400)
    expect(res._json.error).toBe('invalid_email')
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('over-long email → 400', async () => {
    const res = mkRes()
    const email = `${'x'.repeat(250)}@b.co`
    await handler(mkReq({ body: { email }, ip: '198.51.100.4' }), res)
    expect(res._status).toBe(400)
  })

  it('valid email, no backend wired → honest 503 not_configured', async () => {
    const res = mkRes()
    await handler(mkReq({ body: { email: 'dev@example.com' }, ip: '198.51.100.5' }), res)
    expect(res._status).toBe(503)
    expect(res._json.error).toBe('not_configured')
  })

  it('floods are throttled to 429 within the window', async () => {
    const ip = '198.51.100.99'
    let last
    for (let i = 0; i < 7; i++) {
      last = mkRes()
      await handler(mkReq({ body: { email: 'flood@example.com' }, ip }), last)
    }
    expect(last._status).toBe(429)
    expect(last._json.error).toBe('rate_limited')
  })

  it('never echoes the submitted email back to the client', async () => {
    const res = mkRes()
    await handler(mkReq({ body: { email: 'secret@example.com' }, ip: '198.51.100.6' }), res)
    expect(JSON.stringify(res._json)).not.toContain('secret@example.com')
  })
})
