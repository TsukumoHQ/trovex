#!/usr/bin/env node
/*
 * Voice guard — stops AI-slop and non-canonical blog links at the merge, not the
 * morning after.
 *
 * The marketing pages are hand-authored static HTML under public/ (no generator,
 * same as check-brand). This guard, wired into `npm run build`, fails any deploy
 * whose shipped copy reintroduces a banned slop word or a trovex.dev/blog link
 * (the blog lives only on tsukumo.ch — repo-surface-map / check-no-blog).
 *
 * Scope = web/public + index.html ONLY (the shipped surface). The repo README is
 * deliberately out of scope: its one known trovex.dev/blog link is republish-gated
 * (the deep-link waits on the tsukumo post) and is tracked by the daily dokan
 * voice-guard monitor instead — gating it here would red-light every merge.
 *
 * The banned list mirrors the content-lead voice canon (memory 'voice').
 */
import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const ROOTS = ['public', 'index.html']
const SCAN = /\.(html|txt)$/

// Banned slop words — cleanly + deterministically detectable only.
const BANNED = [
  /\brevolutionary\b/i,
  /\bseamless(?:ly)?\b/i,
  /\bsupercharges?\b/i,
  /\bsupercharged\b/i,
  /\bunlocks?\b/i,
  /\bunlocked\b/i,
  /\bunlocking\b/i,
  /\bAI[-\s]powered\b/i,
  /\bgame[-\s]chang(?:er|ing)\b/i,
  /\bcutting[-\s]edge\b/i,
]
// The blog lives ONLY at tsukumo.ch/blog. Any trovex.dev/blog link in shipped copy = drift.
const NON_CANONICAL_BLOG = /trovex\.dev\/blog/i

const offenders = []

function scan(p) {
  let st
  try { st = statSync(p) } catch { return }
  if (st.isDirectory()) {
    if (/node_modules|dist|assets/.test(p)) return
    for (const e of readdirSync(p)) scan(join(p, e))
    return
  }
  if (!SCAN.test(p)) return
  readFileSync(p, 'utf8').split('\n').forEach((line, i) => {
    for (const re of BANNED) {
      const m = line.match(re)
      if (m) offenders.push(`${p}:${i + 1}: banned "${m[0]}" — ${line.trim().slice(0, 100)}`)
    }
    if (NON_CANONICAL_BLOG.test(line)) {
      offenders.push(`${p}:${i + 1}: trovex.dev/blog link — point it to https://tsukumo.ch/blog`)
    }
  })
}

for (const r of ROOTS) if (existsSync(r)) scan(r)

if (offenders.length) {
  console.error('\n✗ Voice guard FAILED — slop or non-canonical blog link in shipped copy:')
  console.error('  Banned: revolutionary / seamless / supercharge / unlock / AI-powered /')
  console.error('  game-changer / cutting-edge. Blog links go to tsukumo.ch/blog.\n')
  for (const o of offenders) console.error('  ' + o)
  console.error('')
  process.exit(1)
}
console.log('✓ Voice guard: no banned slop words or trovex.dev/blog links in shipped copy.')
