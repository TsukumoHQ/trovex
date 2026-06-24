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
// Runs on dokan (no host runs): write flag via DOKAN_INPUT {"write":true}, or --write on argv.
// GOTCHA: dokan DOUBLE-encodes DOKAN_INPUT — it arrives as a JSON *string of* the JSON
// (e.g. "\"{\\\"write\\\":true}\""), so one JSON.parse yields a STRING; parse again to get the object.
let DOKAN_IN = {};
try { let v = JSON.parse(process.env.DOKAN_INPUT || "{}"); if (typeof v === "string") v = JSON.parse(v); DOKAN_IN = v || {}; } catch { DOKAN_IN = {}; }
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
// Opp stage per point-of-contact. A booked/engaged call (stage past SCREENING) is the STRONGEST
// dark-funnel signal we can read from the CRM — they raised their hand for a consulting conversation.
// (Verified in the lead-machine sample: warm booked deals were mis-tiered COLD because the scorer
// was blind to this; the LLM judged empty enrichment. Reading opp stage fixes it at the source.)
const BOOKED_STAGES = new Set(["MEETING", "PROPOSAL", "CUSTOMER"]);
const oppStageByPoc = new Map();
for (const o of opps?.data?.opportunities || []) {
  if (o.pointOfContactId) oppStageByPoc.set(o.pointOfContactId, (o.stage || "").toUpperCase());
}

// Junk filter: test/probe rows are not leads — drop them from the report and from clusters so a
// fake company domain can't fabricate a team. Same regex family as the north-star scoreboard.
const isJunk = (em, first) =>
  /(^|@)(example\.com|y\.com|test|eeid\.ch)/i.test(em || "") ||
  /^(test|klk|asdf|qwer|poip|xxx|probe)/i.test(first || "") ||
  em === "x@x.com";

// Cluster by company domain.
const byDomain = new Map();
for (const p of ppl) {
  const em = (p.emails?.primaryEmail || "").toLowerCase();
  const first = p.name?.firstName || "?";
  const dom = em.includes("@") ? em.split("@")[1] : null;
  const company = dom && !FREE.has(dom);
  const stage = oppStageByPoc.get(p.id) || null;
  const rec = { id: p.id, first, dom, company, teamIntent: !!p.teamIntent, hasOpp: oppStageByPoc.has(p.id), booked: BOOKED_STAGES.has(stage || ""), stage, junk: isJunk(em, first) };
  if (company && !rec.junk) {
    if (!byDomain.has(dom)) byDomain.set(dom, []);
    byDomain.get(dom).push(rec);
  }
  p._rec = rec;
}

function score(rec, clusterSize) {
  let s = 0;
  if (rec.company) s += 40;
  if (clusterSize >= 2) s += 40;        // 2+ same-domain = a team evaluating us
  if (rec.booked) s += 40;              // booked call (opp MEETING+) = strong consulting intent
  else if (rec.hasOpp) s += 20;         // open opp, pre-meeting = some intent
  return Math.min(s, 100);
}
const band = (s) => (s >= 80 ? "HOT" : s >= 40 ? "WARM" : "COLD");

const rows = [];
const toWrite = []; // persons to set teamIntent=true
let junkSkipped = 0;
for (const p of ppl) {
  const r = p._rec;
  if (r.junk) { junkSkipped++; continue; } // test/probe rows are not leads
  const cluster = r.company ? byDomain.get(r.dom).length : 0;
  // Score whenever there's a readable signal — company OR a booked/open opp. A booked solo-dev
  // (free email, no cluster) is still a real consulting hand-raise → WARM, not unscored.
  const s = (r.company || r.hasOpp) ? score(r, cluster) : null;
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
console.log(`| Person | Domain | Company? | Cluster | Booked | Score | Band | teamIntent |`);
console.log(`|--------|--------|:--------:|-------:|:------:|------:|------|:----------:|`);
for (const r of rows.sort((a, b) => (b.score || 0) - (a.score || 0))) {
  console.log(`| ${r.first} | ${r.dom || "—"} | ${r.company ? "✓" : "—"} | ${r.cluster || "—"} | ${r.booked ? "✓" : r.hasOpp ? "opp" : "—"} | ${r.score == null ? "n/a" : r.score} | ${r.score == null ? "—" : band(r.score)} | ${r.team ? "true" : r.teamIntent ? "true(was)" : "—"} |`);
}
const booked = rows.filter((r) => r.booked).length;
console.log(`\n**${rows.filter((r) => r.team).length} person(s) in a team cluster · ${booked} booked call(s) · ${toWrite.length} need teamIntent set · ${junkSkipped} junk skipped.**`);

let wrote = 0;
if (WRITE && toWrite.length) {
  for (const r of toWrite) {
    const res = await tw(`/rest/people/${r.id}`, { method: "PATCH", body: JSON.stringify({ teamIntent: true }) });
    if (res) wrote++;
  }
  console.log(`\nWRITE: set teamIntent=true on ${wrote}/${toWrite.length} persons.`);
  console.error(`lead-scorer: wrote teamIntent on ${wrote}/${toWrite.length}`);
} else {
  console.error(`lead-scorer: ${rows.filter((r) => r.team).length} team-cluster persons, ${toWrite.length} to flag (dry)`);
}

// Structured receipt for the dokan operator (parsed from the ::dokan:result:: line).
console.log(`::dokan:result:: ${JSON.stringify({
  date: today,
  mode: WRITE ? "write" : "dry",
  persons: ppl.length,
  teamClusters: clusters.length,
  teamPersons: rows.filter((r) => r.team).length,
  booked,
  flagged: toWrite.length,
  wrote,
  junkSkipped,
})}`);
