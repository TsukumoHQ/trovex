#!/usr/bin/env node
/*
 * Quickstart guard — one canonical install/index/search/serve recipe everywhere.
 *
 * Audit 2026-10-13 TR-03: the landing, the /for editor pages, the README and the docs
 * had drifted into several ways of running the same commands (`uv run trovex …` from a
 * clone vs `uv tool install` + `trovex …`, two sample paths, a zero-install `uvx` search
 * that finds nothing on a fresh machine). The SSOT is src/quickstart.json (the landing
 * imports it). Static pages and markdown can't import JSON, so this check, wired into
 * `npm run build`, fails the deploy when:
 *   - a quickstart surface is missing a canonical command it must show, or
 *   - any shipped surface still carries a stale variant (quickstart.json "stale").
 * Deterministic, no deps. Paths are relative to web/ (the build cwd).
 */
import { readdirSync, readFileSync, existsSync, statSync } from 'node:fs'
import { join } from 'node:path'

const QS = JSON.parse(readFileSync('src/quickstart.json', 'utf8'))
const decode = (s) => s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&')
const read = (p) => decode(readFileSync(p, 'utf8'))

const CORE = [QS.install, QS.index, QS.search, QS.serve]
const MD_FULL = [...CORE, QS.claudeCode, QS.claudeCodeSetup, QS.tryIndex, QS.trySearch]

/** surface → commands it must carry */
const REQUIRED = {
  '../README.md': MD_FULL,
  '../docs/quickstart.md': MD_FULL,
  'public/for/index.html': [QS.install, QS.index, QS.serve, QS.mcpUrl],
  'public/for/fleet/index.html': [QS.install, QS.index, QS.serve, QS.mcpUrl],
  'public/for/claude-code/index.html': [...CORE, QS.claudeCode, QS.claudeCodeSetup],
}
for (const ed of ['cursor', 'windsurf', 'zed', 'cline', 'roo']) {
  REQUIRED[`public/for/${ed}/index.html`] = [...CORE, QS.mcpUrl]
}

/** where a stale variant must never ship */
function walk(dir, acc = []) {
  if (!existsSync(dir)) return acc
  for (const e of readdirSync(dir)) {
    const p = join(dir, e)
    if (statSync(p).isDirectory()) walk(p, acc)
    else if (/\.(html|txt|tsx?|md)$/.test(p) && !p.endsWith('quickstart.json')) acc.push(p)
  }
  return acc
}
const STALE_SCOPE = [...walk('public'), ...walk('src'), 'index.html', '../README.md', '../docs/quickstart.md', '../docs/beta-welcome.md']

const problems = []
let checked = 0
for (const [file, cmds] of Object.entries(REQUIRED)) {
  if (!existsSync(file)) { problems.push(`${file}: missing (a quickstart surface was moved or deleted)`); continue }
  checked++
  const body = read(file)
  for (const c of cmds) if (!body.includes(c)) problems.push(`${file}: missing canonical command \`${c}\``)
}
// The landing must render from the SSOT, not a hand-copied string.
if (!read('src/App.tsx').includes("from './quickstart.json'")) problems.push('src/App.tsx: does not import src/quickstart.json')
for (const file of STALE_SCOPE) {
  if (!existsSync(file)) continue
  const body = read(file)
  for (const bad of QS.stale) if (body.includes(bad)) problems.push(`${file}: stale variant \`${bad}\``)
}

if (problems.length) {
  console.error(`✗ quickstart guard: ${problems.length} drift(s) from src/quickstart.json:`)
  for (const p of problems) console.error('    ' + p)
  process.exit(1)
}
console.log(`✓ quickstart guard: ${checked} quickstart surfaces match src/quickstart.json; no stale variants shipped.`)
