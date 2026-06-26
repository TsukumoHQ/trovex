/**
 * GET /api/savings-badge?a=&l=&s=&c=&d=&p=   (pretty: /savings/badge?…)
 *
 * A dynamic shields.io ENDPOINT badge (https://shields.io/badges/endpoint-badge)
 * for the savings receipt loop (cro spec 971fb1a, format #2 — TSU-48). Users embed:
 *
 *   [![trovex](https://img.shields.io/endpoint?url=https%3A%2F%2Ftrovex.dev%2Fsavings%2Fbadge%3Fa%3D3%26l%3D12%26…)](https://trovex.dev/savings)
 *
 * shields fetches this JSON and renders the badge, so one embed stays live: if the
 * model or framing changes, every badge updates, and the honesty gate is enforced
 * HERE (server-side) — a stale baked-in number can't overclaim.
 *
 * Honest by construction:
 *   - the number is computed only from the six numeric calculator inputs in the
 *     querystring (the SAME _savings.js model the calculator + card use) — no header,
 *     no cookie, no repo path, no query text, no PII can reach it (readInputs reads
 *     only the 6 keys);
 *   - the message is explicitly marked "(est.)" — it's a per-input estimate, not a
 *     measured number, and the click-through lands on /savings where the formula is
 *     visible ("show the math");
 *   - below the receipt honesty gate (or with no inputs that clear it) the badge
 *     shows a neutral "estimate your token savings" — never a fabricated brag.
 */

import { compute, isShareworthy, pct, readInputs } from './_savings.js'

// trovex brand green (web/src/index.css). shields takes a hex colour without the '#'.
const ACCENT = '22c55e'
const NEUTRAL = '9aa6b8'

export function badge(params) {
  const m = compute(readInputs(params))
  const worthy = isShareworthy(m)
  return {
    schemaVersion: 1,
    label: 'trovex',
    message: worthy ? `~${pct(m)}% fewer tokens (est.)` : 'estimate your token savings',
    color: worthy ? ACCENT : NEUTRAL,
    // shields clamps to a 300s floor; an estimate doesn't need to be fresher than the CDN.
    cacheSeconds: 3600,
  }
}

export default function handler(req, res) {
  let params
  try {
    params = new URL(req.url, 'http://localhost').searchParams
  } catch {
    params = new URLSearchParams()
  }

  // Pure function of the querystring → cache hard at the CDN; shields will also cache.
  res.setHeader('Cache-Control', 'public, max-age=3600, s-maxage=604800, stale-while-revalidate=86400')
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.setHeader('Access-Control-Allow-Origin', '*')
  return res.status(200).send(JSON.stringify(badge(params)))
}
