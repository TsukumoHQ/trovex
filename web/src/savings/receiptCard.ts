// Savings-receipt share card — the dark-social atom (design-lead).
// Pure SVG builder: client-side, no backend (matches /savings being a static page).
// Privacy-safe: AGGREGATE ONLY — no paths, repo, query, or user data on the card.
// Brand: trovex terminal-restraint — flat stage #06080d, green #22c55e, Fira,
// hard corners, one accent (matches the blog OG cards). Honesty-gated.
//
// Wiring (fullstack): on the /savings result, add a "save card" button that calls
// downloadReceiptCard({...}) — it builds the SVG from the computed memo `m` + pct
// and triggers a download. Returns/does nothing when the saving isn't worth a card.

const RECEIPT_MIN_RATIO = 0.2; // mirror Savings.tsx — below this, no card

const C = {
  stage: '#06080d',
  fg: '#e6edf3',
  muted: '#9aa6b8',
  subtle: '#74808f',
  accent: '#22c55e',
  sans: "'Fira Sans', system-ui, -apple-system, sans-serif",
  mono: "'Fira Code', ui-monospace, SFMono-Regular, Menlo, monospace",
};

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

export type ReceiptCardInput = {
  /** round(ratio*100) */
  pct: number;
  /** savedPerLookup / wouldHaveRead, 0..1 — gates the card */
  ratio: number;
  /** monthly token saving — gates the card (>0) */
  tokensPerMonth: number;
  /** humanTokens(tokensPerMonth), e.g. "2.3M" */
  tokensLabel: string;
  /** money(dollarsPerMonth), e.g. "$1,234" */
  moneyLabel: string;
};

/**
 * Build the 1200x630 share card as an SVG string, or `null` when the saving is
 * too small to be worth a receipt (mirrors the on-page honesty gate).
 */
export function receiptSvg(m: ReceiptCardInput): string | null {
  if (!(m.ratio >= RECEIPT_MIN_RATIO && m.tokensPerMonth > 0)) return null;

  const pct = `~${Math.round(m.pct)}%`;
  const sub = `${m.tokensLabel} tokens/mo · ~${m.moneyLabel}/mo`;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="trovex saves ${esc(pct)} of doc-lookup tokens">
  <rect width="1200" height="630" fill="${C.stage}"/>
  <!-- wordmark -->
  <rect x="64" y="58" width="20" height="20" fill="${C.accent}"/>
  <text x="98" y="75" font-family="${C.mono}" font-size="28" fill="${C.fg}">trovex</text>
  <text x="1136" y="74" text-anchor="end" font-family="${C.mono}" font-size="20" fill="${C.subtle}" letter-spacing="2">SAVINGS RECEIPT</text>
  <!-- headline -->
  <text x="62" y="320" font-family="${C.sans}" font-weight="700" font-size="200" letter-spacing="-6" fill="${C.accent}">${esc(pct)}</text>
  <text x="70" y="404" font-family="${C.sans}" font-weight="700" font-size="58" letter-spacing="-1" fill="${C.fg}">fewer tokens per lookup</text>
  <!-- aggregate sub (no private fields) -->
  <text x="70" y="476" font-family="${C.mono}" font-size="30" fill="${C.muted}">${esc(sub)}</text>
  <!-- footer -->
  <line x1="64" y1="544" x2="1136" y2="544" stroke="rgba(148,163,184,0.16)" stroke-width="1"/>
  <text x="64" y="582" font-family="${C.mono}" font-size="22" fill="${C.accent}">trovex.dev/savings</text>
  <text x="1136" y="582" text-anchor="end" font-family="${C.mono}" font-size="20" fill="${C.subtle}">measure your own →</text>
</svg>`;
}

/**
 * Build the card, rasterize to PNG client-side (canvas — no infra), and trigger a
 * download. PNG because X / LinkedIn / Slack reject SVG on upload; a PNG drags
 * straight into a post, so the share loop completes. No-op when gated off.
 * Resolves true if a card was produced. Fonts come from the page (Fira loaded).
 */
export async function downloadReceiptCard(m: ReceiptCardInput, filename = 'trovex-savings.png'): Promise<boolean> {
  const svg = receiptSvg(m);
  if (!svg) return false;
  const svgUrl = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }));
  try {
    const img = new Image();
    img.decoding = 'async';
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error('receipt svg failed to load'));
      img.src = svgUrl;
    });
    const scale = 2; // retina
    const canvas = document.createElement('canvas');
    canvas.width = 1200 * scale;
    canvas.height = 630 * scale;
    const ctx = canvas.getContext('2d');
    if (!ctx) return false;
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const png = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
    if (!png) return false;
    const pngUrl = URL.createObjectURL(png);
    const a = document.createElement('a');
    a.href = pngUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(pngUrl);
    return true;
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
}
