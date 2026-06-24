#!/usr/bin/env node
/*
 * Install-affordance guard — keeps the install command on every discovery/comparison page.
 *
 * The /vs, /answers, /glossary content pages are our GEO/AEO discovery surface: a dev
 * arrives from an AI-engine citation or a comparison search. Each one must let them
 * install IN PLACE (the canonical `uv tool install …` command), not bounce to the
 * landing — that's the activation lever (PRs #381, #399). This was hand-applied across
 * 34 pages; without a guard, a NEW page added later silently ships without the install
 * affordance and the conversion surface regresses.
 *
 * This check, wired into `npm run build`, fails the deploy if any CONTENT page (a
 * subdirectory index.html under the watched sections) lacks the install command.
 * Section hub pages (e.g. /vs/index.html) are listing/nav pages and are exempt.
 *
 * Deterministic, no deps.
 */
import { readdirSync, readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const PUB = 'public'
const SECTIONS = ['vs', 'answers', 'glossary']
// The canonical install command (must match the landing / README / llms.txt).
const INSTALL = 'uv tool install trovex'

const missing = []
let checked = 0

for (const section of SECTIONS) {
  const base = join(PUB, section)
  if (!existsSync(base)) { console.error(`✗ install-cta guard: section missing: ${base}`); process.exit(1) }
  for (const entry of readdirSync(base, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue // skips the section hub index.html (a listing page)
    const f = join(base, entry.name, 'index.html')
    if (!existsSync(f)) continue
    checked++
    if (!readFileSync(f, 'utf8').includes(INSTALL)) missing.push(`${section}/${entry.name}`)
  }
}

if (missing.length) {
  console.error(`✗ install-cta guard: ${missing.length} discovery page(s) missing the install command:`)
  for (const m of missing) console.error(`    ${m} — add the install block before its .cta-row (see /vs pattern)`)
  process.exit(1)
}

console.log(`✓ install-cta guard: ${checked} discovery pages, all carry the install command.`)
