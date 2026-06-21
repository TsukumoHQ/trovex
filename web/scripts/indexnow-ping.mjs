#!/usr/bin/env node
/*
 * IndexNow ping — nudges Bing + Yandex (and IndexNow-participating engines) to recrawl
 * changed trovex.dev pages. No GSC, no secret: the key file at the domain root IS the auth.
 *
 * Setup (already in repo):
 *   - Key file: web/public/<KEY>.txt  (served at https://trovex.dev/<KEY>.txt)
 *   - This script reads the key from that file automatically.
 *
 * Usage (run AFTER deploy, once the changed pages + key file are live):
 *   node scripts/indexnow-ping.mjs                 # ping every URL in sitemap.xml
 *   node scripts/indexnow-ping.mjs /glossary/ /answers/canonical-context-for-agents/
 *                                                   # ping only these paths/URLs
 *   node scripts/indexnow-ping.mjs --dry           # print payload, do not submit
 *
 * Cadence: run after each batch of page changes deploys (part of the GEO reindex cadence).
 * IndexNow dedupes + rate-limits server-side; pinging the full sitemap is safe.
 */
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const HOST = 'trovex.dev'
const ORIGIN = `https://${HOST}`
const ENDPOINT = 'https://api.indexnow.org/indexnow'
const PUB = new URL('../public/', import.meta.url).pathname

function findKey() {
  const f = readdirSync(PUB).find((n) => /^[a-f0-9]{8,128}\.txt$/i.test(n))
  if (!f) throw new Error('IndexNow key file (web/public/<hex>.txt) not found')
  return { key: readFileSync(join(PUB, f), 'utf8').trim(), keyLocation: `${ORIGIN}/${f}` }
}

function sitemapUrls() {
  const xml = readFileSync(join(PUB, 'sitemap.xml'), 'utf8')
  return [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1].trim())
}

function normalize(arg) {
  if (arg.startsWith('http')) return arg
  return ORIGIN + (arg.startsWith('/') ? arg : '/' + arg)
}

const args = process.argv.slice(2)
const dry = args.includes('--dry')
const explicit = args.filter((a) => !a.startsWith('--'))
const urlList = explicit.length ? explicit.map(normalize) : sitemapUrls()
const { key, keyLocation } = findKey()
const payload = { host: HOST, key, keyLocation, urlList }

console.log(`IndexNow: ${urlList.length} URL(s), key ${key.slice(0, 8)}…, keyLocation ${keyLocation}`)
if (dry) { console.log(JSON.stringify(payload, null, 2)); process.exit(0) }

const res = await fetch(ENDPOINT, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json; charset=utf-8' },
  body: JSON.stringify(payload),
})
const body = await res.text()
console.log(`IndexNow response: ${res.status} ${res.statusText}${body ? ' — ' + body.slice(0, 200) : ''}`)
// 200 = accepted, 202 = accepted/pending. Anything else is a real failure.
process.exit(res.status === 200 || res.status === 202 ? 0 : 1)
