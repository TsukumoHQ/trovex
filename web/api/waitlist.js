/**
 * trovex private-beta waitlist capture (first-party, no third-party SaaS).
 *
 * POST /api/waitlist  { email, company }   ("company" is a honeypot — must be empty)
 *
 * Storage is env-gated so no secret lives in the repo and nothing is captured until
 * the operator wires a backend in Vercel. In priority order:
 *   1. Upstash/Vercel KV   — set WAITLIST_KV_REST_API_URL + WAITLIST_KV_REST_API_TOKEN
 *                            (or the platform's KV_REST_API_URL / KV_REST_API_TOKEN)
 *   2. GitHub issue        — set WAITLIST_GITHUB_TOKEN + WAITLIST_GITHUB_REPO (owner/repo)
 *   3. none configured     — 503 { reason: 'not_configured' }; the form says the list
 *                            isn't open yet. We never claim success without storing.
 *
 * Privacy: the email is volunteered PII and is the ONLY thing stored. It is never
 * written to logs, analytics, or error traces. The client fires waitlist_submitted
 * (source attribution only) — see web/src/analytics.ts.
 */

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

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

async function storeKV(email) {
  const url = process.env.WAITLIST_KV_REST_API_URL || process.env.KV_REST_API_URL
  const token = process.env.WAITLIST_KV_REST_API_TOKEN || process.env.KV_REST_API_TOKEN
  if (!url || !token) return false
  // SADD keeps the list de-duplicated; value carries a timestamp for ordering.
  const member = `${Date.now()}|${email}`
  const res = await fetch(`${url}/sadd/trovex_waitlist/${encodeURIComponent(member)}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  return res.ok
}

async function storeGitHubIssue(email) {
  const token = process.env.WAITLIST_GITHUB_TOKEN
  const repo = process.env.WAITLIST_GITHUB_REPO // "owner/repo"
  if (!token || !repo) return false
  const res = await fetch(`https://api.github.com/repos/${repo}/issues`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'trovex-waitlist',
    },
    body: JSON.stringify({
      title: 'waitlist signup',
      body: `email: ${email}`,
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

  try {
    const stored = (await storeKV(email)) || (await storeGitHubIssue(email))
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
