#!/usr/bin/env node
/**
 * SIMAP TENDER MONITOR — Swiss public-procurement consulting-lead channel (owner GO 2026-06-22).
 *
 * Pulls fitting public tenders from simap.ch (Confederation + cantons + communes — the official
 * platform) via its PUBLIC read-only JSON API, filters to our fit (AI / software / data / digital /
 * agentic / dev-consulting), weights Romandie, dedups, and prints a watchlist — flagging tenders
 * that are NEW since the last run. ASSESSMENT ONLY: a human decides whether to pursue; this script
 * never bids. Fitting tenders → log to Twenty as a consulting opportunity by hand.
 *
 * Reality (mem swiss-public-tenders-channel): open tenders favour established firms (refs/financials/
 * certs); a young firm's winnable entry = sub-threshold invitation / gré-à-gré / subcontracting /
 * cantonal digital mandates. Our references that qualify us = the OSS suite + consented cases. So this
 * is a SIGNAL feed for the human, not an auto-bidder.
 *
 * API (verified live 2026-06-22, no account/key needed — public + read-only):
 *   GET https://www.simap.ch/api/publications/v2/project/project-search
 *       ?search=<term>&orderAddressCountryOnlySwitzerland=true&page=0&size=<n>
 *   The endpoint sits behind a cookie-check gate, so we prime a cookie jar (curl -c/-b -L) on the
 *   first hit and reuse it. Response = { projects:[{ id, title{de,fr,it,en}, projectNumber,
 *   publicationNumber, pubType('tender'|'award'), processType, projectSubType, publicationDate,
 *   procOfficeName{}, orderAddress{cantonId,city{}} , lots[] }], pagination }.
 *   Server-side `search` is FUZZY full-text (returns construction noise for "intelligence
 *   artificielle"), so we confirm fit CLIENT-SIDE on the title. No fabrication: API down → n/a.
 *
 * Output: STDOUT = watchlist markdown (owner rule "tout dans trovex" → pipe into the store; ping cmo
 * on a NEW fit). STDERR = progress + summary. State (seen project numbers, for the NEW flag) persists
 * in reports/.simap-seen.json (git-ignored). `--save` also writes reports/simap-tenders-<date>.md.
 *
 * Usage:
 *   node growth/analytics/simap-tender-monitor.mjs            # full assessment watchlist
 *   node growth/analytics/simap-tender-monitor.mjs --new      # only tenders NEW since last run
 *   node growth/analytics/simap-tender-monitor.mjs --save
 */
import { writeFileSync, mkdirSync, readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));
const ymd = (d) => d.toISOString().slice(0, 10);
const NEW_ONLY = process.argv.includes("--new");
const SAVE = process.argv.includes("--save");

const API = "https://www.simap.ch/api/publications/v2/project/project-search";
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36";

// Fit search terms (DE + FR) — pull candidate pools server-side, union, then client-filter.
const QUERIES = [
  "software", "logiciel", "intelligence artificielle", "künstliche intelligenz",
  "digitalisation", "digitalisierung", "données", "data", "informatique", "Applikation",
  "développement logiciel", "automatisation", "cloud",
];
// Client-side fit confirmation on the title (the API search is fuzzy). A title must MATCH fit and
// NOT match the noise list (construction/facilities/etc that share loose keywords).
// FIT = strong IT signals only. Bare "entwicklung"/"développement" deliberately EXCLUDED — they
// false-match "Zentrumsentwicklung" (town-centre construction) etc; real dev tenders also carry
// logiciel/informatique/software, so coverage holds.
const FIT = /(logiciel|software|applikation|application|informati|intelligence artificielle|künstliche intelligenz|\bai\b|\bia\b|machine learning|données|\bdata\b|digitalis|numérique|plateforme|plattform|automatis|cloud|devops|cyber|saas|système d.information|informationssystem|fachanwendung|microservice|sap|\bweb\b|\bapi\b|\bagent)/i;
// NOISE = share a loose keyword but are clearly not software work (construction, facilities, lab/
// medical hardware — the latter false-matches "automatisiertes …gerät").
const NOISE = /(piscine|bâtiment|gebäude|wärme|heizung|chauffage|toiture|façade|fassade|fenêtre|fenster|route|strasse|nettoyage|reinigung|catering|mobilier|möbel|sanitaire|électricité gén|baumeister|génie civil|tiefbau|hochbau|architecte|paysag|ascenseur|\blift\b|gerät|appareil|instrument|maschine|mikrobiolog|labor|medizin|medical)/i;
const ROMANDIE = new Set(["GE", "VD", "VS", "NE", "JU", "FR", "BE"]); // BE bilingual

// In-memory cookie jar — the endpoint sits behind a cookie-check gate (302 → /cookie-check sets a
// cookie → redirects back). Native fetch has no cookie jar and drops Set-Cookie across redirects,
// so we follow redirects MANUALLY, stash Set-Cookie, and replay the cookie. Pure node — no curl/
// shell dependency, so this runs unchanged in a bare dokan node container. Public API, no secrets.
const jar = {};
const cookieHeader = () => Object.entries(jar).map(([k, v]) => `${k}=${v}`).join("; ");
const stashCookies = (res) => {
  const sc = typeof res.headers.getSetCookie === "function" ? res.headers.getSetCookie() : [];
  for (const c of sc) {
    const m = c.match(/^([^=]+)=([^;]+)/);
    if (m) jar[m[1]] = m[2];
  }
};
async function fetchJson(url) {
  try {
    const hdr = () => ({ "User-Agent": UA, Accept: "application/json", ...(Object.keys(jar).length ? { Cookie: cookieHeader() } : {}) });
    let res = await fetch(url, { headers: hdr(), redirect: "manual" });
    stashCookies(res);
    for (let hops = 0; (res.status === 301 || res.status === 302) && hops < 4; hops++) {
      let loc = res.headers.get("location");
      if (!loc) break;
      if (loc.startsWith("/")) loc = "https://www.simap.ch" + loc;
      res = await fetch(loc, { headers: hdr(), redirect: "manual" });
      stashCookies(res);
    }
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null; // network/gate failure → n/a, never fabricated
  }
}

