/**
 * /blog/* routing after the blog was removed from trovex.dev (it lives only on
 * tsukumo.ch — repo-surface-map). cmo locked DROP for the trovex-original posts
 * that were never migrated: they return 410 Gone — the correct deindex signal
 * (a 30x just says "moved", a 410 says "this is gone", which search/AI engines
 * honor to drop the URL). Anything else under /blog/* → 308 to the canonical
 * tsukumo blog index.
 *
 * Wired via web/vercel.json: rewrite /blog/:path* -> /api/blog-gone?path=:path*
 * (a rewrite, not a redirect, so the 410 is served at the original /blog/<slug>).
 */

// The dropped trovex-original slugs (cmo DROP decision, 2026-06-22). 410 Gone.
const GONE = new Set([
  'the-token-cost-of-agents-rereading-docs',
  'mcp-context-patterns-for-coding-agents',
  'one-source-of-truth-for-a-fleet-of-agents',
])

export default function handler(req, res) {
  const raw = Array.isArray(req.query?.path) ? req.query.path.join('/') : (req.query?.path || '')
  const slug = String(raw).split('/')[0].split('?')[0].trim().toLowerCase()

  if (GONE.has(slug)) {
    res.setHeader('Cache-Control', 'public, max-age=3600')
    res.status(410).send('410 Gone — this post has been removed. See https://tsukumo.ch/blog')
    return
  }
  // Everything else under /blog/* → the canonical blog index on tsukumo.
  res.statusCode = 308
  res.setHeader('Location', 'https://tsukumo.ch/blog')
  res.setHeader('Cache-Control', 'public, max-age=3600')
  res.end()
}
