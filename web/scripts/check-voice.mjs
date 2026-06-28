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
 * Scope:
 *   - Slop words + non-canonical blog links: web/public + index.html (html/txt),
 *     the static shipped surface. The repo README is deliberately out of scope: its
 *     one known trovex.dev/blog link is republish-gated and is tracked by the daily
 *     dokan voice-guard monitor instead — gating it here would red-light every merge.
 *   - Em-dash (U+2014): the LANDING copy surface only — web/src (the React landing +
 *     /savings + /audit) plus the per-tool HTML entries (index/savings/audit.html).
 *     This closes the gap that let em-dashes ship on the landing (TSU-139): the old
 *     scope never looked at web/src or the *.html entries. It is deliberately NOT
 *     applied to the broader public/ corpus (llms.txt, /vs comparison pages, svgs) —
 *     that is geo/content's lane and carries intentional em-dashes; policing it here
 *     would red-light unrelated merges. Comments are stripped before the scan, and
 *     the dashboard 'no-value' glyph (a standalone — between tags) is allowed. The
 *     en-dash ranges we ship (41–81%, U+2013) are a different character and never
 *     match the em-dash check.
 *
 * The banned list mirrors the content-lead voice canon (memory 'voice').
 */
import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs'
import { join } from 'node:path'

// Slop + blog-link scope (unchanged: the static public surface).
const ROOTS = ['public', 'index.html']
const SCAN = /\.(html|txt)$/

// Em-dash scope: the landing copy surface (React src + per-tool HTML entries).
const EMDASH_ROOTS = ['src', 'index.html', 'savings.html', 'audit.html']
const EMDASH_SCAN = /\.(tsx?|jsx?|html)$/
const EM_DASH = /—/
// Allow a standalone em-dash glyph (the dashboard 'no-value' cell, e.g.
// <span className="num">—</span>) or one written as a lone string literal —
// never prose. Prose em-dashes sit between words/spaces, not between tags.
const GLYPH_ALLOW = /(>\s*—\s*<)|(['"`]—['"`])|(\{\s*['"`]—['"`]\s*\})/

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

// Blank out comments (JS/TS block + line, JSX {/* */}, HTML <!-- -->) while
// preserving newlines + column counts, so em-dashes in comments do not trip the
// guard and line numbers in offenses stay accurate.
function stripComments(src) {
  src = src.replace(/\r/g, '') // normalize CRLF so line-end anchors are reliable
  src = src.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' ')) // /* */ and {/* */}
  src = src.replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' ')) // <!-- -->
  src = src
    .split('\n')
    .map((l) => l.replace(/(^|[^:])\/\/.*/, '$1')) // // line comments, but keep :// in URLs
    .join('\n')
  return src
}

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

function scanEmDash(p) {
  let st
  try { st = statSync(p) } catch { return }
  if (st.isDirectory()) {
    if (/node_modules|dist|assets/.test(p)) return
    for (const e of readdirSync(p)) scanEmDash(join(p, e))
    return
  }
  if (!EMDASH_SCAN.test(p)) return
  stripComments(readFileSync(p, 'utf8')).split('\n').forEach((line, i) => {
    if (EM_DASH.test(line) && !GLYPH_ALLOW.test(line)) {
      offenders.push(`${p}:${i + 1}: em-dash (use a comma/colon/period, or an en-dash for ranges) — ${line.trim().slice(0, 100)}`)
    }
  })
}

for (const r of ROOTS) if (existsSync(r)) scan(r)
for (const r of EMDASH_ROOTS) if (existsSync(r)) scanEmDash(r)

if (offenders.length) {
  console.error('\n✗ Voice guard FAILED — slop, non-canonical blog link, or em-dash in shipped copy:')
  console.error('  Banned: revolutionary / seamless / supercharge / unlock / AI-powered /')
  console.error('  game-changer / cutting-edge. Blog links go to tsukumo.ch/blog.')
  console.error('  Em-dash: zero in shipped landing copy — use a comma/colon/period.\n')
  for (const o of offenders) console.error('  ' + o)
  console.error('')
  process.exit(1)
}
console.log('✓ Voice guard: no banned slop words, trovex.dev/blog links, or em-dashes in shipped copy.')
