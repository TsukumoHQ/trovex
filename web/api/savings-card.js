/**
 * GET /api/savings-card?a=&l=&s=&c=&d=&p=[&format=svg]
 *
 * Renders the /savings calculator result as a branded share card (cro receipt
 * spec 971fb1a, formats #3 + #4):
 *   - default            → PNG (image/png), used as the og:image on a shared
 *                          /savings link so X / LinkedIn / Slack preview the
 *                          ACTUAL number (those crawlers do NOT render SVG
 *                          og:images — hence the raster).
 *   - ?format=svg        → the SVG card (spec format #3, self-contained).
 *
 * Honest by construction: the number comes only from the querystring (the same
 * six numeric inputs the calculator encodes — no PII, no headers). If the result
 * is below the receipt honesty gate (or the link carries no inputs), we render
 * the GENERIC brand card (the product's ~60% claim) rather than a weak/fake brag.
 *
 * No headless browser: satori lays the card out and converts text to vector
 * PATHS using the bundled fonts (so the rasterizer needs no fonts), then
 * @resvg/resvg-js rasterizes — the same pipeline as scripts/gen-blog-og.mjs.
 * This is deliberate: resvg's native font loading (fontFiles/fontBuffers) does
 * not apply our bundled fonts on Vercel's linux runtime, so we bake the glyphs
 * into the SVG at layout time instead.
 */

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { compute, hasInputs, humanTokens, isShareworthy, money, pct, readInputs } from './_savings.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const FONT = (f) => readFileSync(join(HERE, '_fonts', f))
// satori needs the font data at layout time to outline the glyphs.
const FONTS = [
  { name: 'Fira Code', data: FONT('FiraCode-Regular.ttf'), weight: 400, style: 'normal' },
  { name: 'Fira Code', data: FONT('FiraCode-SemiBold.ttf'), weight: 600, style: 'normal' },
  { name: 'Fira Sans', data: FONT('FiraSans-Bold.otf'), weight: 700, style: 'normal' },
]

// trovex brand tokens (web/src/index.css; brutalist-min — flat stage, green used once).
const C = {
  stage: '#06080d',
  fg: '#e6edf3',
  muted: '#9aa6b8',
  subtle: '#74808f',
  accent: '#22c55e',
  border: 'rgba(148,163,184,0.16)',
}

const h = (type, props, ...kids) => ({
  type,
  props: { ...props, children: kids.length <= 1 ? kids[0] : kids },
})

/** The card element tree (satori flexbox). `m` may be null → generic card. */
function card(m) {
  const worthy = m && isShareworthy(m)
  const headline = worthy ? `~${pct(m)}%` : '~60%'
  // Non-breaking spaces around the colored figures — satori collapses normal
  // whitespace at flex-item boundaries, which would glue "87.6Mtokens" / "~$263/ month".
  const roll = worthy
    ? h(
        'div',
        { style: { display: 'flex' } },
        h('span', { style: { color: C.fg } }, humanTokens(m.tokensPerMonth)),
        h('span', {}, ' tokens / month'),
        h('span', { style: { color: C.subtle } }, '  ·  '),
        h('span', { style: { color: C.fg } }, `~${money(m.dollarsPerMonth)}`),
        h('span', {}, ' / month'),
      )
    : h(
        'div',
        { style: { display: 'flex' } },
        h('span', { style: { color: C.fg } }, 'one canonical answer'),
        h('span', {}, ' instead of rereading the repo'),
      )
  const note = worthy ? 'an estimate on your own inputs' : 'estimate yours in 30 seconds'

  return h(
    'div',
    {
      style: {
        width: '1200px',
        height: '630px',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: C.stage,
        fontFamily: 'Fira Code',
      },
    },
    h('div', { style: { height: '6px', backgroundColor: C.accent } }),
    h(
      'div',
      {
        style: {
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '54px 64px 44px',
        },
      },
      // brand + eyebrow
      h(
        'div',
        { style: { display: 'flex', flexDirection: 'column' } },
        h(
          'div',
          { style: { display: 'flex', alignItems: 'center', fontSize: '30px', color: C.fg } },
          h('div', { style: { width: '20px', height: '20px', backgroundColor: C.accent, marginRight: '16px' } }),
          h('span', {}, 'trovex.dev'),
        ),
        h(
          'div',
          { style: { marginTop: '26px', fontSize: '25px', color: C.subtle, letterSpacing: '2px' } },
          'token-savings estimate',
        ),
      ),
      // hero number + label
      h(
        'div',
        { style: { display: 'flex', flexDirection: 'column' } },
        h(
          'div',
          { style: { fontSize: '168px', fontWeight: 600, color: C.accent, lineHeight: 1, letterSpacing: '-4px' } },
          headline,
        ),
        h(
          'div',
          { style: { marginTop: '14px', fontFamily: 'Fira Sans', fontSize: '46px', fontWeight: 700, color: C.muted } },
          'fewer tokens per doc lookup',
        ),
      ),
      // roll line
      h('div', { style: { fontSize: '34px', color: C.muted, display: 'flex' } }, roll),
      // footer
      h(
        'div',
        {
          style: {
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '24px',
            borderTop: `1px solid ${C.border}`,
            paddingTop: '22px',
          },
        },
        h('span', { style: { color: C.subtle } }, note),
        h('span', { style: { color: C.accent } }, 'trovex.dev/savings'),
      ),
    ),
  )
}

async function buildSvg(m) {
  const { default: satori } = await import('satori')
  // card() builds a satori hyperscript tree, not a React element — satori accepts it.
  return satori(/** @type {any} */ (card(m)), { width: 1200, height: 630, fonts: /** @type {any} */ (FONTS) })
}

async function svgToPng(svg) {
  const { Resvg } = await import('@resvg/resvg-js')
  // satori already outlined the text to paths, so resvg needs no fonts here.
  return new Resvg(svg, { fitTo: { mode: 'width', value: 1200 } }).render().asPng()
}

export default async function handler(req, res) {
  let params
  try {
    params = new URL(req.url, 'http://localhost').searchParams
  } catch {
    params = new URLSearchParams()
  }

  // No querystring inputs (the bare /savings or /audit og:image) → render the GENERIC
  // brand card (the conservative ~60% claim), NOT the default scenario, which computes
  // ~64% and would overstate our public floor. The real number shows only when the link
  // carries the sharer's own inputs. (Matches the honesty note in the header docblock.)
  const m = hasInputs(params) ? compute(readInputs(params)) : null

  // Cache hard at the CDN — the card is a pure function of the querystring.
  res.setHeader('Cache-Control', 'public, max-age=3600, s-maxage=604800, stale-while-revalidate=86400')

  let svg
  try {
    svg = await buildSvg(m)
  } catch (e) {
    // Layout failed — never 500 an og:image (a broken image kills the preview).
    res.setHeader('Content-Type', 'text/plain; charset=utf-8')
    return res.status(200).send(`card unavailable: ${String(e.message || e)}`)
  }

  if ((params.get('format') || '').toLowerCase() === 'svg') {
    res.setHeader('Content-Type', 'image/svg+xml; charset=utf-8')
    return res.status(200).send(svg)
  }

  try {
    const png = await svgToPng(svg)
    res.setHeader('Content-Type', 'image/png')
    return res.status(200).send(png)
  } catch {
    // Rasterization failed — fall back to the (self-contained) SVG; a degraded
    // card beats no card.
    res.setHeader('Content-Type', 'image/svg+xml; charset=utf-8')
    return res.status(200).send(svg)
  }
}
