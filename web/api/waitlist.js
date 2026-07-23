/**
 * trovex private-beta waitlist capture (first-party, no third-party SaaS).
 *
 * POST /api/waitlist  { email, company, ...attribution }
 *   - "company" is a honeypot — must be empty
 *   - attribution = closed-enum source props (geo_source, channel, utm_*, referrer host)
 *     from web/src/analytics.ts getAttribution(); NO PII. Stored with the signup so we
 *     can read signups-by-source. The email is the only PII.
 *
 * Storage is env-gated so no secret lives in the repo and nothing is captured until
 * the operator wires a backend in Vercel. In priority order:
 *   1. Supabase            — set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (service key is
 *                            SERVER-ONLY: never client, never NEXT_PUBLIC, never committed).
 *                            Inserts a row into the `waitlist` table via the REST endpoint.
 *                            RLS is ON with no public policy, so only the service role writes.
 *   2. Upstash/Vercel KV   — set WAITLIST_KV_REST_API_URL + WAITLIST_KV_REST_API_TOKEN
 *                            (or the platform's KV_REST_API_URL / KV_REST_API_TOKEN)
 *   3. GitHub issue        — set WAITLIST_GITHUB_TOKEN + WAITLIST_GITHUB_REPO (owner/repo)
 *   4. none configured     — 503 { reason: 'not_configured' }; the form says the list
 *                            isn't open yet. We never claim success without storing.
 *
 * Privacy: the email is volunteered PII and is the ONLY thing stored. It is never
 * written to logs, analytics, or error traces. The client fires waitlist_submitted
 * (source attribution only) — see web/src/analytics.ts.
 */

import { createHash } from 'node:crypto'
import { rateLimited } from './_rate-limit.js'
import { notifyOwner } from './_notify.js'
import { syncLeadToTwenty } from './_twenty.js'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// Server-derived, non-client attribution (never trust the body for these).
// referer = host only (no path/query/PII). ip_hash = salted SHA-256 so a row can be
// rate-limited / de-duped without storing a raw IP; skipped if no salt is configured.
function serverMeta(req) {
  let referer = null
  try {
    const raw = req.headers.referer || req.headers.referrer
    if (raw) referer = new URL(raw).host.slice(0, 64)
  } catch { /* malformed Referer — ignore */ }

  const fwd = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim()
  const ip = fwd || req.socket?.remoteAddress || ''
  let ip_hash = null
  const salt = process.env.WAITLIST_IP_SALT
  if (salt && ip) {
    ip_hash = createHash('sha256').update(salt + ip).digest('hex').slice(0, 32)
  }
  // ip is returned for the in-memory rate-limit fallback ONLY — never stored,
  // logged, or persisted (only ip_hash is written to a row).
  return { referer, ip_hash, ip: ip || null }
}

// Closed allowlist of source-attribution fields (no PII). Anything else is dropped;
// each value is coerced to a short string so a crafted body can't bloat storage.
const ATTRIBUTION_KEYS = [
  'geo_source', 'channel', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'referrer',
]
function pickAttribution(body) {
  const out = {}
  for (const k of ATTRIBUTION_KEYS) {
    if (body[k] == null) continue
    const v = String(body[k]).trim().slice(0, 64)
    if (v) out[k] = v
  }
  return out
}

function readJson(req) {
  // Vercel may pre-parse req.body; otherwise read the stream. Cap the size.
  if (req.body && typeof req.body === 'object') return Promise.resolve(req.body)
  return new Promise((resolve) => {
    let raw = ''
    req.on('data', (c) => {
      raw += c
      if (raw.length > 4096) raw = raw.slice(0, 4096)
    })
    req.on('end', () => {
      try { resolve(JSON.parse(raw || '{}')) } catch { resolve({}) }
    })
    req.on('error', () => resolve({}))
  })
}

// Map the closed attribution enums to the `waitlist` table shape:
//   source = the acquisition source (geo_source/channel, falling back to utm_source)
//   utm    = jsonb bag of the raw utm_* fields (+ referrer host the client derived)
function buildSourceAndUtm(attribution) {
  const source =
    attribution.geo_source || attribution.channel || attribution.utm_source || null
  const utm = {}
  for (const k of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'referrer', 'channel', 'geo_source']) {
    if (attribution[k]) utm[k] = attribution[k]
  }
  return { source, utm: Object.keys(utm).length ? utm : null }
}

