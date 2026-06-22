#!/usr/bin/env node
/*
 * No-blog guard — trovex.dev must NEVER ship a blog.
 *
 * The blog lives only on tsukumo.ch (repo-surface-map). trovex.dev/blog once
 * duplicated it (SEO/GEO self-harm) and was killed + 301'd to tsukumo. This guard,
 * wired into `npm run build`, makes resurrection impossible: any stale branch that
 * re-adds the blog (public/blog/, a /blog sitemap entry, or an internal /blog link)
 * fails the build before it can deploy. Links to https://tsukumo.ch/blog are fine.
 */
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const PUB = 'public'
const errors = []

// 1. No served blog directory.
if (existsSync(join(PUB, 'blog'))) {
  errors.push('public/blog/ exists — delete it (the blog is tsukumo.ch only).')
}

// 2. No /blog entry in the sitemap.
const sm = readFileSync(join(PUB, 'sitemap.xml'), 'utf8')
const blogLocs = [...sm.matchAll(/<loc>https:\/\/trovex\.dev(\/blog[^<]*)<\/loc>/g)].map((m) => m[1])
if (blogLocs.length) {
  errors.push('sitemap.xml has /blog entries: ' + blogLocs.join(', '))
}

// 3. No INTERNAL /blog links (href="/blog..."). Absolute tsukumo links are allowed.
const htmlFiles = []
function walk(dir) {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e)
    if (statSync(p).isDirectory()) walk(p)
    else if (e.endsWith('.html')) htmlFiles.push(p)
  }
}
walk(PUB)
const INTERNAL_BLOG = /href=["']\/blog\b/
for (const f of [...htmlFiles, 'src/App.tsx']) {
  if (!existsSync(f)) continue
  const src = readFileSync(f, 'utf8')
  src.split('\n').forEach((line, i) => {
    if (INTERNAL_BLOG.test(line)) errors.push(`${f}:${i + 1} internal /blog link — point it to https://tsukumo.ch/blog`)
  })
}

if (errors.length) {
  console.error('\n✗ No-blog guard FAILED — the blog belongs to tsukumo.ch only:')
  errors.forEach((e) => console.error('  ' + e))
  console.error('')
  process.exit(1)
}
console.log(`✓ No-blog guard: no /blog dir, sitemap entry, or internal /blog link.`)
