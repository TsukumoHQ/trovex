/**
 * /blog/* routing after the blog moved off trovex.dev (it lives only on tsukumo.ch
 * — repo-surface-map). cmo's call flipped DROP → MIGRATE: the trovex-original posts
 * get republished on tsukumo and 301'd per-slug.
 *
 * REPUBLISH-GATED: a slug only goes in MIGRATED once its tsukumo post is verified
 * LIVE (a real 200, not the "Post not found" soft-404). 301'ing to a soft-404 is
 * the exact content-loss bug we already fixed once — never add a slug here blind.
 *
 *   - slug in MIGRATED      → 301 to its tsukumo post (permanent; post exists).
 *   - any other /blog/*     → 307 to the tsukumo blog INDEX (temporary; the post
 *                             isn't republished yet, or there's no 1:1 target).
 *
 * Wired via web/vercel.json: rewrite /blog/(.*) -> /api/blog-gone?path=$1 (a
 * rewrite, so the status is served at the original /blog/<slug> URL). /blog/(.*)
 * not :path* — the old indexed URLs had trailing slashes that :path* misses.
 */

// slug → live tsukumo URL. Add a slug ONLY after curl-confirming the target is a
// real 200 post (not soft-404). Empty until content republishes the originals.
const MIGRATED = {
  // Republished + verified LIVE (200) on tsukumo 2026-06-23 — 1:1 same-slug.
  'the-token-cost-of-agents-rereading-docs': 'https://tsukumo.ch/blog/the-token-cost-of-agents-rereading-docs',
  'mcp-context-patterns-for-coding-agents': 'https://tsukumo.ch/blog/mcp-context-patterns-for-coding-agents',
  'one-source-of-truth-for-a-fleet-of-agents': 'https://tsukumo.ch/blog/one-source-of-truth-for-a-fleet-of-agents',
  'local-first-vs-cloud-rag-for-agent-context': 'https://tsukumo.ch/blog/local-first-vs-cloud-rag-for-agent-context',
}

export default function handler(req, res) {
  const raw = Array.isArray(req.query?.path) ? req.query.path.join('/') : (req.query?.path || '')
  const slug = String(raw).split('/')[0].split('?')[0].trim().toLowerCase()

  const target = MIGRATED[slug]
  if (target) {
    res.statusCode = 301
    res.setHeader('Location', target)
    res.setHeader('Cache-Control', 'public, max-age=3600')
    res.end()
    return
  }
  // Not yet migrated → temporary redirect to the canonical blog index on tsukumo.
  res.statusCode = 307
  res.setHeader('Location', 'https://tsukumo.ch/blog')
  res.setHeader('Cache-Control', 'public, max-age=300')
  res.end()
}
