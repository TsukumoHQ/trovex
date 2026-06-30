#!/usr/bin/env node
/*
 * Analytics-coverage guard — keeps the Plausible snippet on EVERY served HTML page.
 *
 * trovex.dev measures reach (visits, GEO/AI-engine attribution) via a first-party
 * Plausible proxy (`/js/script.js` + `/api/event`, see web/vercel.json). The loader
 * lives in each page's <head>; loading it fires an automatic pageview that captures
 * the referrer + UTM — that's how a session arriving from an AI-engine citation onto a
 * /answers or /glossary page becomes a measured, attributed visit.
 *
 * The snippet was hand-applied per page, so a NEW page (or a whole section — /answers,
 * /glossary, /use-cases were ALL missing it pre-PR) silently ships with ZERO analytics:
 * its traffic is invisible and the north-star reach number reads low precisely on the
 * GEO/AEO surface AI engines cite most. This guard, wired into `npm run build`, fails
 * the deploy if any served HTML page under public/ lacks the loader. No deps.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const PUB = 'public'
// Must match the first-party loader src in index.html / vercel.json rewrites.
const LOADER = '/js/script.js'

function htmlFiles(dir) {
  const out = []
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name)
    if (e.isDirectory()) out.push(...htmlFiles(p))
    else if (e.name.endsWith('.html')) out.push(p)
  }
  return out
}

const files = htmlFiles(PUB)
const missing = files.filter((f) => !readFileSync(f, 'utf8').includes(LOADER))

if (missing.length) {
  console.error(`✗ analytics guard: ${missing.length} page(s) missing the Plausible loader (${LOADER}):`)
  for (const m of missing) console.error(`    ${m} — add the loader block before </head> (see /vs pattern)`)
  process.exit(1)
}

console.log(`✓ analytics guard: ${files.length} pages, all carry the Plausible loader.`)
