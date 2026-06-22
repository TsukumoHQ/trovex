#!/usr/bin/env node
/*
 * Sitemap guard — keeps sitemap.xml in lockstep with the static pages.
 *
 * The marketing pages are hand-authored static HTML under public/ (no generator),
 * so it's easy to add a page and forget the sitemap, or delete one and leave a
 * dead <loc>. This check, wired into `npm run build`, fails the deploy on either.
 *
 * Canonical pages = directory-style index.html (served at a trailing-slash URL) +
 * the root. 404.html and other non-index html are excluded.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const PUB = 'public'
// Routes served by a vercel rewrite to a function (vercel.json), NOT a public/ file,
// so the walker below can't see them. They are real, indexable URLs and belong in the
// sitemap — list them here so the guard treats them as live pages, not dead <loc>s.
//   /savings → /api/savings (serves the built savings.html calculator shell)
const REWRITES = ['/savings']
const pages = new Set(['/', ...REWRITES])
function walk(dir) {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e)
    if (statSync(p).isDirectory()) { walk(p); continue }
    if (e === 'index.html') {
      const url = '/' + p.slice(PUB.length + 1).replace(/index\.html$/, '')
      pages.add(url)
    }
  }
}
walk(PUB)

const sm = readFileSync(join(PUB, 'sitemap.xml'), 'utf8')
const locs = new Set([...sm.matchAll(/<loc>https:\/\/trovex\.dev([^<]*)<\/loc>/g)].map((m) => m[1]))

const missing = [...pages].filter((u) => !locs.has(u)).sort()
const dead = [...locs].filter((u) => !pages.has(u)).sort()

if (missing.length || dead.length) {
  console.error('\n✗ Sitemap guard FAILED: sitemap.xml is out of sync with public/.')
  if (missing.length) { console.error('  Pages missing from sitemap.xml:'); missing.forEach((u) => console.error('    ' + u)) }
  if (dead.length) { console.error('  <loc> entries with no page on disk:'); dead.forEach((u) => console.error('    ' + u)) }
  console.error('')
  process.exit(1)
}
console.log(`✓ Sitemap guard: ${pages.size} pages, all in sitemap.xml, no dead entries.`)