const t = (o) => (o ? o.fr || o.de || o.it || o.en || "" : ""); // pick a human title, FR-first

async function run() {
  // State (seen project numbers, for the NEW flag) is best-effort: a read-only/ephemeral fs (e.g. a
  // dokan container) just means each run reads as a first run — the watchlist still prints. No crash.
  const seenPath = join(__dir, "reports", ".simap-seen.json");
  let seen = new Set();
  try {
    if (existsSync(seenPath)) seen = new Set(JSON.parse(readFileSync(seenPath, "utf8")));
  } catch { /* unreadable state → treat as first run */ }
  const firstRun = seen.size === 0;

  const byNum = new Map();
  let apiUp = false;
  for (const q of QUERIES) {
    const url = `${API}?search=${encodeURIComponent(q)}&orderAddressCountryOnlySwitzerland=true&page=0&size=50`;
    const data = await fetchJson(url);
    if (!data || !Array.isArray(data.projects)) continue;
    apiUp = true;
    for (const p of data.projects) {
      if (p.pubType !== "tender") continue; // skip 'award' = already awarded, not a lead
      const title = t(p.title);
      if (!FIT.test(title) || NOISE.test(title)) continue;
      const num = p.projectNumber || p.id;
      if (byNum.has(num)) continue;
      const canton = p.orderAddress?.cantonId || null;
      byNum.set(num, {
        num,
        title: title.trim(),
        date: p.publicationDate,
        canton,
        romandie: canton ? ROMANDIE.has(canton) : false,
        office: t(p.procOfficeName) || p.procOfficeName?.de || "—",
        procType: p.processType,
        subType: p.projectSubType,
        pubNumber: p.publicationNumber,
        isNew: !seen.has(num),
      });
    }
  }

  if (!apiUp) {
    process.stdout.write(`# Simap Tender Watchlist — ${ymd(new Date())}\n\n_simap.ch API unavailable (cookie-gate/network) → **n/a**. No tenders fabricated. Re-run later._\n`);
    process.stderr.write("simap: API n/a\n");
    return;
  }

  let rows = [...byNum.values()];
  // Romandie first, then newest, then canton.
  rows.sort((a, b) => Number(b.romandie) - Number(a.romandie) || (a.date < b.date ? 1 : -1));
  const fresh = rows.filter((r) => r.isNew);
  const shown = NEW_ONLY ? fresh : rows;

  const today = ymd(new Date());
  const md = [];
  const P = (s) => md.push(s);
  P(`# Simap Tender Watchlist — Swiss public procurement — ${today}`);
  P(``);
  P(`*Owner: analytics-lead · auto-pulled from simap.ch public API by \`simap-tender-monitor.mjs\` · fit = AI/software/data/digital/dev · open tenders only (\`pubType=tender\`; awarded ones dropped) · Romandie-weighted. **ASSESSMENT ONLY — a human decides; this script never bids.** Honest: server search is fuzzy, fit is confirmed on the title; API down → n/a; a fitting tender → log to Twenty by hand as a consulting opportunity.*`);
  P(``);
  P(`**${rows.length} fitting open tender(s)** · ${fresh.length} NEW since last run${firstRun ? " (first run — all flagged new; this is the go/no-go baseline)" : ""}.`);
  P(``);
  if (!shown.length) {
    P(NEW_ONLY ? `_No NEW fitting tenders since last run — a real zero._` : `_No fitting open tenders right now — a real zero._`);
  } else {
    P(`| New | Canton | Published | Tender | Office | Procedure |`);
    P(`|:---:|:------:|:---------:|--------|--------|-----------|`);
    for (const r of shown) {
      P(`| ${r.isNew ? "🆕" : ""} | ${r.romandie ? `**${r.canton}**` : r.canton || "—"} | ${r.date} | ${r.title.slice(0, 90)} (${r.num}) | ${(r.office || "—").slice(0, 40)} | ${r.procType}/${r.subType} |`);
    }
  }
  P(``);
  P(`<sub>Lookup: search the tender number on simap.ch. Romandie cantons bolded (GE/VD/VS/NE/JU/FR/BE). Winnable entry for a young firm = sub-threshold invitation / gré-à-gré / subcontracting / cantonal digital mandates (mem swiss-public-tenders-channel); refs that qualify us = the OSS suite + consented cases.</sub>`);

  const out = md.join("\n");
  process.stdout.write(out + "\n");
  process.stderr.write(`simap: ${rows.length} fitting tenders, ${fresh.length} new (queries=${QUERIES.length})\n`);

  // Persist the union of seen numbers so the next run can flag NEW (best-effort — skipped silently
  // on a read-only fs like a dokan container).
  try {
    mkdirSync(join(__dir, "reports"), { recursive: true });
    const merged = new Set([...seen, ...rows.map((r) => r.num)]);
    writeFileSync(seenPath, JSON.stringify([...merged]));
  } catch { /* ephemeral/read-only fs → no persistence, fine */ }

  if (SAVE) {
    try {
      mkdirSync(join(__dir, "reports"), { recursive: true });
      const f = join(__dir, "reports", `simap-tenders-${today}.md`);
      writeFileSync(f, out + "\n");
      process.stderr.write(`simap: saved ${f}\n`);
    } catch { process.stderr.write("simap: --save failed (read-only fs)\n"); }
  }
}

await run();
