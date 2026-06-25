#!/usr/bin/env node
/*
 * Brand guard — prevents the recurring "Synergix" leak at the source.
 *
 * Rule (memory 'no-synergix-mention'): trovex is the ONLY brand on public
 * surfaces. There is no page generator for the marketing pages (they are
 * hand-authored static HTML under public/), so the durable fix is this check,
 * wired into `npm run build` — any deploy that reintroduces the brand name fails.
 *
 * Canonical footer: `© 2026 trovex · one source of truth for your agents' docs`.
 *
 * Allowed exception: the GitHub org token in github.com/TsukumoHQ URLs and the
 * io.github.tsukumohq MCP-registry namespace (unavoidable technical identifiers).
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

// Also scan the FastAPI server-rendered templates — the public install page lives
// here (src/trovex/templates), NOT under web/, which is the gap that let the install-page
// synergix leak slip past this guard. Path is relative to web/ (this script's CI cwd).
const ROOTS = ['public', 'src', 'index.html', '../src/trovex/templates']
const SCAN = /\.(html|txt|json|webmanifest|tsx?|jsx?|css)$/
// Strip the allowed technical identifiers before scanning for the brand word.
const ALLOW = /(github\.com\/TsukumoHQ|TsukumoHQ\/[\w.-]+|io\.github\.tsukumohq)/gi
const offenders = []

function scan(p) {
  let st
  try { st = statSync(p) } catch { return }
  if (st.isDirectory()) {
    if (/node_modules|dist/.test(p)) return
    for (const e of readdirSync(p)) scan(join(p, e))
    return
  }
  if (!SCAN.test(p)) return
  const cleaned = readFileSync(p, 'utf8').replace(ALLOW, '')
  cleaned.split('\n').forEach((line, i) => {
    if (/synergix/i.test(line)) offenders.push(`${p}:${i + 1}: ${line.trim().slice(0, 120)}`)
  })
}

for (const r of ROOTS) scan(r)

if (offenders.length) {
  console.error('\n✗ Brand guard FAILED: "Synergix" found on a public surface.')
  console.error('  trovex is the only public brand. Use "trovex" (canonical footer: "© 2026 trovex").')
  console.error('  Only allowed use is the github.com/TsukumoHQ repo URL / io.github.tsukumohq namespace.\n')
  for (const o of offenders) console.error('  ' + o)
  console.error('')
  process.exit(1)
}
console.log('✓ Brand guard: no "Synergix" on public surfaces.')
