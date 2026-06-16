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

  let ip_hash = null
  const salt = process.env.WAITLIST_IP_SALT
  if (salt) {
    const fwd = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim()
    const ip = fwd || req.socket?.remoteAddress || ''
    if (ip) ip_hash = createHash('sha256').update(salt + ip).digest('hex').slice(0, 32)
  }
  return { referer, ip_hash }
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

async function storeSupabase(email, attribution, meta) {
  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) return false
  // Service role bypasses RLS — this code path only ever runs server-side.
  // Columns mirror the closed attribution enums + server-derived meta (referer host,
  // hashed IP). The email is the only PII; never logged.
  const row = {
    email,
    geo_source: attribution.geo_source || null,
    channel: attribution.channel || null,
    utm_source: attribution.utm_source || null,
    utm_medium: attribution.utm_medium || null,
    utm_campaign: attribution.utm_campaign || null,
    utm_content: attribution.utm_content || null,
    referrer: attribution.referrer || null,
    referer: meta.referer || null,
    ip_hash: meta.ip_hash || null,
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
  return res.ok
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

  if (!email || email.length > 254 || !EMAIL_RE.test(email)) {
    return res.status(400).json({ ok: false, error: 'invalid_email' })
  }

  const attribution = pickAttribution(body)
  const meta = serverMeta(req)

  try {
    const stored =
      (await storeSupabase(email, attribution, meta)) ||
      (await storeKV(email, attribution)) ||
      (await storeGitHubIssue(email, attribution))
    if (!stored) {
      // No backend wired yet — be honest, don't claim a save.
      return res.status(503).json({ ok: false, error: 'not_configured' })
    }
    return res.status(200).json({ ok: true })
  } catch {
    // Never echo the email or the underlying error to the client/logs.
    return res.status(502).json({ ok: false, error: 'store_failed' })
  }
}
