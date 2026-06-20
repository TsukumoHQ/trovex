/**
 * Twenty CRM sink for the trovex waitlist — mirror a captured signup into the
 * consulting pipeline so the owner sees the lead + where it came from.
 *
 * Faithful port of tsukumo's src/lib/twenty.ts (#362): Supabase stays the source
 * of truth, Twenty is the pipeline VIEW. On a NEW signup we upsert a Person (by
 * email) and attach a Note carrying the attribution. Keep the two in lockstep.
 *
 * Server-side only, env-gated, best-effort + fire-and-forget — the notifyOwner
 * pattern. A failure NEVER blocks or fails the signup, and nothing fires until
 * the key is wired:
 *   - TWENTY_API_KEY   — required; the workspace API key (Bearer).
 *   - TWENTY_BASE_URL  — optional; default the Twenty cloud api host. No trailing slash.
 * Idempotent on email: an existing Person is left as-is (no duplicate, no note).
 *
 * Privacy: the volunteered email (+ source attribution) go to the owner's own
 * CRM (the point). Never written to logs here.
 */

const DEFAULT_BASE = 'https://api.twenty.com'
const TIMEOUT_MS = 4000

function cfg() {
  const key = process.env.TWENTY_API_KEY
  if (!key) return null
  const base = (process.env.TWENTY_BASE_URL || DEFAULT_BASE).replace(/\/+$/, '')
  return { base, key }
}

function splitName(name, email) {
  const trimmed = (name || '').trim()
  if (trimmed) {
    const parts = trimmed.split(/\s+/)
    const firstName = parts.shift()
    return { firstName: firstName.slice(0, 100), lastName: parts.join(' ').slice(0, 100) }
  }
  return { firstName: (email.split('@')[0] || 'lead').slice(0, 100), lastName: '' }
}

async function twentyFetch(c, path, init) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  try {
    return await fetch(`${c.base}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${c.key}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(init.headers || {}),
      },
      signal: ctrl.signal,
    })
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}

async function findPersonId(c, email) {
  const q = encodeURIComponent(`emails.primaryEmail[eq]:${email}`)
  const res = await twentyFetch(c, `/rest/people?filter=${q}&limit=1`, { method: 'GET' })
  if (!res || !res.ok) return null
  const json = await res.json().catch(() => null)
  const people = json?.data?.people
  return Array.isArray(people) && people[0]?.id ? people[0].id : null
}

async function createPerson(c, lead) {
  const { firstName, lastName } = splitName(lead.name, lead.email)
  const body = { name: { firstName, lastName }, emails: { primaryEmail: lead.email } }
  if (lead.role) body.jobTitle = String(lead.role).slice(0, 120)
  if (lead.linkedin) body.linkedinLink = { primaryLinkUrl: String(lead.linkedin).slice(0, 256) }
  const res = await twentyFetch(c, '/rest/people', { method: 'POST', body: JSON.stringify(body) })
  if (!res || !res.ok) return null
  const json = await res.json().catch(() => null)
  return json?.data?.createPerson?.id || json?.data?.id || null
}

async function attachSourceNote(c, personId, lead) {
  const lines = [
    `Source: ${lead.source ?? 'trovex'}`,
    lead.company ? `Company: ${lead.company}` : '',
    lead.utm?.utm_source ? `utm_source: ${lead.utm.utm_source}` : '',
    lead.utm?.utm_medium ? `utm_medium: ${lead.utm.utm_medium}` : '',
    lead.utm?.utm_campaign ? `utm_campaign: ${lead.utm.utm_campaign}` : '',
    lead.utm?.utm_content ? `utm_content: ${lead.utm.utm_content}` : '',
    lead.referer ? `referer: ${lead.referer}` : '',
    lead.message ? `\nMessage:\n${String(lead.message).slice(0, 2000)}` : '',
  ].filter(Boolean)
  const body = lines.join('\n')

  // Twenty's note body is the RICH_TEXT field `bodyV2` (NOT `body` — that field does
  // not exist; a `body` payload 400s). Pass the composite { markdown } sub-field.
  const noteRes = await twentyFetch(c, '/rest/notes', {
    method: 'POST',
    body: JSON.stringify({ title: 'Lead source — trovex waitlist', bodyV2: { markdown: body } }),
  })
  if (!noteRes || !noteRes.ok) return
  const noteJson = await noteRes.json().catch(() => null)
  const noteId = noteJson?.data?.createNote?.id || noteJson?.data?.id
  if (!noteId) return
  // noteTarget links the note to a person via the morph field `targetPerson`, so the
  // REST FK is `targetPersonId` (NOT `personId` — that's silently ignored, leaving the
  // source note unlinked to the lead).
  await twentyFetch(c, '/rest/noteTargets', {
    method: 'POST',
    body: JSON.stringify({ noteId, targetPersonId: personId }),
  })
}

/**
 * Upsert a waitlist lead into Twenty. No-op when TWENTY_API_KEY is unset.
 * Idempotent on email. Best-effort: a failure must never affect the signup.
 *
 * lead: { email, name?, company?, source?, message?, linkedin?, role?, utm?, referer? }
 */
export async function syncLeadToTwenty(lead) {
  const c = cfg()
  if (!c || !lead?.email) return
  try {
    const existing = await findPersonId(c, lead.email)
    if (existing) return // already in the pipeline — idempotent
    const personId = await createPerson(c, lead)
    if (personId) await attachSourceNote(c, personId, lead)
  } catch {
    /* swallow — CRM sync is best-effort and must never affect the capture */
  }
}