// Result of a store attempt: 'ok' (inserted), 'duplicate' (already on the list),
// 'skip' (backend not configured → try the next one), or throws on a real error.
async function storeSupabase(email, attribution, meta) {
  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) return 'skip'
  // Service role bypasses RLS (RLS is ON with no policy → only the server writes).
  // This code path only ever runs server-side. The email is the only PII; never logged.
  const { source, utm } = buildSourceAndUtm(attribution)
  const row = {
    project: 'trovex', // central multi-project Supabase: unique(project,email)
    email,
    source,
    utm,
    referer: meta.referer || null,
  }
  const res = await fetch(`${url}/rest/v1/waitlist`, {
    method: 'POST',
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`,
      'Content-Type': 'application/json',
      Prefer: 'return=minimal',
    },
    body: JSON.stringify(row),
  })
  if (res.ok) return 'ok'
  // Unique violation on email → already on the list; treat as success.
  if (res.status === 409) return 'duplicate'
  // 23505 can also surface inside a 400/422 body depending on PostgREST version.
  if (res.status === 400 || res.status === 422) {
    const detail = await res.text().catch(() => '')
    if (detail.includes('23505') || detail.includes('duplicate key')) return 'duplicate'
    // Surface the real failure (e.g. relation does not exist) without leaking PII.
    throw new Error(`supabase ${res.status}`)
  }
  throw new Error(`supabase ${res.status}`)
}

async function storeKV(email, attribution) {
  const url = process.env.WAITLIST_KV_REST_API_URL || process.env.KV_REST_API_URL
  const token = process.env.WAITLIST_KV_REST_API_TOKEN || process.env.KV_REST_API_TOKEN
  if (!url || !token) return false
  // SADD keeps the list de-duplicated; the member is a JSON record carrying the
  // timestamp, email, and source attribution (no PII beyond the volunteered email).
  const member = JSON.stringify({ ts: Date.now(), email, ...attribution })
  const res = await fetch(`${url}/sadd/trovex_waitlist/${encodeURIComponent(member)}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  return res.ok
}

async function storeGitHubIssue(email, attribution) {
  const token = process.env.WAITLIST_GITHUB_TOKEN
  const repo = process.env.WAITLIST_GITHUB_REPO // "owner/repo"
  if (!token || !repo) return false
  const attrLines = Object.entries(attribution)
    .map(([k, v]) => `${k}: ${v}`)
    .join('\n')
  const res = await fetch(`https://api.github.com/repos/${repo}/issues`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'trovex-waitlist',
    },
    body: JSON.stringify({
      title: 'waitlist signup',
      body: `email: ${email}${attrLines ? `\n\nsource:\n${attrLines}` : ''}`,
      labels: ['waitlist'],
    }),
  })
  return res.ok
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST')
    return res.status(405).json({ ok: false, error: 'method_not_allowed' })
  }

  const body = await readJson(req)
  const email = String(body.email || '').trim().toLowerCase()
  const honeypot = String(body.company || '').trim()

  // Honeypot: a bot filled the hidden field. Pretend success, store nothing.
  if (honeypot) return res.status(200).json({ ok: true })

  const meta = serverMeta(req)
  // Throttle floods before any further work (durable via KV when configured, else
  // best-effort per-instance). Gated ahead of validation so spam of any shape is
  // capped; honeypot + validation remain the hard defenses.
  if (await rateLimited({ scope: 'waitlist', ipHash: meta.ip_hash, ip: meta.ip })) {
    return res.status(429).json({ ok: false, error: 'rate_limited' })
  }

  if (!email || email.length > 254 || !EMAIL_RE.test(email)) {
    return res.status(400).json({ ok: false, error: 'invalid_email' })
  }

  const attribution = pickAttribution(body)

  try {
    // storeSupabase returns 'ok' | 'duplicate' (stored) or 'skip' (not configured →
    // fall through to the legacy backends). 'skip' is truthy, so branch explicitly.
    const sb = await storeSupabase(email, attribution, meta)
    const stored =
      sb === 'ok' || sb === 'duplicate'
        ? true
        : (await storeKV(email, attribution)) || (await storeGitHubIssue(email, attribution))
    if (!stored) {
      // No backend wired yet — be honest, don't claim a save.
      return res.status(503).json({ ok: false, error: 'not_configured' })
    }
    // Ping the owner on a genuinely new signup (skip known duplicates). Best-effort
    // + env-gated; awaited (a plain Vercel function may freeze after the response).
    // A failed notify never affects the stored signup.
    // channel:'healthcheck' is the reserved synthetic source (same convention as the
    // /go?s=healthcheck shortlink probes) — the dokan funnel-health canary (script 439)
    // POSTs a real signup to prove the write path end-to-end, then deletes the row. It
    // must never page the owner or create a Twenty CRM contact on every run.
    if (sb !== 'duplicate' && attribution.channel !== 'healthcheck') {
      const { source, utm } = buildSourceAndUtm(attribution)
      // Best-effort side-effects: owner ping + Twenty CRM pipeline mirror.
      // Neither affects the stored signup; run concurrently so latency doesn't
      // stack, and both are env-gated + swallow their own errors.
      await Promise.all([
        notifyOwner({
          title: 'New trovex waitlist signup',
          fields: { email, source, via: meta.referer },
        }),
        syncLeadToTwenty({ email, name: null, company: null, source, message: null, utm: utm || {}, referer: meta.referer }),
      ])
    }
    return res.status(200).json({ ok: true })
  } catch {
    // Never echo the email or the underlying error to the client/logs.
    return res.status(502).json({ ok: false, error: 'store_failed' })
  }
}
