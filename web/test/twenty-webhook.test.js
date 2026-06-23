/**
 * The Twenty webhook is an inbound endpoint that pings the owner on a new consulting
 * lead. These tests pin the AUTH gate that runs before any side-effect: method allow,
 * the honest 503 when no secret is wired, 401 on a bad/absent secret, and 200 on a
 * valid secret (query token OR x-webhook-secret header). The owner-notify + KV cache
 * need live services and are out of scope here. See api/twenty-webhook.js.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import handler from '../api/twenty-webhook.js'

function mkReq({ method = 'POST', body = {}, headers = {}, url = '/api/twenty-webhook' } = {}) {
  return { method, body, headers, url }
}
function mkRes() {
  const res = { _status: 0, _json: null, _headers: {} }
  res.setHeader = (k, v) => { res._headers[k] = v }
  res.status = (c) => { res._status = c; return res }
  res.json = (o) => { res._json = o; return res }
  return res
}

const SECRET = 'test-secret-abc123'
// Notify/KV env stay UNSET so side-effects are no-ops (best-effort, no network in CI).
const SIDE_EFFECT_ENV = [
  'NOTIFY_WEBHOOK_URL', 'RESEND_API_KEY', 'NOTIFY_EMAIL_TO',
  'WAITLIST_KV_REST_API_URL', 'WAITLIST_KV_REST_API_TOKEN', 'KV_REST_API_URL', 'KV_REST_API_TOKEN',
]
beforeEach(() => {
  for (const k of SIDE_EFFECT_ENV) delete process.env[k]
  process.env.TWENTY_WEBHOOK_SECRET = SECRET
  vi.restoreAllMocks()
})
afterEach(() => { delete process.env.TWENTY_WEBHOOK_SECRET })

describe('POST /api/twenty-webhook — auth gate', () => {
  it('rejects non-POST with 405 + Allow header', async () => {
    const res = mkRes()
    await handler(mkReq({ method: 'GET' }), res)
    expect(res._status).toBe(405)
    expect(res._headers.Allow).toBe('POST')
  })

  it('no secret configured → honest 503 not_configured, no side-effect', async () => {
    delete process.env.TWENTY_WEBHOOK_SECRET
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const res = mkRes()
    await handler(mkReq({ url: '/api/twenty-webhook?token=anything', body: { eventName: 'person.created' } }), res)
    expect(res._status).toBe(503)
    expect(res._json.error).toBe('not_configured')
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('wrong token → 401 unauthorized, no side-effect', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const res = mkRes()
    await handler(mkReq({ url: '/api/twenty-webhook?token=wrong', body: { eventName: 'person.created' } }), res)
    expect(res._status).toBe(401)
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('absent token → 401', async () => {
    const res = mkRes()
    await handler(mkReq({ body: { eventName: 'person.created' } }), res)
    expect(res._status).toBe(401)
  })

  it('valid query token → 200 ok', async () => {
    const res = mkRes()
    await handler(mkReq({
      url: `/api/twenty-webhook?token=${SECRET}`,
      body: { eventName: 'person.created', record: { name: { firstName: 'Dev' }, emails: { primaryEmail: 'a@b.co' } } },
    }), res)
    expect(res._status).toBe(200)
    expect(res._json).toEqual({ ok: true })
  })

  it('valid x-webhook-secret header → 200 ok', async () => {
    const res = mkRes()
    await handler(mkReq({
      headers: { 'x-webhook-secret': SECRET },
      body: { eventName: 'opportunity.created', record: { name: 'Big deal', stage: 'SCREENING' } },
    }), res)
    expect(res._status).toBe(200)
  })

  it('authorized but unknown event → 200 ack, no throw', async () => {
    const res = mkRes()
    await handler(mkReq({ url: `/api/twenty-webhook?token=${SECRET}`, body: { eventName: 'note.created' } }), res)
    expect(res._status).toBe(200)
  })

  it('never echoes a lead email back to the client', async () => {
    const res = mkRes()
    await handler(mkReq({
      url: `/api/twenty-webhook?token=${SECRET}`,
      body: { eventName: 'person.created', record: { emails: { primaryEmail: 'secret@example.com' } } },
    }), res)
    expect(JSON.stringify(res._json)).not.toContain('secret@example.com')
  })
})
