/**
 * Twenty CRM webhook sink — near-real-time owner alert on a new consulting lead.
 *
 * Twenty fires `person.created` / `opportunity.created` to this endpoint (owner enables
 * the webhook in Twenty settings, or POST /rest/webhooks with the workspace key, pointing
 * targetUrl at https://trovex.dev/api/twenty-webhook?token=<TWENTY_WEBHOOK_SECRET>).
 * We (1) verify the request is really from our webhook, (2) ping the owner (notifyOwner
 * pattern), (3) best-effort cache the event for the north-star dashboard. Spec: trovex
 * doc 1dbad3e8 §Webhooks. Until this is live the scoreboard polls Twenty REST each run.
 *
 * Server-side only, env-gated:
 *   - TWENTY_WEBHOOK_SECRET — required; shared secret. The endpoint is a no-op (503) until
 *     it is set, so nothing fires accidentally. Twenty lets you set an arbitrary targetUrl,
 *     so the reliable, provider-agnostic check is a secret: matched against the `token` query
 *     param OR an `x-webhook-secret` header (timing-safe). NEVER in client code / git / logs.
 *   - WAITLIST_KV_REST_API_URL + _TOKEN (or KV_REST_API_*) — optional; if present, each event
 *     is LPUSH'd onto `twenty_events` for the dashboard. Absent → caching is skipped.
 *
 * Privacy: a lead's name/email reaches only the OWNER's own notify channel (the point) — it
 * is never written to logs or error traces. We always answer 2xx after auth so Twenty does
 * not retry-storm; a downstream failure is swallowed, never surfaced.
 */

import { createHmac, timingSafeEqual } from 'node:crypto'
import { notifyOwner } from './_notify.js'

function readJson(req) {
  if (req.body && typeof req.body === 'object') return Promise.resolve(req.body)
  return new Promise((resolve) => {
    let raw = ''
    req.on('data', (c) => {
      raw += c
      if (raw.length > 65536) raw = raw.slice(0, 65536) // cap; Twenty records are small
    })
    req.on('end', () => {
      try { resolve(JSON.parse(raw || '{}')) } catch { resolve({}) }
    })
    req.on('error', () => resolve({}))
  })
}

// Constant-time string compare that never throws on a length mismatch.
function safeEqual(a, b) {
  const ab = Buffer.from(String(a))
  const bb = Buffer.from(String(b))
  if (ab.length !== bb.length) return false
  return timingSafeEqual(ab, bb)
}

// True iff the request carries our shared secret (query token or x-webhook-secret header).
// Also accepts a Twenty HMAC-SHA256 signature header when the body is signed with the same
// secret — so it works whether the owner appends ?token= or configures a Twenty signing key.
function authorized(req, rawForHmac) {
  const secret = process.env.TWENTY_WEBHOOK_SECRET
  if (!secret) return null // not configured

  let token = ''
  try { token = new URL(req.url, 'http://x').searchParams.get('token') || '' } catch { /* ignore */ }
  if (token && safeEqual(token, secret)) return true

  const header = req.headers['x-webhook-secret']
  if (header && safeEqual(header, secret)) return true

  const sig = req.headers['x-twenty-webhook-signature'] || req.headers['x-signature']
  if (sig && rawForHmac) {
    const digest = createHmac('sha256', secret).update(rawForHmac).digest('hex')
    if (safeEqual(sig, digest)) return true
  }
  return false
}

// Pull the event name + record out of Twenty's payload, defensively across shapes:
//   { eventName: 'person.created', record: {...} }  (current)
//   { event: '...', record: { after: {...} } }      (alt / older)
function parseEvent(body) {
  const eventName = String(body.eventName || body.event || body.name || '').toLowerCase()
  const record = body.record?.after || body.record || body.objectRecord || {}
  return { eventName, record }
}

function personFields(r) {
  const first = r?.name?.firstName || ''
  const last = r?.name?.lastName || ''
  const name = `${first} ${last}`.trim() || undefined
  const email = r?.emails?.primaryEmail || r?.email || undefined
  return { lead: name, email, role: r?.jobTitle || undefined, company: r?.company?.name || undefined }
}

function opportunityFields(r) {
  const name = r?.name || undefined
  const stage = r?.stage || undefined
  let amount
  const micros = r?.amount?.amountMicros
  if (typeof micros === 'number') {
    const cur = r?.amount?.currencyCode || ''
    amount = `${(micros / 1_000_000).toLocaleString('en-US')} ${cur}`.trim()
  }
  return { opportunity: name, stage, amount }
}

// Best-effort dashboard cache. Stores a TRIMMED, PII-light event (no email) onto a KV list.
// Env-gated + swallows its own errors; never blocks the webhook ack.
async function cacheEvent(eventName, record) {
  const url = process.env.WAITLIST_KV_REST_API_URL || process.env.KV_REST_API_URL
  const token = process.env.WAITLIST_KV_REST_API_TOKEN || process.env.KV_REST_API_TOKEN
  if (!url || !token) return
  const slim = {
    ts: Date.now(),
    event: eventName,
    id: record?.id,
    stage: record?.stage,
    source: record?.source, // Twenty's source enum (channel) — not PII
  }
  const member = encodeURIComponent(JSON.stringify(slim))
  try {
    await fetch(`${url}/lpush/twenty_events/${member}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
  } catch { /* best-effort cache — never affects the ack */ }
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST')
    return res.status(405).json({ ok: false, error: 'method_not_allowed' })
  }

  const body = await readJson(req)
  // Re-serialize for the HMAC fallback (we don't have the exact raw bytes once parsed; this
  // matches Twenty's JSON.stringify of the same object closely enough for the common case,
  // and the token/header paths don't depend on it).
  const rawForHmac = JSON.stringify(body)

  const ok = authorized(req, rawForHmac)
  if (ok === null) return res.status(503).json({ ok: false, error: 'not_configured' })
  if (!ok) return res.status(401).json({ ok: false, error: 'unauthorized' })

  const { eventName, record } = parseEvent(body)

  // Always ack 2xx after auth so Twenty doesn't retry-storm; side-effects are best-effort.
  try {
    if (eventName === 'person.created') {
      const f = personFields(record)
      await Promise.all([
        notifyOwner({
          title: 'New consulting lead (Twenty)',
          fields: { lead: f.lead, email: f.email, role: f.role, company: f.company },
        }),
        cacheEvent(eventName, record),
      ])
    } else if (eventName === 'opportunity.created') {
      const f = opportunityFields(record)
      await Promise.all([
        notifyOwner({
          title: 'New opportunity (Twenty)',
          fields: { opportunity: f.opportunity, stage: f.stage, amount: f.amount },
        }),
        cacheEvent(eventName, record),
      ])
    }
    // Any other event (incl. Twenty's create-time test ping) → ack, no side-effect.
  } catch {
    /* swallow — the owner alert is best-effort and must never trigger a Twenty retry */
  }
  return res.status(200).json({ ok: true })
}
