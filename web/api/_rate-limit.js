/**
 * Best-effort abuse throttle for the public form routes (waitlist).
 *
 * Durable when a KV REST backend is configured (WAITLIST_KV_REST_API_URL/TOKEN,
 * falling back to KV_REST_API_URL/TOKEN — Upstash / Vercel KV compatible): the
 * counter is shared across serverless instances, so a flood is caught no matter
 * which instance it lands on. With no KV configured it falls back to a
 * per-instance in-memory sliding window (only catches floods on the same warm
 * instance).
 *
 * Privacy: the durable (KV) key is the salted ip_hash only — a raw IP is NEVER
 * written to KV, logs, or storage. With no salt configured we fall back to the
 * raw IP as an EPHEMERAL in-memory map key only (held transiently in process
 * memory, never persisted). Fail-open: if KV is unreachable we don't block
 * legitimate users — the honeypot + validation remain the hard anti-abuse.
 */

const DEFAULT_MAX = 5
const DEFAULT_WINDOW_MS = 60_000

// Per-instance fallback store. Ephemeral; bounded by opportunistic cleanup.
const mem = new Map()
function memLimited(key, max, windowMs) {
  const now = Date.now()
  const recent = (mem.get(key) || []).filter((t) => now - t < windowMs)
  recent.push(now)
  mem.set(key, recent)
  if (mem.size > 5000) {
    for (const [k, v] of mem) {
      if (v.every((t) => now - t >= windowMs)) mem.delete(k)
    }
  }
  return recent.length > max
}

// INCR + first-hit EXPIRE against a KV REST API. Returns null when KV is not
// configured or unreachable so the caller can fall back to memory.
async function kvLimited(key, max, windowMs) {
  const url = process.env.WAITLIST_KV_REST_API_URL || process.env.KV_REST_API_URL
  const token = process.env.WAITLIST_KV_REST_API_TOKEN || process.env.KV_REST_API_TOKEN
  if (!url || !token) return null
  const windowSec = Math.ceil(windowMs / 1000)
  try {
    const incr = await fetch(`${url}/incr/${encodeURIComponent(key)}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!incr.ok) return null
    const data = await incr.json()
    const count = typeof data.result === 'number' ? data.result : 1
    if (count === 1) {
      // First hit in the window → set the TTL. Fire-and-forget: a failure only
      // loosens this one window, it never blocks the request.
      await fetch(`${url}/expire/${encodeURIComponent(key)}/${windowSec}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {})
    }
    return count > max
  } catch {
    return null
  }
}

export async function rateLimited({ scope, ipHash, ip, max = DEFAULT_MAX, windowMs = DEFAULT_WINDOW_MS }) {
  const id = ipHash || ip
  if (!id) return false // no client identifier → honeypot + validation cover it
  if (ipHash) {
    const kv = await kvLimited(`rl:${scope}:${ipHash}`, max, windowMs)
    if (kv !== null) return kv
  }
  return memLimited(`${scope}:${id}`, max, windowMs)
}
