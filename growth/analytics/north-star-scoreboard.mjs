#!/usr/bin/env node
/**
 * NORTH-STAR SCOREBOARD — the owner's one-screen launch readout: reach → consulting leads.
 *
 * This sits ABOVE the operator dashboards (weekly-digest, plausible-snapshot, geo-citation-monitor)
 * and consolidates their headline numbers into three panels the owner reads at a glance:
 *
 *   PANEL A — Consulting (the money end): inquiries by source PROPERTY (trovex / WRAI.TH / yoru /
 *             referral / direct) × channel, with the qualified (hot+warm) split. North star =
 *             QUALIFIED, SUITE-SOURCED consulting leads — not raw count, not vanity reach.
 *   PANEL B — trovex activation funnel (PUBLIC BETA: install = the conversion): landing_view →
 *             github_clicked (install-intent). Waitlist events are dormant by design (no waitlist
 *             UI) and read a real 0. Needs the trovex site id (else honest n/a).
 *   PANEL B2 — GEO attribution: which AI engine / channel sent the landing sessions, broken down
 *             from the geo_source/channel props on landing_view. A floor, not a census (AI referrers
 *             are stripped → direct/unknown; UTM'd links are the only reliable AI-engine signal).
 *   PANEL C — 4-engine AI-citation panel (awareness, top of funnel): suite citation share per engine,
 *             read from the latest geo-citation-monitor report (no live engine calls here — the panel
 *             run is separate and rate-limited). A snapshot, never a guaranteed rank.
 *
 * HONESTY is the contract. Every panel degrades to `n/a` when its key/source is missing — NEVER a
 * fabricated number. A real zero reads `0`. Reach (stars, visits, citations) is the input; the only
 * number that "wins" is a qualified consulting lead. We say openly which engine/source was unavailable.
 *
 * Keys (out-of-git, env only — never printed/committed). Load what you have; missing → n/a:
 *   set -a; . ~/.config/trovex-growth/plausible.env; . ~/.config/trovex-growth/supabase.env; set +a
 *   - PLAUSIBLE_STATS_API_KEY            (read-only Stats API)
 *   - TSUKUMO_PLAUSIBLE_SITE_ID || PLAUSIBLE_SITE_ID   (tsukumo.ch — consulting funnel)
 *   - TROVEX_PLAUSIBLE_SITE_ID           (trovex.dev — waitlist funnel; OPTIONAL, n/a if absent)
 *   - SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY          (leads + waitlist; NON-PII columns only)
 * The 4-engine panel reads reports parsed from `geo-citation-monitor.mjs` output (run + saved separately).
 *
 * Output: prints the report to STDOUT (owner rule: "rien en md, tout dans trovex" — pipe into
 * trovex_write to centralize). Progress/summary → stderr. `--save` is an opt-in disk escape hatch
 * (off by default; we do NOT write disk reports).
 *
 * Hygiene: pre-launch traffic is crawler + e2e-verification noise (traffic-hygiene.md). `--since
 * <launch-date>` starts the window at launch day; default = the hygiene floor (cumulative launch read).
 *
 * Usage:  node north-star-scoreboard.mjs                       # cumulative since launch floor
 *         node north-star-scoreboard.mjs --since 2026-07-01    # since launch day
 *         node north-star-scoreboard.mjs --window 7            # rolling last-7-days instead
 *         node north-star-scoreboard.mjs --citations reports/geo-citations-2026-06-19.md  # pin a panel file
 */
import { writeFileSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));
const ymd = (d) => d.toISOString().slice(0, 10);

// Launch hygiene floor — before this, traffic is crawler + our own verification, not demand
// (traffic-hygiene.md). Bump to the real distribution date once launch fires. Mirrors plausible-snapshot.
const HYGIENE_START = "2026-06-18";

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : undefined;
}

function window_() {
  const end = new Date();
  const win = arg("--window");
  const since = arg("--since");
  if (win) return { start: ymd(new Date(end.getTime() - Number(win) * 86400_000)), end: ymd(end), label: `rolling ${win}d` };
  const start = since || HYGIENE_START;
  return { start, end: ymd(end), label: since ? `since ${since}` : `cumulative since launch floor ${HYGIENE_START}` };
}

// ---- data adapters (each returns data or null; null → n/a, never fabricated) ----
async function plausible(site, path) {
  const key = process.env.PLAUSIBLE_STATS_API_KEY;
  if (!key || !site) return null;
  try {
    const r = await fetch(`https://plausible.io/api/v1/stats/${path}&site_id=${site}`, { headers: { Authorization: `Bearer ${key}` } });
    if (!r.ok) return null;
    return r.json();
  } catch { return null; }
}
const evAgg = (site, w, name, extra = "") =>
  plausible(site, `aggregate?period=custom&date=${w.start},${w.end}&metrics=events&filters=event:name==${name}${extra}`)
    .then((d) => (d ? d.results?.events?.value ?? 0 : null));

