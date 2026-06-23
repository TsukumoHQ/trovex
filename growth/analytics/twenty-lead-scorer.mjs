#!/usr/bin/env node
/**
 * TWENTY LEAD SCORER — the dark-funnel TEAM signal, written into the CRM (cmo priority #1: close the
 * autonomous lead loop — capture→dedup→SCORE→surface, owner only does the final call).
 *
 * The readable team-buying signal we can compute TODAY from the CRM itself: a COMPANY email domain
 * (not a free provider) and especially **2+ people from the SAME company domain** = a team evaluating
 * trovex = high `teamIntent` (the consulting signal). This is the same intent the future savings-receipt
 * "shared from a company domain / by 2+ eng" will carry — this scorer reads it from the deduped CRM now.
 *
 * What it does: GET all Twenty persons → derive each one's email domain → cluster by domain → score:
 *   company domain (+40) · 2+ persons same domain = TEAM (+40) · has a linked opportunity (+20).
 *   teamIntent := domain cluster ≥ 2 (a team, not a solo dev). Free-provider / no-email → unscored.
 * `--write` PATCHes `teamIntent=true` on the cluster members (never downgrades an existing true).
 *
 * HONEST: reads only the CRM's own data; no fabrication; thin data reads thin. Free email (gmail/etc)
 * is NOT a company signal — left unscored, not guessed. PII stays in Twenty; this prints only domains +
 * counts + first names for the operator, never full emails.
 *
 * Creds: TWENTY_BASE_URL + TWENTY_API_KEY (env; leak-safe in dokan, mem dokan-secret-injection).
 * Cloudflare blocks non-browser UA (1010) → Mozilla UA.
 *
 * Usage:  node growth/analytics/twenty-lead-scorer.mjs           # dry report (no writes)
 *         node growth/analytics/twenty-lead-scorer.mjs --write   # set teamIntent on team clusters
 */
const BASE = process.env.TWENTY_BASE_URL, KEY = process.env.TWENTY_API_KEY;
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36";
// Runs on dokan (no host runs): write flag via DOKAN_INPUT {"write":true} (env JSON), or --write on argv.
let DOKAN_IN = {};
try { DOKAN_IN = JSON.parse(process.env.DOKAN_INPUT || "{}"); } catch { DOKAN_IN = {}; }
const WRITE = process.argv.includes("--write") || DOKAN_IN.write === true;
const FREE = new Set(["gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "yahoo.fr", "proton.me", "protonmail.com", "icloud.com", "me.com", "gmx.ch", "gmx.com", "bluewin.ch", "hispeed.ch", "live.com", "aol.com", "pm.me"]);

async function tw(path, init) {
  if (!BASE || !KEY) return null;
  try {
    const r = await fetch(`${BASE}${path}`, { ...init, headers: { Authorization: `Bearer ${KEY}`, "User-Agent": UA, "Content-Type": "application/json", Accept: "application/json", ...(init?.headers || {}) } });
    if (!r.ok) return null;
    return r.json();
  } catch { return null; }
}

const data = await tw(`/rest/people?limit=200`);
const opps = await tw(`/rest/opportunities?limit=100`);
if (!data) { console.log("# Twenty lead scorer — n/a (TWENTY creds missing or API unreachable). Nothing fabricated."); process.exit(0); }
const ppl = data.data?.people || [];
const oppPocIds = new Set((opps?.data?.opportunities || []).map((o) => o.pointOfContactId).filter(Boolean));

// Cluster by company domain.
const byDomain = new Map();
for (const p of ppl) {
  const em = (p.emails?.primaryEmail || "").toLowerCase();
  const dom = em.includes("@") ? em.split("@")[1] : null;
  const company = dom && !FREE.has(dom);
  const rec = { id: p.id, first: p.name?.firstName || "?", dom, company, teamIntent: !!p.teamIntent, hasOpp: oppPocIds.has(p.id) };
  if (company) {
    if (!byDomain.has(dom)) byDomain.set(dom, []);
    byDomain.get(dom).push(rec);
  }
  p._rec = rec;
}

function score(rec, clusterSize) {
  let s = 0;
  if (rec.company) s += 40;
  if (clusterSize >= 2) s += 40;
  if (rec.hasOpp) s += 20;
  return s;
}
const band = (s) => (s >= 80 ? "HOT" : s >= 40 ? "WARM" : "COLD");

const rows = [];
const toWrite = []; // persons to set teamIntent=true
for (const p of ppl) {
  const r = p._rec;
  const cluster = r.company ? byDomain.get(r.dom).length : 0;
  const s = r.company ? score(r, cluster) : null;
  const team = cluster >= 2; // 2+ from same company = a team evaluating us
  rows.push({ ...r, cluster, score: s, team });
  if (team && !r.teamIntent) toWrite.push(r);
}

// Report (non-PII: domain + count + first name + score).
const today = new Date().toISOString().slice(0, 10);
console.log(`# Twenty Lead Scorer — dark-funnel TEAM signal — ${today}`);
console.log(`*Company-domain + same-domain-cluster → teamIntent, computed from the CRM. Honest: free-email/no-email = unscored (not guessed). ${WRITE ? "WRITE mode: setting teamIntent on team clusters." : "DRY: no writes (pass --write to apply)."}*\n`);
const clusters = [...byDomain.entries()].filter(([, m]) => m.length >= 2);
console.log(`## Team clusters (2+ people, same company domain) — the teamIntent signal`);
if (!clusters.length) console.log(`_None yet — no company domain has 2+ people. A real zero._`);
for (const [dom, m] of clusters) console.log(`- **${dom}** — ${m.length} people (${m.map((x) => x.first).join(", ")}) → teamIntent${m.every((x) => x.teamIntent) ? " (already set)" : " ← FLAG"}`);
console.log(`\n## Scored persons`);
console.log(`| Person | Domain | Company? | Cluster | Score | Band | teamIntent |`);
console.log(`|--------|--------|:--------:|-------:|------:|------|:----------:|`);
for (const r of rows.sort((a, b) => (b.score || 0) - (a.score || 0))) {
  console.log(`| ${r.first} | ${r.dom || "—"} | ${r.company ? "✓" : "—"} | ${r.cluster || "—"} | ${r.score == null ? "n/a" : r.score} | ${r.score == null ? "—" : band(r.score)} | ${r.team ? "true" : r.teamIntent ? "true(was)" : "—"} |`);
}
console.log(`\n**${rows.filter((r) => r.team).length} person(s) in a team cluster · ${toWrite.length} need teamIntent set.**`);

if (WRITE && toWrite.length) {
  let ok = 0;
  for (const r of toWrite) {
    const res = await tw(`/rest/people/${r.id}`, { method: "PATCH", body: JSON.stringify({ teamIntent: true }) });
    if (res) ok++;
  }
  console.log(`\nWRITE: set teamIntent=true on ${ok}/${toWrite.length} persons.`);
  console.error(`lead-scorer: wrote teamIntent on ${ok}/${toWrite.length}`);
} else {
  console.error(`lead-scorer: ${rows.filter((r) => r.team).length} team-cluster persons, ${toWrite.length} to flag (dry)`);
}
