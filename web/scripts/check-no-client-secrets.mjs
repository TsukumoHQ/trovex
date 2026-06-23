#!/usr/bin/env node
/*
 * No-client-secrets guard — the golden rule, enforced at build time.
 *
 * Server secrets (Supabase service-role, Resend/Twenty/OpenAI keys, signing secrets,
 * KV/GitHub tokens, the IP salt) live ONLY in server env (web/api/* + Vercel env). They
 * must NEVER reach the client bundle: web/src/ is shipped to browsers. This guard, wired
 * into `npm run build`, makes a leak impossible to MERGE — not just to catch in review:
 *   1. a known server-secret identifier appearing anywhere under src/
 *   2. a secret-shaped Vite var (import.meta.env.VITE_*KEY|SECRET|TOKEN…) — Vite inlines
 *      every VITE_ var into the client bundle, so a secret-shaped one is a live leak.
 * Server code (web/api/, scripts/) is out of scope — that's where secrets belong.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const ROOT = 'src'
const errors = []

// Server-only secret identifiers that must never appear in client source.
const SECRET_IDENTS = [
  'SUPABASE_SERVICE_ROLE_KEY',
  'SERVICE_ROLE',
  'RESEND_API_KEY',
  'TWENTY_API_KEY',
  'TWENTY_WEBHOOK_SECRET',
  'NEWSLETTER_CONFIRM_SECRET',
  'WAITLIST_GITHUB_TOKEN',
  'WAITLIST_KV_REST_API_TOKEN',
  'KV_REST_API_TOKEN',
  'WAITLIST_IP_SALT',
  'NOTIFY_WEBHOOK_URL',
  'OPENAI_API_KEY',
  'PERPLEXITY_API_KEY',
  'GEMINI_API_KEY',
  'SERPAPI_KEY',
]
const SECRET_RE = new RegExp(`\\b(${SECRET_IDENTS.join('|')})\\b`)

// A Vite-exposed var whose name looks like a secret (VITE_ prefix → inlined into the bundle).
const SECRET_VITE_RE = /import\.meta\.env\.(VITE_[A-Z0-9_]*(?:KEY|SECRET|TOKEN|SERVICE_ROLE|PASSWORD)[A-Z0-9_]*)/i

const SRC_EXT = /\.(ts|tsx|js|jsx|mjs|cjs)$/

const files = []
function walk(dir) {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e)
    if (statSync(p).isDirectory()) walk(p)
    else if (SRC_EXT.test(e)) files.push(p)
  }
}
walk(ROOT)

for (const f of files) {
  const src = readFileSync(f, 'utf8')
  src.split('\n').forEach((line, i) => {
    const m1 = line.match(SECRET_RE)
    if (m1) errors.push(`${f}:${i + 1} server secret '${m1[1]}' referenced in client source — move it behind a web/api/* route.`)
    const m2 = line.match(SECRET_VITE_RE)
    if (m2) errors.push(`${f}:${i + 1} secret-shaped Vite var '${m2[1]}' — VITE_* is inlined into the client bundle; never put a secret there.`)
  })
}

if (errors.length) {
  console.error('\n✗ No-client-secrets guard FAILED — a server secret must never reach the browser:')
  errors.forEach((e) => console.error('  ' + e))
  console.error('')
  process.exit(1)
}
console.log(`✓ No-client-secrets guard: scanned ${files.length} src files, no server secrets in the client bundle.`)
