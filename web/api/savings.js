/**
 * GET /savings  (rewritten here from vercel.json)
 *
 * Serves the static /savings calculator page, but rewrites the Open Graph /
 * Twitter meta when the link carries a shared result, so a shared
 * /savings?a=…&l=… link previews the ACTUAL number (image + title) in
 * X / LinkedIn / Slack. Every shared receipt becomes a visual ad.
 *
 * Mechanism: fetch the built static savings.html (so the hashed app bundle stays
 * correct), then swap only the <head> og:/twitter: meta — the page body and the
 * React app are untouched and boot normally (the app reads the same querystring).
 *
 * Honest: if the link has no inputs, or the result is below the receipt honesty
 * gate, we serve the page UNCHANGED (the static generic ~60% card) — we never
 * inject a weak or fabricated number. No PII: only the six numeric calculator
 * fields are read.
 */

import { compute, hasInputs, humanTokens, isShareworthy, money, pct, QS, readInputs } from './_savings.js'

function originOf(req) {
  const proto = (req.headers['x-forwarded-proto'] || 'https').split(',')[0].trim()
  const host = (req.headers['x-forwarded-host'] || req.headers.host || 'trovex.dev').split(',')[0].trim()
  return `${proto}://${host}`
}

// Swap the content="" of the <meta> tag carrying `selector` (e.g. property="og:image").
// Exported for unit tests (escaping is the security boundary here).
export function setMeta(html, selector, value) {
  const safe = value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
  const tagRe = new RegExp(`<meta[^>]*\\b${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[^>]*>`, 'i')
  return html.replace(tagRe, (tag) =>
    /content="/i.test(tag)
      ? tag.replace(/content="[^"]*"/i, `content="${safe}"`)
      : tag.replace(/\s*\/?>$/, ` content="${safe}" />`),
  )
}

export default async function handler(req, res) {
  let search = ''
  let params
  try {
    const u = new URL(req.url, 'http://localhost')
    search = u.search
    params = u.searchParams
  } catch {
    params = new URLSearchParams()
  }

  const origin = originOf(req)

  // Fetch the built static page (correct hashed bundle). On any failure, fall
  // back to the static file directly so the user still gets the calculator.
  let html
  try {
    const r = await fetch(`${origin}/savings.html`, { headers: { 'user-agent': 'trovex-og-injector' } })
    if (!r.ok) throw new Error(`fetch savings.html ${r.status}`)
    html = await r.text()
  } catch {
    res.statusCode = 307
    res.setHeader('Location', `/savings.html${search}`)
    return res.end()
  }

  // Only rewrite meta for a shareworthy result; otherwise serve the page as-is.
  // Any failure here is non-fatal: we serve the unmodified static page (generic
  // og card) rather than 500 the calculator.
  try {
   if (hasInputs(params)) {
    const m = compute(readInputs(params))
    if (isShareworthy(m)) {
      // Card URL carries ONLY the six inputs (no utm / format), so the CDN cache
      // key is stable and the card is a pure function of the numbers.
      const cardQs = new URLSearchParams()
      for (const k of Object.values(QS)) {
        const v = params.get(k)
        if (v != null) cardQs.set(k, v)
      }
      const cardUrl = `${origin}/api/savings-card?${cardQs.toString()}`
      const p = pct(m)
      const perMo = money(m.dollarsPerMonth)
      const title = `~${p}% fewer doc-lookup tokens (~${perMo}/mo) · trovex`
      const desc =
        `An estimate on real inputs, same model trovex uses: ~${humanTokens(m.tokensPerMonth)} tokens/month ` +
        `saved by handing agents one canonical answer instead of rereading the repo. Run your own numbers.`

      html = setMeta(html, 'property="og:image"', cardUrl)
      html = setMeta(html, 'name="twitter:image"', cardUrl)
      html = setMeta(html, 'property="og:title"', title)
      html = setMeta(html, 'name="twitter:title"', title)
      html = setMeta(html, 'property="og:description"', desc)
      html = setMeta(html, 'property="og:url"', `${origin}/savings${search}`)
    }
   }
  } catch {
    /* meta-injection failed — serve the unmodified page (generic og card) */
  }

  res.setHeader('Content-Type', 'text/html; charset=utf-8')
  res.setHeader('Cache-Control', 'public, max-age=0, s-maxage=86400, stale-while-revalidate=604800')
  return res.status(200).send(html)
}
