/**
 * GET /api/savings-card?a=&l=&s=&c=&d=&p=[&format=svg]
 *
 * Renders the /savings calculator result as a branded share card (cro receipt
 * spec 971fb1a, formats #3 + #4):
 *   - default            → PNG (image/png), used as the og:image on a shared
 *                          /savings link so X / LinkedIn / Slack preview the
 *                          ACTUAL number (those crawlers do NOT render SVG
 *                          og:images — hence the raster).
 *   - ?format=svg        → the raw SVG card (spec format #3, embeddable).
 *
 * Honest by construction: the number comes only from the querystring (the same
 * six numeric inputs the calculator encodes — no PII, no headers). If the result
 * is below the receipt honesty gate (or the link carries no inputs), we render
 * the GENERIC brand card (the product's ~60% claim) rather than a weak/fake brag.
 *
 * No headless browser: hand-built SVG + @resvg/resvg-js (the same rasterizer the
 * build-time blog-OG script uses), fonts bundled in ./_fonts.
 */

import { Resvg } from '@resvg/resvg-js'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { compute, humanTokens, isShareworthy, money, pct, readInputs } from './_savings.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const FONT_FILES = [
  join(HERE, '_fonts', 'FiraCode-Regular.ttf'),
  join(HERE, '_fonts', 'FiraCode-SemiBold.ttf'),
  join(HERE, '_fonts', 'FiraSans-Bold.otf'),
]
// Read fonts once at cold start; fail loud if a font is missing (build mistake).
const FONT_BUFFERS = FONT_FILES.map((f) => readFileSync(f))

// trovex brand tokens (web/src/index.css; brutalist-min — flat stage, green used once).
const C = {
  stage: '#06080d',
  fg: '#e6edf3',
  muted: '#9aa6b8',
  subtle: '#74808f',
  accent: '#22c55e',
  border: 'rgba(148,163,184,0.16)',
}

const esc = (s) =>
  String(s).replace(/[<>&"']/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' }[c]))

/** Build the 1200×630 share card as an SVG string. `m` may be null → generic card. */
function buildSvg(m) {
  const worthy = m && isShareworthy(m)
  const headline = worthy ? `~${pct(m)}%` : '~60%'
  const roll = worthy
    ? `<tspan fill="${C.fg}">${esc(humanTokens(m.tokensPerMonth))}</tspan> tokens / month` +
      `  ·  ` +
      `<tspan fill="${C.fg}">~${esc(money(m.dollarsPerMonth))}</tspan> / month`
    : `<tspan fill="${C.fg}">one canonical answer</tspan> instead of rereading the repo`
  const note = worthy ? 'an estimate on your own inputs' : 'estimate yours in 30 seconds'

  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="trovex token-savings estimate: ${esc(headline)} fewer tokens per doc lookup">
  <rect width="1200" height="630" fill="${C.stage}"/>
  <rect x="0" y="0" width="1200" height="6" fill="${C.accent}"/>
  <rect x="80" y="78" width="20" height="20" fill="${C.accent}"/>
  <g font-family="Fira Code">
    <text x="112" y="96" font-size="30" fill="${C.fg}">trovex.dev</text>
    <text x="80" y="168" font-size="25" fill="${C.subtle}" letter-spacing="2">token-savings estimate</text>
    <text x="76" y="360" font-size="185" font-weight="600" fill="${C.accent}" letter-spacing="-4">${esc(headline)}</text>
    <text x="80" y="512" font-size="34" fill="${C.muted}">${roll}</text>
  </g>
  <text x="80" y="428" font-family="Fira Sans" font-size="46" font-weight="700" fill="${C.muted}">fewer tokens per doc lookup</text>
  <line x1="80" y1="556" x2="1120" y2="556" stroke="${C.border}" stroke-width="1"/>
  <g font-family="Fira Code" font-size="24">
    <text x="80" y="598" fill="${C.subtle}">${esc(note)}</text>
    <text x="1120" y="598" fill="${C.accent}" text-anchor="end">trovex.dev/savings</text>
  </g>
</svg>`
}

function svgToPng(svg) {
  return new Resvg(svg, {
    fitTo: { mode: 'width', value: 1200 },
    font: { fontBuffers: FONT_BUFFERS, loadSystemFonts: false, defaultFontFamily: 'Fira Code' },
  })
    .render()
    .asPng()
}

export default function handler(req, res) {
  let params
  try {
    params = new URL(req.url, 'http://localhost').searchParams
  } catch {
    params = new URLSearchParams()
  }

  const m = compute(readInputs(params))
  const svg = buildSvg(m)

  // Cache hard at the CDN — the card is a pure function of the querystring.
  res.setHeader('Cache-Control', 'public, max-age=3600, s-maxage=604800, stale-while-revalidate=86400')

  if ((params.get('format') || '').toLowerCase() === 'svg') {
    res.setHeader('Content-Type', 'image/svg+xml; charset=utf-8')
    return res.status(200).send(svg)
  }

  try {
    const png = svgToPng(svg)
    res.setHeader('Content-Type', 'image/png')
    return res.status(200).send(png)
  } catch {
    // Rasterization failed — never 500 an og:image (a broken image kills the
    // preview). Fall back to the SVG; a degraded card beats no card.
    res.setHeader('Content-Type', 'image/svg+xml; charset=utf-8')
    return res.status(200).send(svg)
  }
}
