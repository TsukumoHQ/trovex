#!/usr/bin/env node
/*
 * Internal-link + silo guard — keeps the /answers, /vs, /glossary silo intact.
 *
 * The marketing/AEO pages are hand-authored static HTML under public/ (no generator),
 * so a renamed or typo'd cross-link silently 404s — a dead internal link breaks both the
 * crawl path AND the topical silo that earns GEO/AEO citations. This check, wired into
 * `npm run build`, fails the deploy on:
 *   1. DEAD LINK  — an internal href that resolves to no file on disk.
 *   2. SILO ORPHAN — a content page (/answers, /vs, /glossary) that cross-links no sibling
 *      content page, so it sits outside the internal-link silo.
 *
 * Deterministic, no deps. Internal = href starting "/" or "https://trovex.dev/". External,
 * mailto:, tel:, and pure "#frag" anchors are ignored.
 */
import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const PUB = 'public'
const SILO = ['answers', 'vs', 'glossary'] // sections that must form an internal-link silo

// --- collect every hand-authored page ---
const htmlFiles = []
function walk(dir) {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e)
    if (statSync(p).isDirectory()) { walk(p); continue }
    if (e === 'index.html') htmlFiles.push(p)
  }
}
walk(PUB)

// Resolve an internal URL path (no host, no query/fragment) to the file it must serve.
// Returns the disk path that has to exist, or null if the link is malformed.
function resolveTarget(urlPath) {
  let p = urlPath.split('#')[0].split('?')[0]
  if (p === '' || p === '/') return join(PUB, 'index.html')
  if (p.endsWith('/')) return join(PUB, p, 'index.html')
  // has a file extension → an asset/file served verbatim
  if (/\.[a-z0-9]+$/i.test(p)) return join(PUB, p)
  // extensionless, no trailing slash (e.g. /for) → accept dir-index or a bare file
  if (existsSync(join(PUB, p, 'index.html'))) return join(PUB, p, 'index.html')
  return join(PUB, p)
}

// Pull internal hrefs out of one HTML file.
function internalHrefs(html) {
  const out = []
  for (const m of html.matchAll(/href="([^"]+)"/g)) {
    let h = m[1]
    if (h.startsWith('https://trovex.dev')) h = h.slice('https://trovex.dev'.length) || '/'
    if (!h.startsWith('/')) continue // external, mailto:, tel:, bare #frag
    out.push(h)
  }
  return out
}

// Is this URL path a SILO content page (…/answers/<slug>/, not the bare hub)?
function siloPageOf(urlPath) {
  const m = urlPath.split('#')[0].split('?')[0].match(/^\/(answers|vs|glossary)\/([^/]+)\/?$/)
  return m && m[2] ? `${m[1]}/${m[2]}` : null
}

const deadLinks = []   // { from, href }
const orphans = []     // page id with no sibling cross-link

for (const file of htmlFiles) {
  const urlPath = '/' + file.slice(PUB.length + 1).replace(/index\.html$/, '')
  const html = readFileSync(file, 'utf8')
  const hrefs = internalHrefs(html)

  // 1. dead-link check. Root "/" is the Vite SPA entry (emitted to dist/index.html, not a
  // public/ static file) — always valid, same exception the sitemap guard makes.
  for (const h of hrefs) {
    const base = h.split('#')[0].split('?')[0]
    if (base === '/' || base === '') continue
    const target = resolveTarget(h)
    if (!target || !existsSync(target)) deadLinks.push({ from: urlPath, href: h })
  }

  // 2. silo-orphan check — only for the silo content pages themselves
  const self = siloPageOf(urlPath)
  if (self) {
    const links = hrefs.map(siloPageOf).filter((s) => s && s !== self)
    if (links.length === 0) orphans.push(self)
  }
}

if (deadLinks.length || orphans.length) {
  console.error('\n✗ Internal-link guard FAILED.')
  if (deadLinks.length) {
    console.error('  Dead internal links (href resolves to no file on disk):')
    deadLinks.forEach(({ from, href }) => console.error(`    ${from}  →  ${href}`))
  }
  if (orphans.length) {
    console.error('  Silo orphans (content page cross-links no sibling — wire it into the silo):')
    orphans.forEach((id) => console.error(`    /${id}/`))
  }
  console.error('')
  process.exit(1)
}
const siloCount = htmlFiles.filter((f) => siloPageOf('/' + f.slice(PUB.length + 1).replace(/index\.html$/, ''))).length
console.log(`✓ Internal-link guard: ${htmlFiles.length} pages, no dead links, ${siloCount} silo pages all cross-linked.`)
