#!/usr/bin/env node
/*
 * check-pii-openai — data-minimization guard, server-side (TSU-218; ports tsukumo TSU-216).
 *
 * The funnel must never send a person's NAME or full EMAIL to OpenAI. Lead/ICP enrichment may
 * send only business attributes (company / role / email-domain). This was fixed in the tsukumo
 * lead-machine (TSU-212 dokan 395, TSU-214 dokan 394) and is gated there in CI (TSU-216). This is
 * the same gate on the trovex side so a leak can't slip in via this repo's server surfaces.
 *
 * SCOPE: the server JS surfaces — web/api/* (the waitlist + Twenty webhook lead surface) and
 * web/scripts/*. NOT web/src/ (client; covered by check-no-client-secrets) and NOT the Python
 * product embedder in ../src/trovex (that embeds the USER's own code/docs on the user's own key by
 * design — product behaviour, not lead PII). Override roots with GUARD_ROOTS="a,b".
 *
 * DETECTOR (the exact leak shape, low false-positive): in a file that calls OpenAI
 * (api.openai.com / OPENAI_API_KEY / chat/completions / embeddings), flag a PII LABEL bound to a
 * template interpolation — `name: ${...}` / `email: ${...}` / `firstName: ${...}`. Ignores the
 * legit uses: `Hi ${name}` (greeting), a `firstName:` object literal, `email_domain: ${...}`.
 *
 * Wired into `npm run build` like the other check-*.mjs guards. Exit 1 (red) on a finding.
 * No deps, no secrets — pure Node fs over the checked-out tree.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, extname } from 'node:path'

const ROOTS = (process.env.GUARD_ROOTS || 'api,scripts').split(',').map((s) => s.trim()).filter(Boolean)
const EXTS = new Set(['.mjs', '.cjs', '.js', '.mts', '.ts'])
const SKIP_DIR = /(^|\/)(node_modules|\.next|dist|\.git)(\/|$)/
const SKIP_FILE = /check-pii-openai\.mjs$/ // this guard necessarily contains the markers + self-test literals

const USES_OPENAI = /api\.openai\.com|OPENAI_API_KEY|chat\/completions|\/v1\/embeddings|text-embedding/i
// A PII field NAME used as a labelled fact fed into a template interpolation. `email_domain:` is
// excluded by the `(?!_?domain)` guard (business attribute, not the person).
const PII_LABEL = /[`'"]\s*(name|first[_ ]?name|last[_ ]?name|full[_ ]?name|email(?!_?domain)|e-mail)\s*:\s*\$\{/i

function walk(dir, out) {
  let entries
  try { entries = readdirSync(dir) } catch { return }
  for (const name of entries) {
    const p = join(dir, name)
    if (SKIP_DIR.test(p)) continue
    let st
    try { st = statSync(p) } catch { continue }
    if (st.isDirectory()) walk(p, out)
    else if (EXTS.has(extname(p)) && !SKIP_FILE.test(p)) out.push(p)
  }
}

// SELF-TEST: prove the detector is armed before trusting a CLEAN verdict.
const armed =
  PII_LABEL.test('`name: ${lead.name}`') &&
  PII_LABEL.test('`email: ${l.email}`') &&
  !PII_LABEL.test('`Hi ${name}, thanks`') &&
  !PII_LABEL.test('`email_domain: ${lead.companyDomain}`') &&
  !PII_LABEL.test('`company: ${lead.company}`')
if (!armed) {
  console.error('check-pii-openai: DETECTOR DISARMED — self-test failed. Aborting (won\'t trust a CLEAN result).')
  process.exit(2)
}

const files = []
for (const root of ROOTS) walk(root, files)

const openaiFiles = []
const findings = []
for (const file of files) {
  let src
  try { src = readFileSync(file, 'utf8') } catch { continue }
  if (!USES_OPENAI.test(src)) continue
  openaiFiles.push(file)
  src.split('\n').forEach((line, i) => {
    if (PII_LABEL.test(line)) findings.push({ file, line: i + 1, snippet: line.trim().slice(0, 160) })
  })
}

console.log(`check-pii-openai: scanned ${files.length} files under [${ROOTS.join(', ')}], ${openaiFiles.length} call OpenAI.`)
if (openaiFiles.length) console.log(`  OpenAI-using: ${openaiFiles.join(', ')}`)

if (findings.length) {
  console.error(`\n❌ PII→OpenAI leak: ${findings.length} PII label(s) interpolated into an LLM prompt:`)
  for (const f of findings) console.error(`   ${f.file}:${f.line}  ${f.snippet}`)
  console.error('\nData-minimization: never send a person\'s name or full email to OpenAI.')
  console.error('Send only business attributes (company / role / email-domain). Strip the field above.')
  process.exit(1)
}

console.log('✅ CLEAN — no OpenAI-using server source interpolates a PII label (name/full-email) into a prompt.')
