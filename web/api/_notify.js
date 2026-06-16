/**
 * Owner notification on a new waitlist signup. Server-side only, env-gated —
 * nothing fires until the owner wires a channel. Two optional sinks, both read
 * from SERVER env only (never client, never exposed, never committed):
 *
 *   - NOTIFY_WEBHOOK_URL  — Slack / Discord / generic incoming webhook; POST { text }.
 *   - RESEND_API_KEY + NOTIFY_EMAIL_TO (+ optional NOTIFY_EMAIL_FROM) — email via Resend.
 *
 * Best-effort: every failure is swallowed and NEVER fails the signup. The
 * volunteered email goes to the OWNER's own private channel (that's the point) —
 * it is NOT written to logs; on error we surface nothing, so no PII can leak.
 * Each sink has a hard timeout so a hung webhook can't pin the function. Awaited
 * (a plain Vercel function may freeze after the response, dropping pending work).
 */

const TIMEOUT_MS = 3000

function format(title, fields) {
  const out = [title]
  for (const [k, v] of Object.entries(fields)) {
    if (v) out.push(`${k}: ${v}`)
  }
  return out.join('\n')
}

async function withTimeout(run) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  try {
    await run(ctrl.signal)
  } catch {
    /* swallow — notification is best-effort, never fails the signup */
  } finally {
    clearTimeout(timer)
  }
}

async function postWebhook(text) {
  const url = process.env.NOTIFY_WEBHOOK_URL
  if (!url) return
  await withTimeout((signal) =>
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal,
    }),
  )
}

async function sendEmail(subject, text) {
  const key = process.env.RESEND_API_KEY
  const to = process.env.NOTIFY_EMAIL_TO
  if (!key || !to) return
  const from = process.env.NOTIFY_EMAIL_FROM || 'trovex <onboarding@resend.dev>'
  await withTimeout((signal) =>
    fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, to, subject, text }),
      signal,
    }),
  )
}

export async function notifyOwner({ title, fields }) {
  const body = format(title, fields)
  await Promise.allSettled([postWebhook(body), sendEmail(title, body)])
}