// Break an event down by one of its custom props (e.g. geo_source / channel) → rows of
// { value, visitors, events } sorted desc by visitors. null = source/key unavailable (→ n/a);
// [] = a real zero (event fired, but the prop was never present / window empty).
const evBreakdown = (site, w, prop, evName) =>
  plausible(site, `breakdown?period=custom&date=${w.start},${w.end}&property=event:props:${prop}&metrics=visitors,events&filters=event:name==${evName}&limit=30`)
    .then((d) => {
      if (!d) return null;
      const rows = d.results ?? [];
      return rows.map((r) => ({ value: r[prop] ?? r.value ?? "(none)", visitors: r.visitors ?? 0, events: r.events ?? 0 }))
        .sort((a, b) => b.visitors - a.visitors);
    });

async function supabase(query) {
  const url = process.env.SUPABASE_URL, key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;
  try {
    const r = await fetch(`${url}/rest/v1/${query}`, { headers: { apikey: key, Authorization: `Bearer ${key}` } });
    if (!r.ok) return null;
    return r.json();
  } catch { return null; }
}

// Twenty CRM (tsukumo.twenty.com) — the consulting lead SYSTEM OF RECORD (Supabase `leads` is now
// just raw capture). Returns parsed REST data or null (→ n/a). Read-only; PII stays in the CRM.
async function twenty(path) {
  const url = process.env.TWENTY_BASE_URL, key = process.env.TWENTY_API_KEY;
  if (!url || !key) return null;
  try {
    const r = await fetch(`${url}${path}`, { headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" } });
    if (!r.ok) return null;
    const j = await r.json();
    return j.data || null;
  } catch { return null; }
}

// An Opportunity past NEW = a qualified consulting lead (a real conversation is moving).
const QUALIFIED_STAGES = new Set(["SCREENING", "MEETING", "PROPOSAL", "CUSTOMER"]);
// Twenty person.source → coarse property bucket. suite = the OSS funnel (the north-star source).
function twentySourceBucket(source) {
  switch (source) {
    case "OSS_SUITE": return { label: "OSS suite (trovex/WRAI.TH/yoru)", suite: true };
    case "WAITLIST": case "SEARCH": case "AI_ENGINE": case "SOCIAL": return { label: source === "WAITLIST" ? "waitlist" : "content/search", suite: false };
    case "REFERRAL": return { label: "referral", suite: false };
    case "IN_PERSON": return { label: "in-person", suite: false };
    case "DIRECT": return { label: "direct", suite: false };
    default: return { label: source ? source.toLowerCase() : "untagged", suite: false };
  }
}

// ---- 4-engine citation panel: parse the latest geo-citation-monitor report ----
// The monitor writes per-engine rows like:
//   | ChatGPT (OpenAI web_search) | live | **5/10 (50%)** | ... |
//   | Perplexity (sonar) | n/a (no PERPLEXITY_API_KEY) | — | ... |
//   | **UNION (any engine)** | — | **7/10 (70%)** | ... |
// We surface the four target engines (ChatGPT, Perplexity, Gemini, Google AIO) + the union.
function citationPanel() {
  const pinned = arg("--citations");
  let txt, srcDate, srcFile;
  try {
    if (pinned) {
      srcFile = pinned;
      txt = readFileSync(pinned, "utf8");
      const m = pinned.match(/(\d{4}-\d{2}-\d{2})/);
      srcDate = m ? m[1] : "unknown";
    } else {
      const dir = join(__dir, "reports");
      const files = readdirSync(dir).filter((f) => /^geo-citations-\d{4}-\d{2}-\d{2}\.md$/.test(f)).sort();
      if (!files.length) return null;
      srcFile = `reports/${files[files.length - 1]}`;
      srcDate = files[files.length - 1].slice("geo-citations-".length, -3);
      txt = readFileSync(join(dir, files[files.length - 1]), "utf8");
    }
  } catch { return null; }

  const ENGINES = [
    { name: "ChatGPT", match: /chatgpt/i },
    { name: "Perplexity", match: /perplexity/i },
    { name: "Gemini", match: /gemini/i },
    { name: "Google AI Overviews", match: /google ai overview/i },
  ];
  const rows = txt.split("\n").filter((l) => l.trim().startsWith("|"));
  const cellAll = (line) => {
    // 3rd pipe-cell is the "All" column; strip ** and whitespace.
    const cols = line.split("|").map((c) => c.trim());
    return cols[3] ? cols[3].replace(/\*\*/g, "") : "—";
  };
  const engines = ENGINES.map((e) => {
    const line = rows.find((l) => e.match.test(l));
    if (!line) return { name: e.name, status: "n/a", share: "n/a (engine row absent)" };
    const statusCol = line.split("|").map((c) => c.trim())[2] || "";
    const live = /live/i.test(statusCol);
    if (!live) return { name: e.name, status: "n/a", share: statusCol };
    const share = cellAll(line);
    // A `0/0` "All" cell = zero valid samples (every query errored, e.g. 429 quota) — NOT a real 0%.
    if (/^0\s*\/\s*0\b/.test(share)) return { name: e.name, status: "n/a", share: "n/a (all queries errored — see panel)" };
    return { name: e.name, status: "live", share };
  });
  const unionLine = rows.find((l) => /UNION/i.test(l));
  const union = unionLine ? cellAll(unionLine) : "n/a";
  return { srcDate, srcFile, engines, union };
}

async function main() {
  const w = window_();
  const n = (v) => (v == null ? "n/a" : String(v));
  const rate = (a, b) => (a == null || b == null || !b ? "n/a" : `${Math.round((a / b) * 100)}%`);

  const tsukumoSite = process.env.TSUKUMO_PLAUSIBLE_SITE_ID || process.env.PLAUSIBLE_SITE_ID;
  const trovexSite = process.env.TROVEX_PLAUSIBLE_SITE_ID;

  // ===== PANEL A — Consulting (the money end) — Twenty CRM is the SYSTEM OF RECORD =====
  // Pipeline = Opportunities joined to their pointOfContact's source. Qualified = stage past NEW.
  // North star = qualified opportunities whose source is the OSS suite.
  const [twOpps, twPpl] = await Promise.all([
    twenty(`/rest/opportunities?limit=100`),
    twenty(`/rest/people?limit=100`),
  ]);
  let propRows = null, totalInq = null, totalQual = null, suiteQual = null, twPersons = null;
  let lmBooked = null, lmBookedWin = null, lmTeam = null, lmTiers = null; // Panel F — lead machine
  if (twOpps && twPpl) {
    const opps = twOpps.opportunities || twOpps || [];
    const ppl = twPpl.people || twPpl || [];
    twPersons = ppl.length;
    // Lead-machine KPIs: a booked call = an opp that reached MEETING+ (a call is booked/held).
    // teamIntent = the dark-funnel team signal (twenty-lead-scorer sets it on company-domain clusters).
    const BOOKED = new Set(["MEETING", "PROPOSAL", "CUSTOMER"]);
    lmBooked = opps.filter((o) => BOOKED.has(o.stage)).length;
    // Booked IN THE WINDOW — opp.createdAt is the booked-date proxy (Twenty has no separate booked field).
    lmBookedWin = opps.filter((o) => BOOKED.has(o.stage) && (o.createdAt || "").slice(0, 10) >= w.start).length;
    lmTeam = ppl.filter((p) => p.teamIntent).length;
    // Tier distribution — the lead/hand-raiser pipeline writes Person.tier (A/B/C; score>=60=A,35-59=B,<35=C).
    // Reads live; until the pipeline write goes live (currently dry-run) it's all unset → 0/0/0 = honest.
    lmTiers = { A: 0, B: 0, C: 0, unset: 0 };
    for (const p of ppl) { const t = p.tier; if (t === "A" || t === "B" || t === "C") lmTiers[t]++; else lmTiers.unset++; }
    const srcOf = (id) => (ppl.find((p) => p.id === id) || {}).source || null;
    const by = new Map();
    for (const o of opps) {
      const { label, suite } = twentySourceBucket(srcOf(o.pointOfContactId));
      const cur = by.get(label) || { property: label, inquiries: 0, qualified: 0, suite };
      cur.inquiries++;
      if (QUALIFIED_STAGES.has(o.stage)) cur.qualified++;
      by.set(label, cur);
    }
    propRows = [...by.values()].sort((a, b) => b.qualified - a.qualified || b.inquiries - a.inquiries);
    totalInq = opps.length;
    totalQual = propRows.reduce((s, r) => s + r.qualified, 0);
    suiteQual = propRows.filter((r) => r.suite).reduce((s, r) => s + r.qualified, 0);
  }

  // Supabase `leads` = RAW capture cross-check (now secondary to Twenty). Flag obvious test rows so
  // junk can't masquerade as a real lead (a 'klklkl/poipoipoi' row once inflated the north star).
  const rawLeads = await supabase(`leads?project=eq.tsukumo&select=lead_band,channel,how_heard,email,name`);
  const isTestRow = (l) => /(^|@)(example\.com|y\.com|test|eeid\.ch)/i.test(l.email || "") ||
    /^(test|klk|asdf|qwer|poip|xxx)/i.test((l.name || "").toLowerCase()) || /probe/i.test(l.email || "");
  const rawTotal = rawLeads ? rawLeads.length : null;
  const rawTest = rawLeads ? rawLeads.filter(isTestRow).length : null;
  const rawReal = rawLeads ? rawTotal - rawTest : null;

  // ---- Dark funnel: self-report (how_heard) vs auto-attribution (channel) ----
  // A lead's `channel` is what our auto-attribution captured (UTM/referrer at submit);
  // `how_heard` is what the lead SELF-REPORTS. Where they disagree — or auto is blind to a
  // real source the lead named — that's the dark funnel (AI engines + dark social strip the
  // referrer; offline/word-of-mouth never had one). We surface the size of that gap so the
  // pipeline isn't read as if auto-attribution were complete. Honest: n/a with no leads.
  // Map a free-text how_heard to a coarse acquisition class (or a non-channel marker).
  const heardClass = (h) => {
    const s = (h || "").toLowerCase().trim();
    if (!s) return "none"; // no self-report → can't compare
    if (/(yoru|wraith|trovex|suite|oss)/.test(s)) return "suite";
    if (/(chatgpt|gpt|openai|perplexity|claude|anthropic|gemini|copilot|\bai\b)/.test(s)) return "ai_engine";
    if (/(google|search|bing|seo)/.test(s)) return "search";
    if (/(linkedin|twitter|\bx\b|threads|reddit|social|youtube|hn|hacker)/.test(s)) return "social";
    if (/(referr|friend|colleag|word|network|recommend)/.test(s)) return "referral";
    // booking/call/email/in-person/event = a conversion MECHANISM, not an acquisition channel
    // — auto-attribution legitimately can't see it, so it's NOT counted as a dark miss.
    if (/(booking|calendly|call|email|in.?person|event|meet)/.test(s)) return "offline";
    return "other";
  };
  // Normalize the auto channel to the same vocabulary; null/empty/unknown = auto blind.
  const autoClass = (c) => {
    const s = (c || "").toLowerCase().trim();
    if (!s || s === "unknown" || s === "none") return "missing";
    if (s === "ai_engine" || s === "ai") return "ai_engine";
    return s; // direct | search | social | referral | suite | …
  };
  let dark = null;
  if (rawLeads) {
    const real = rawLeads.filter((l) => !isTestRow(l));
    const acc = { compared: 0, agree: 0, disagree: 0, autoBlind: 0, offlineOrDirect: 0, noSelfReport: 0 };
    for (const l of real) {
      const self = heardClass(l.how_heard);
      const auto = autoClass(l.channel);
      if (self === "none") { acc.noSelfReport++; continue; }
      acc.compared++;
      const autoVisible = auto !== "missing" && auto !== "direct";
      if (self === "offline" || self === "other") { acc.offlineOrDirect++; continue; } // not a comparable acquisition source
      if (!autoVisible) { acc.autoBlind++; continue; } // lead named a real source; auto missed it = dark
      if (auto === self) acc.agree++; else acc.disagree++;
    }
    // Dark = auto blind to a named source + auto/self disagree, over comparable leads.
    const denom = acc.agree + acc.disagree + acc.autoBlind;
    acc.darkCount = acc.disagree + acc.autoBlind;
    acc.darkRate = denom > 0 ? Math.round((acc.darkCount / denom) * 100) : null;
    dark = acc;
  }

  // Plausible cross-check: assessment_request total + suite-sourced.
  const [assessAll, assessSuite] = await Promise.all([
    evAgg(tsukumoSite, w, "assessment_request"),
    evAgg(tsukumoSite, w, "assessment_request", ";event:props:source==suite"),
  ]);

  // ===== PANEL B — trovex waitlist funnel (beta primary conversion) =====
  // Store (Supabase) = source of truth for the COUNT. Count and source-breakdown are queried
  // SEPARATELY so a missing attribution column can't nuke the count (select * narrows nothing,
  // but channel/geo_source may not exist on every deploy → degrade the breakdown to n/a only).
  const wlCountRows = await supabase(`waitlist?project=eq.trovex&created_at=gte.${w.start}&select=created_at`);
  let wlCount = wlCountRows ? wlCountRows.length : null;
  // Cross-property fallback: if no project='trovex' rows, count all waitlist (single-property beta).
  if (wlCountRows && wlCountRows.length === 0) {
    const wlAny = await supabase(`waitlist?created_at=gte.${w.start}&select=created_at`);
    if (wlAny) wlCount = wlAny.length;
  }
  // Source attribution lives in the `source` column (geo_source/channel persisted at signup, PR #102),
  // with `referer` host as the dark-social fallback. NON-PII (no email/utm pulled into the report).
  let wlBySource = null;
  if (wlCount) {
    const wl = await supabase(`waitlist?project=eq.trovex&created_at=gte.${w.start}&select=source,referer`);
    if (wl && wl.length) {
      const by = new Map();
      for (const r of wl) {
        const k = r.source || r.referer || "direct/unknown";
        by.set(k, (by.get(k) || 0) + 1);
      }
      wlBySource = [...by.entries()].sort((a, b) => b[1] - a[1]);
    }
  }
  // Public-beta conversion = install-intent (github_clicked), NOT waitlist. The waitlist events
  // (request_access_clicked / waitlist_submitted) are DORMANT by design — no waitlist UI on the
  // public-beta landing — so they read 0/n/a, not a gap. We still fetch them as a dormancy check.
  const [tvLanding, tvInstall, tvCta, tvSubmit, geoRows, chanRows] = trovexSite
    ? await Promise.all([
        evAgg(trovexSite, w, "landing_view"),
        evAgg(trovexSite, w, "github_clicked"),
        evAgg(trovexSite, w, "request_access_clicked"),
        evAgg(trovexSite, w, "waitlist_submitted"),
        evBreakdown(trovexSite, w, "geo_source", "landing_view"),
        evBreakdown(trovexSite, w, "channel", "landing_view"),
      ])
    : [null, null, null, null, null, null];

  // ---- Blog ROI (Panel E): is the blog (60+ posts) actually paying? ----
  // Blog→install = trovex.dev events attributed to the blog via utm_campaign=blog (set on blog→trovex
  // links). Blog→lead = Supabase leads self-/UTM-attributed to the blog. Both degrade to n/a/0 until
  // the blog→trovex links are UTM-tagged + traffic lands — never fabricated. Citation share reuses Panel C.
  const [blogLanding, blogInstall] = trovexSite
    ? await Promise.all([
        evAgg(trovexSite, w, "landing_view", ";event:props:utm_campaign==blog"),
        evAgg(trovexSite, w, "github_clicked", ";event:props:utm_campaign==blog"),
      ])
    : [null, null];
  const blogLeads = await supabase(`leads?or=(utm_campaign.eq.blog,utm_source.eq.blog,how_heard.ilike.*blog*)&select=project,utm_campaign,utm_source,how_heard`);

  // ---- Savings-receipt propagation (Panel D, privacy-safe). The dark-funnel virality of the shared
  // savings receipt, measured WITHOUT any identity. `share_clicked` = receipts shared FROM the site
  // (by format); `visit:utm_source==savings-share` = sessions that arrived VIA a shared receipt.
  // Both anonymous — audit/savings are privacy-by-design (no email, nothing leaves the page), so a
  // share carries no who/which-company (see trovex record audit-savings-privacy-by-design). This is
  // the honest propagation signal — the receipt spreading team→team — never a profile. A non-zero
  // inflow with zero share_clicks (or vice-versa) is still real: shares can happen off-site (copied
  // link / posted badge) and land later.
  const [shareClicks, shareByFormat, savingsInflow] = trovexSite
    ? await Promise.all([
        evAgg(trovexSite, w, "share_clicked"),
        evBreakdown(trovexSite, w, "format", "share_clicked"),
        plausible(trovexSite, `aggregate?period=custom&date=${w.start},${w.end}&metrics=visitors&filters=visit:utm_source==savings-share`)
          .then((d) => (d ? d.results?.visitors?.value ?? 0 : null)),
      ])
    : [null, null, null];

  // ===== PANEL C — 4-engine citation panel =====
  const cite = citationPanel();

  // ---- assemble ----
  const date = ymd(new Date());
  const md = [];
  const P = (s) => md.push(s);

  P(`# Trovex North-Star Scoreboard — reach → consulting leads — ${date}`);
  P(``);
  P(`*Owner-facing launch scoreboard · window: ${w.label} (${w.start}→${w.end}) · auto-assembled by \`north-star-scoreboard.mjs\` from Twenty CRM (consulting pipeline) + live Plausible + Supabase + the latest citation panel. No fabricated data — \`n/a\` = source/key unavailable, \`0\` = a real zero. The only number that wins is a **qualified consulting lead**; reach is the input.*`);
  P(``);

  // Headline
  P(`## ★ Headline`);
  P(`- **North star — qualified, suite-sourced consulting leads: ${n(suiteQual)}** (of ${n(totalQual)} qualified, ${n(totalInq)} total opportunities in the Twenty pipeline). _Qualified = opportunity past the NEW stage; suite = OSS-funnel sourced._`);
  P(`- **trovex public-beta conversion — install-intent (github_clicked): ${n(tvInstall)}** of ${n(tvLanding)} landing views (${rate(tvInstall, tvLanding)}). _Waitlist is dormant by design; install is the conversion._`);
  P(`- **Suite AI-citation share (any engine): ${cite ? cite.union : "n/a"}** ${cite ? `_(snapshot ${cite.srcDate})_` : "_(no citation panel run yet)_"}.`);
  P(`- **Consulting (Plausible \`assessment_request\`):** ${n(assessAll)} total${assessSuite == null ? "" : ` · ${n(assessSuite)} suite-sourced`} — on-site events; the Twenty pipeline (Panel A) is the durable record.`);
  P(``);

  // Panel A — Twenty CRM = system of record
  P(`## A · Consulting pipeline by source property — the money end (Twenty CRM)`);
  if (!propRows) {
    P(`_Twenty CRM unavailable (no \`TWENTY_API_KEY\`/\`TWENTY_BASE_URL\`) → **n/a**. Cannot fabricate consulting volume._`);
  } else if (!propRows.length) {
    P(`_0 opportunities in the pipeline — a real zero, reported honestly._`);
  } else {
    P(`*Source of record: Twenty (${twPersons} persons). Qualified = opportunity past NEW (stages: NEW→SCREENING→MEETING→PROPOSAL→CUSTOMER).*`);
    P(``);
    P(`| Source property | Opportunities | Qualified | Suite? |`);
    P(`|-----------------|--------------:|----------:|:------:|`);
    for (const r of propRows) P(`| ${r.property} | ${r.inquiries} | ${r.qualified} | ${r.suite ? "✅" : "—"} |`);
    P(`| **Total** | **${totalInq}** | **${totalQual}** (suite: **${suiteQual}**) | |`);
  }
  P(``);
  P(`**Raw-capture cross-check (Supabase \`leads\`):** ${rawTotal == null ? "n/a" : `${rawTotal} rows, of which ${rawTest} are test/junk → ${rawReal} real`}. Twenty (above) is the deduped system of record; Supabase stays the raw inbound capture. **Plausible \`assessment_request\`:** all ${n(assessAll)} · suite ${n(assessSuite)}.`);
  P(``);

  // Panel B — public-beta activation funnel (install = the conversion)
  P(`## B · trovex activation funnel — public beta (install = the conversion)`);
  P(`| Stage | Event (trovex.dev) | Count |`);
  P(`|-------|--------------------|------:|`);
  P(`| Reach | landing_view | ${n(tvLanding)} |`);
  P(`| **★ Conversion** | github_clicked (install-intent / star) | ${n(tvInstall)} |`);
  P(``);
  P(`**Rate:** reach→install-intent ${rate(tvInstall, tvLanding)}.`);
  if (!trovexSite) P(`> Web-funnel = **n/a**: no \`TROVEX_PLAUSIBLE_SITE_ID\` set (trovex.dev is a separate Plausible site).`);
  P(`> Positioning is **public beta** — install/GitHub-star is the conversion. The waitlist events are **dormant by design** (no waitlist UI on the landing): request_access_clicked ${n(tvCta)} · waitlist_submitted ${n(tvSubmit)} — a real zero, not a gap. Helpers + \`/api/waitlist\` + Twenty mirror stay ready if the GTM flips.`);
  P(``);

  // Panel B2 — GEO attribution: which engine/channel sends the landing sessions
  P(`## B2 · GEO attribution — which engine/channel sends sessions (trovex.dev landing)`);
  P(`*Derived client-side from referrer host + UTM, merged onto every \`landing_view\`. **A floor, not a census:** AI-engine referrers are often stripped, so those sessions land in \`direct\`/\`unknown\` — a self-reported UTM (links WE tag) is the only reliable AI-engine signal. Read the TREND + the UTM'd share, not the absolute engine split.*`);
  P(``);
  const AI_ENGINES = new Set(["chatgpt", "perplexity", "claude", "gemini", "copilot"]);
  if (!trovexSite || geoRows == null) {
    P(`_GEO breakdown = **n/a**: ${!trovexSite ? "no `TROVEX_PLAUSIBLE_SITE_ID`" : "Plausible custom-prop breakdown unavailable"}. Cannot fabricate a source split._`);
  } else if (!geoRows.length) {
    P(`_0 \`landing_view\` events with a \`geo_source\` prop in this window — a real zero (no traffic yet, or events pre-date the geo-attribution deploy)._`);
  } else {
    const totalV = geoRows.reduce((s, r) => s + r.visitors, 0) || 1;
    const aiV = geoRows.filter((r) => AI_ENGINES.has(r.value)).reduce((s, r) => s + r.visitors, 0);
    P(`**AI-engine-sent sessions: ${aiV} of ${geoRows.reduce((s, r) => s + r.visitors, 0)} (${Math.round((aiV / totalV) * 100)}%)** — the GEO bet's on-site read.`);
    P(``);
    P(`| geo_source | Sessions | Share | AI engine? |`);
    P(`|-----------|---------:|------:|:----------:|`);
    for (const r of geoRows) P(`| ${r.value} | ${r.visitors} | ${Math.round((r.visitors / totalV) * 100)}% | ${AI_ENGINES.has(r.value) ? "✅" : "—"} |`);
    if (chanRows && chanRows.length) {
      P(``);
      P(`**By channel:** ${chanRows.map((r) => `${r.value} ${r.visitors}`).join(" · ")}.`);
    }
  }
  P(``);

  // Panel C
  P(`## C · 4-engine AI-citation panel — awareness, top of funnel`);
  if (!cite) {
    P(`_No \`reports/geo-citations-*.md\` found → **n/a**. Run \`geo-citation-monitor.mjs --save\` to populate the panel. AI citation has no rank API; it's a sampled snapshot, never fabricated._`);
  } else {
    P(`*Source: \`${cite.srcFile}\` (snapshot ${cite.srcDate}). Each engine is its own surface (~11% overlap); AI answers are non-deterministic — the TREND is the signal, not one run.*`);
    P(``);
    P(`| Engine | Status | Suite cited (all queries) |`);
    P(`|--------|--------|---------------------------|`);
    for (const e of cite.engines) P(`| ${e.name} | ${e.status} | ${e.share} |`);
    P(`| **Union (any engine)** | — | **${cite.union}** |`);
    P(``);
    P(`> An engine reading \`n/a\` has no key provisioned **or** every query errored (e.g. quota/429) — a zero sample, never a fabricated 0%. Fix the key/quota and re-run \`geo-citation-monitor.mjs\`.`);
  }
  P(``);

  // Panel D — dark funnel: self-report vs auto-attribution
  P(`## D · Dark funnel — self-report (\`how_heard\`) vs auto-attribution (\`channel\`)`);
  if (!dark) {
    P(`_Supabase \`leads\` unavailable → **n/a**. Cannot measure the self-report↔auto gap._`);
  } else if (dark.compared === 0) {
    P(`_No real lead carries a self-report yet → **n/a**. (${n(dark.noSelfReport)} lead(s) with no \`how_heard\`.)_`);
  } else {
    P(`*Per-lead reconciliation on Supabase \`leads\` (non-PII columns). \`channel\` = what auto-attribution captured at submit (UTM/referrer); \`how_heard\` = what the lead self-reports. **Dark funnel** = auto blind to a real source the lead named, or the two disagree — the share of pipeline whose true origin auto-attribution missed.*`);
    P(``);
    P(`| Reconciliation | Leads |`);
    P(`|----------------|------:|`);
    P(`| Auto agrees with self-report | ${dark.agree} |`);
    P(`| Auto disagrees with self-report | ${dark.disagree} |`);
    P(`| Auto blind (self-report names a real source) | ${dark.autoBlind} |`);
    P(`| Offline / direct self-report (auto can't attribute) | ${dark.offlineOrDirect} |`);
    P(`| No self-report (not comparable) | ${dark.noSelfReport} |`);
    P(``);
    P(`**Dark-funnel rate: ${dark.darkRate == null ? "n/a" : `${dark.darkRate}%`}** (${dark.darkCount} of ${dark.agree + dark.disagree + dark.autoBlind} comparable leads). _A high rate means auto-attribution is under-counting; at thin volume \`how_heard\` is the more reliable source signal — weight it, and tighten UTM coverage to shrink the gap._`);
  }
  P(``);

  // Panel D propagation — the savings-receipt dark-funnel virality (privacy-safe, no identity).
  P(`### D2 · Savings-receipt propagation — dark-funnel virality (no PII)`);
  if (!trovexSite) {
    P(`_trovex.dev Plausible site not set → **n/a**. (\`TROVEX_PLAUSIBLE_SITE_ID\` missing.)_`);
  } else {
    P(`*The shared savings receipt is anonymous by design (no email, nothing leaves the page — see trovex record \`audit-savings-privacy-by-design\`). So we measure PROPAGATION, never who: \`share_clicked\` = receipts shared FROM the site; \`utm_source=savings-share\` inflow = sessions that arrived VIA a shared receipt. A real team→team spread signal with zero PII. To attribute a share to a company (teamIntent → a Twenty lead) would need a separate opt-in capture — owner decision, not built.*`);
    P(``);
    P(`| Propagation signal | Value | Source |`);
    P(`|--------------------|------:|--------|`);
    P(`| Receipts shared from site (\`share_clicked\`) | ${shareClicks == null ? "n/a" : n(shareClicks)} | Plausible (trovex.dev) |`);
    P(`| Sessions arrived via a shared receipt (\`utm_source=savings-share\`) | ${savingsInflow == null ? "n/a" : n(savingsInflow)} | Plausible (trovex.dev) |`);
    if (shareByFormat && shareByFormat.length) {
      P(`| — by format | ${shareByFormat.map((r) => `${r.value}:${r.events}`).join(" · ")} | |`);
    }
    const propTotal = (shareClicks || 0) + (savingsInflow || 0);
    P(``);
    P(`**Receipt propagation this window: ${shareClicks == null && savingsInflow == null ? "n/a" : propTotal === 0 ? "0 — a real zero (no shares out, no shared-receipt inflow yet)" : `${n(shareClicks || 0)} shared · ${n(savingsInflow || 0)} inbound`}.** _Anonymous virality only; not a lead count. Rising inflow with no matching on-site share = off-site spread (copied link / posted badge) — the dark-funnel working._`);
  }
  P(``);

  // Panel E — Blog ROI (does the blog pay?)
  P(`## E · Blog ROI — does the blog pay? (citation + blog→install + blog→lead)`);
  P(`*Decide the blog investment with data, not vibes (cmo). 60+ posts; the question = do they drive citations, installs, or consulting leads. Blog→install/lead need blog→trovex links UTM-tagged (\`utm_campaign=blog\`) — until then they degrade to honest n/a/0, never fabricated.*`);
  P(``);
  P(`| Signal | Value | Source |`);
  P(`|--------|------:|--------|`);
  P(`| AI-citation share (any engine) | ${cite ? cite.union : "n/a"} | geo citation-monitor${cite ? ` (${cite.srcDate})` : " (no report)"} |`);
  P(`| Blog → install-intent (\`github_clicked\`, utm_campaign=blog) | ${trovexSite ? `${n(blogInstall)} / ${n(blogLanding)} blog views` : "n/a"} | Plausible (trovex.dev) |`);
  P(`| Blog → consulting lead (source=blog) | ${blogLeads == null ? "n/a" : blogLeads.length} | Supabase \`leads\` |`);
  P(``);
  {
    const inst = Number(blogInstall) || 0;
    const ld = blogLeads ? blogLeads.length : null;
    const verdict = (!trovexSite && !cite && blogLeads == null)
      ? "n/a — citation + blog-funnel sources not wired yet"
      : (inst === 0 && (ld || 0) === 0)
        ? "no blog-attributed install or lead yet — HOLD judgment until blog→trovex links carry `utm_campaign=blog` + reach lands; if it persists at 0 with real traffic, that's the signal to cut blog spend"
        : "blog is producing attributable signal (see rows) — keep + double down on what converts";
    P(`> **Verdict:** ${verdict}. _A real 0 (with traffic) = not converting; n/a = not yet measurable (untagged links / no citation run)._`);
  }
  P(``);

  // Panel F — Lead machine (cmo #1: autonomous lead loop — capture→score→surface)
  P(`## F · Lead machine — booked calls + team signal (the autonomous loop)`);
  P(`*The loop's output: a call booked + the team-buying signal scored into Twenty (\`twenty-lead-scorer\`). Booked call = opp at MEETING+ (a call is booked/held). teamIntent = company-domain cluster (2+ from one company) = a team evaluating us, the consulting signal. Honest n/a if Twenty unavailable.*`);
  P(``);
  P(`| Metric | Value |`);
  P(`|--------|------:|`);
  P(`| Booked calls (opp MEETING+, all-time) | ${lmBooked == null ? "n/a" : lmBooked} |`);
  P(`| Booked calls in window (${w.label}) | ${lmBookedWin == null ? "n/a" : lmBookedWin} |`);
  P(`| Qualified opportunities (past NEW) | ${n(totalQual)} |`);
  P(`| teamIntent leads (team signal, scored) | ${lmTeam == null ? "n/a" : lmTeam} |`);
  P(`| Tiered leads (A / B / C) | ${lmTiers == null ? "n/a" : `${lmTiers.A} / ${lmTiers.B} / ${lmTiers.C}`}${lmTiers && lmTiers.unset ? ` _(${lmTiers.unset} untiered)_` : ""} |`);
  P(`| Suite-sourced qualified (north star) | ${n(suiteQual)} |`);
  P(``);
  P(`> Booked-calls/day is the lead-machine throughput KPI — at thin volume it's a cumulative count, not yet a rate (needs a booked-date field for per-day). teamIntent leads are surfaced for the owner's yes/no (donna pings on a HOT team cluster). The signal is in the CRM, not a CTA.`);
  P(``);

  // Availability legend
  P(`## Data availability (no fabrication)`);
  P(`| Source | Status |`);
  P(`|--------|--------|`);
  P(`| Twenty CRM — consulting pipeline (system of record) | ${process.env.TWENTY_API_KEY && process.env.TWENTY_BASE_URL ? "live" : "n/a (key missing)"} |`);
  P(`| Plausible — tsukumo.ch (consulting events) | ${tsukumoSite && process.env.PLAUSIBLE_STATS_API_KEY ? "live" : "n/a (key/site missing)"} |`);
  P(`| Plausible — trovex.dev (waitlist web-funnel) | ${trovexSite && process.env.PLAUSIBLE_STATS_API_KEY ? "live" : "n/a (TROVEX_PLAUSIBLE_SITE_ID missing)"} |`);
  P(`| Supabase — leads (raw capture) + waitlist | ${process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY ? "live" : "n/a (key missing)"} |`);
  P(`| AI-citation panel (geo-citation-monitor report) | ${cite ? `live (${cite.srcDate})` : "n/a (no report)"} |`);
  P(``);
  P(`*Privacy: PII (names/emails) lives in Twenty (the CRM) where it belongs; this report surfaces only counts + coarse source/stage. Supabase analytics reads stay non-PII. Reach metrics (citations, visits, stars) are inputs; the north star is qualified consulting leads. Detail lives in the operator docs (weekly-digest, waitlist-funnel-report, geo-citation panel) — this scoreboard is the one-screen roll-up.*`);

  const out = md.join("\n");
  console.log(out);
  process.stderr.write(`scoreboard: north-star(suite-qualified) ${n(suiteQual)}, waitlist ${n(wlCount)}, citation-union ${cite ? cite.union : "n/a"}\n`);
  if (process.argv.includes("--save")) {
    const dir = join(__dir, "reports");
    mkdirSync(dir, { recursive: true });
    const path = join(dir, `north-star-scoreboard-${date}.md`);
    writeFileSync(path, out + "\n");
    process.stderr.write(`also saved ${path} (--save)\n`);
  }
}

main().catch((e) => { console.error(String(e)); process.exit(1); });
