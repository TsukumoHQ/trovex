#!/usr/bin/env node
/*
 * Tsukumo affiliation sync — one signature + one suite footer on every static page.
 *
 * Audit 2026-10-13 TR-01/TR-02: the editorial pages (/answers, /vs, /for, /use-cases,
 * /glossary, /measure, /method) are hand-authored static HTML with no shared template,
 * so the affiliation drifted page by page. The SSOT is src/suite.json (the React
 * landing + /savings import it directly); this script renders it into public/ between
 * marker comments:
 *
 *   topbar  : <!-- tsukumo:sig -->…<!-- /tsukumo:sig -->     right after the brand link
 *   footer  : <!-- tsukumo:suite -->…<!-- /tsukumo:suite -->  last child of footer .wrap
 *
 *   node scripts/sync-suite.mjs          rewrite every page (idempotent)
 *   node scripts/sync-suite.mjs --check  fail (exit 1) if any page is missing or drifted
 *
 * `npm run build` runs --check, so a new page without the blocks, or a hand-edit of a
 * block, fails the deploy instead of shipping. Deterministic, no deps.
 */
import { readdirSync, readFileSync, writeFileSync, statSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const WEB = join(here, '..')
const PUB = join(WEB, 'public')
const suite = JSON.parse(readFileSync(join(WEB, 'src', 'suite.json'), 'utf8'))
const CHECK = process.argv.includes('--check')

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const ext = (href) => (/^https?:/.test(href) ? ' target="_blank" rel="noopener noreferrer"' : '')
const link = (href, label, cls = '') => `<a${cls ? ` class="${cls}"` : ''} href="${esc(href)}"${ext(href)}>${esc(label)}</a>`

const SIG_OPEN = '<!-- tsukumo:sig -->'
const SIG_CLOSE = '<!-- /tsukumo:sig -->'
const SUITE_OPEN = '<!-- tsukumo:suite -->'
const SUITE_CLOSE = '<!-- /tsukumo:suite -->'

export function sigHtml() {
  return `${SIG_OPEN}${link(suite.signature.href, suite.signature.label, 'tsk-sig')}${SIG_CLOSE}`
}

export function suiteHtml(indent = '      ') {
  const items = suite.products.map((p) => {
    const note = [p.role, p.status].filter(Boolean).join(', ')
    return `${indent}    <li>${link(p.href, p.name)} <span class="tsk-note">${esc(note)}</span></li>`
  })
  const community = suite.community.href
  return [
    `${indent}${SUITE_OPEN}`,
    `${indent}<nav class="tsk-suite" aria-label="Tsukumo suite">`,
    `${indent}  ${link(suite.signature.href, suite.signature.label, 'tsk-sig')}`,
    `${indent}  <ul>`,
    ...items,
    `${indent}  </ul>`,
    `${indent}  <p class="tsk-meta">${link(community, suite.community.label)} · ${link(suite.publisher.href, suite.publisher.label)} · ${link('https://tsukumo.ch/privacy', 'privacy')}</p>`,
    `${indent}</nav>`,
    `${indent}${SUITE_CLOSE}`,
  ].join('\n')
}

const reBlock = (open, close) =>
  new RegExp(`[ \\t]*${open.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')}[\\s\\S]*?${close.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')}`)

export function apply(html) {
  let out = html
  // 1. signature in the topbar, right after the brand link.
  if (out.includes(SIG_OPEN)) {
    out = out.replace(reBlock(SIG_OPEN, SIG_CLOSE), (m) => m.match(/^[ \t]*/)[0] + sigHtml())
  } else {
    const topbar = /(<header class="topbar">\s*<div class="wrap">\s*<a class="brand" href="\/">trovex<\/a>)/
    if (!topbar.test(out)) return { html: out, error: 'no topbar brand anchor' }
    out = out.replace(topbar, (m) => `${m}\n      ${sigHtml()}`)
  }
  // 2. suite block as the last child of the footer .wrap.
  if (out.includes(SUITE_OPEN)) {
    out = out.replace(reBlock(SUITE_OPEN, SUITE_CLOSE), suiteHtml())
  } else {
    const foot = /(<footer>\s*<div class="wrap">[\s\S]*?)(\n[ \t]*<\/div>\s*<\/footer>)/
    if (!foot.test(out)) return { html: out, error: 'no footer .wrap' }
    out = out.replace(foot, (_, body, tail) => `${body}\n${suiteHtml()}${tail}`)
  }
  return { html: out }
}

function walk(dir, acc = []) {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e)
    if (statSync(p).isDirectory()) walk(p, acc)
    else if (p.endsWith('.html')) acc.push(p)
  }
  return acc
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]
if (isMain) {
  const drift = []
  const errors = []
  let n = 0
  for (const f of walk(PUB)) {
    const src = readFileSync(f, 'utf8')
    const { html, error } = apply(src)
    n++
    if (error) { errors.push(`${f.slice(WEB.length + 1)}: ${error}`); continue }
    if (html !== src) {
      if (CHECK) drift.push(f.slice(WEB.length + 1))
      else writeFileSync(f, html)
    }
  }
  if (errors.length || drift.length) {
    if (errors.length) {
      console.error(`✗ suite guard: ${errors.length} page(s) without the shared topbar/footer shape:`)
      for (const e of errors) console.error('    ' + e)
    }
    if (drift.length) {
      console.error(`✗ suite guard: ${drift.length} page(s) missing or drifted from src/suite.json:`)
      for (const d of drift) console.error('    ' + d)
      console.error('  fix: node scripts/sync-suite.mjs')
    }
    process.exit(1)
  }
  console.log(`✓ suite guard: ${n} static pages ${CHECK ? 'carry' : 'synced to'} the Tsukumo signature + suite footer.`)
}
