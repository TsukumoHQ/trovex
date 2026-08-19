// Shareable savings-receipt card — the MEASURED counterpart to the /savings
// estimate card (savings/receiptCard.ts). Same dark-social atom, same brand,
// but the numbers are the running instance's REAL saving, not a modelled one.
//
// Privacy-safe by construction: AGGREGATE ONLY. No repo, paths, queries, agent
// names, or session ids ever touch the card — only the totals a user already
// chose to share. The /receipt dashboard itself stays private (never indexed);
// this card is the one artifact a user can deliberately drag into a post, which
// is what closes the awareness loop the study flags as trovex's biggest gap.
//
// Honesty travels with the number: the card is stamped `routing verified` or
// `raw estimate` exactly as the dashboard headline is, so a shared card can
// never over-claim past what the instance actually measured.

const C = {
  stage: '#06080d',
  fg: '#e6edf3',
  muted: '#9aa6b8',
  subtle: '#74808f',
  accent: '#22c55e',
  sans: "'Fira Sans', system-ui, -apple-system, sans-serif",
  mono: "'Fira Code', ui-monospace, SFMono-Regular, Menlo, monospace",
}

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

export type ShareCardInput = {
  /** round(ratio*100) — the headline % */
  pct: number
  /** humanTokens(saved), e.g. "2.3M" — aggregate tokens saved */
  tokensLabel: string
  /** money(savedUsd), e.g. "$1,234" — aggregate $ saved. Empty when the server
   *  hasn't priced the saving yet; the card then omits the $ rather than fake one. */
  moneyLabel: string
  /** number of queries the figure is measured over */
  queries: number
  /** true → "routing verified"; false → "raw estimate" (honesty stamp) */
  verified: boolean
}

/** True when there's a real, non-trivial saving worth a card. */
function worthCard(m: ShareCardInput): boolean {
  return m.pct > 0 && m.queries > 0 && m.tokensLabel !== '0'
}

/**
 * Build the 1200x630 share card as an SVG string, or `null` when there's no
 * measured saving worth sharing (mirrors the dashboard's "no number to show"
 * empty state — we never invent one).
 */
export function shareCardSvg(m: ShareCardInput): string | null {
  if (!worthCard(m)) return null

  const pct = `~${Math.round(m.pct)}%`
  const sub = m.moneyLabel
    ? `${m.tokensLabel} tokens · ${m.moneyLabel} saved`
    : `${m.tokensLabel} tokens saved`
  const stamp = m.verified ? 'routing verified' : 'raw estimate'
  const stampColor = m.verified ? C.accent : C.subtle
  const context = `measured over ${m.queries.toLocaleString('en-US')} queries · ${stamp}`

  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="trovex saved ${esc(pct)} of doc-lookup tokens on this repo">
  <rect width="1200" height="630" fill="${C.stage}"/>
  <!-- wordmark -->
  <rect x="64" y="58" width="20" height="20" fill="${C.accent}"/>
  <text x="98" y="75" font-family="${C.mono}" font-size="28" fill="${C.fg}">trovex</text>
  <text x="1136" y="74" text-anchor="end" font-family="${C.mono}" font-size="20" fill="${C.subtle}" letter-spacing="2">SAVINGS RECEIPT</text>
  <!-- headline -->
  <text x="62" y="316" font-family="${C.sans}" font-weight="700" font-size="196" letter-spacing="-6" fill="${C.accent}">${esc(pct)}</text>
  <text x="70" y="398" font-family="${C.sans}" font-weight="700" font-size="56" letter-spacing="-1" fill="${C.fg}">fewer tokens per lookup</text>
  <!-- aggregate sub (no private fields) -->
  <text x="70" y="466" font-family="${C.mono}" font-size="30" fill="${C.muted}">${esc(sub)}</text>
  <!-- honesty context -->
  <text x="70" y="506" font-family="${C.mono}" font-size="22" fill="${stampColor}">${esc(context)}</text>
  <!-- footer -->
  <line x1="64" y1="544" x2="1136" y2="544" stroke="rgba(148,163,184,0.16)" stroke-width="1"/>
  <text x="64" y="582" font-family="${C.mono}" font-size="22" fill="${C.accent}">trovex.dev</text>
  <text x="1136" y="582" text-anchor="end" font-family="${C.mono}" font-size="20" fill="${C.subtle}">measure your own →</text>
</svg>`
}

/**
 * Build the card, rasterize to PNG client-side (canvas — no infra), trigger a
 * download. PNG because X / LinkedIn / Slack reject SVG on upload; a PNG drags
 * straight into a post, so the share loop completes. No-op (returns false) when
 * there's no measured saving worth a card. Fonts come from the page (Fira).
 */
export async function downloadShareCard(m: ShareCardInput, filename = 'trovex-savings-receipt.png'): Promise<boolean> {
  const svg = shareCardSvg(m)
  if (!svg) return false
  const svgUrl = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }))
  try {
    const img = new Image()
    img.decoding = 'async'
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('share card svg failed to load'))
      img.src = svgUrl
    })
    const scale = 2 // retina
    const canvas = document.createElement('canvas')
    canvas.width = 1200 * scale
    canvas.height = 630 * scale
    const ctx = canvas.getContext('2d')
    if (!ctx) return false
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    const png = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
    if (!png) return false
    const pngUrl = URL.createObjectURL(png)
    const a = document.createElement('a')
    a.href = pngUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(pngUrl)
    return true
  } finally {
    URL.revokeObjectURL(svgUrl)
  }
}
