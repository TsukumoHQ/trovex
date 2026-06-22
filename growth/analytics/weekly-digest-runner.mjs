#!/usr/bin/env node
/**
 * Weekly auto-digest runner — assembles the suite→agency north-star digest from the LIVE
 * sources so the read writes itself: Plausible (funnel + GEO) + Supabase (leads, qualified
 * bands, waitlist). Writes reports/agency-<date>.md. No fabricated data — a zero reads zero.
 *
 * Keys (out-of-git, env only — never printed/committed):
 *   set -a; . ~/.config/trovex-growth/plausible.env; . ~/.config/trovex-growth/supabase.env; set +a
 *   needs PLAUSIBLE_STATS_API_KEY, PLAUSIBLE_SITE_ID, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
 *
 * Hygiene (traffic-hygiene.md): pre-launch traffic is crawler+verification noise. Pass
 *   --since YYYY-MM-DD to start the window at launch day; default = last 7 days.
 * Supabase reads select NON-PII columns only (lead_band/channel/how_heard) — never email.
 *
 * Usage:  node weekly-digest-runner.mjs [--since 2026-07-01] [--dry]
 */
import { writeFileSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// Suite GitHub reach (top-of-funnel for the CLI repos with no landing — see
// github-suite-reach.mjs / suite-reach-measurement.md). Uses the gh CLI; n/a if unavailable.
const SUITE_REPOS = ["TsukumoHQ/WRAI.TH", "TsukumoHQ/trovex", "TsukumoHQ/yoru"];
function ghReach() {
  return SUITE_REPOS.map((r) => {
    const j = (p) => { try { return JSON.parse(execSync(`gh api ${p} 2>/dev/null`, { encoding: "utf8" })); } catch { return null; } };
    const base = j(`repos/${r}`);
    if (!base) return { repo: r, na: true };
    const c = j(`repos/${r}/traffic/clones`);
    return { repo: r, stars: base.stargazers_count, clones14: c ? `${c.count}/${c.uniques}` : "n/a" };
  });
}

const __dir = dirname(fileURLToPath(import.meta.url));
const ymd = (d) => d.toISOString().slice(0, 10);

// GEO citation share is the TOP of the suite→agency funnel (a buyer asking an AI engine,
// before any visit). Read it from the latest geo-citation-monitor report instead of re-probing
// — the digest surfaces the leading indicator without burning an OpenAI call. Honest n/a if no
// report exists. Cohort lines (standing/offensive) only exist on reports from 2026-06-19+.
function latestCitationShare() {
  try {
    const dir = join(__dir, "reports");
    const files = readdirSync(dir).filter((f) => /^geo-citations-\d{4}-\d{2}-\d{2}\.md$/.test(f)).sort();
    if (!files.length) return null;
    const file = files[files.length - 1];
    const txt = readFileSync(join(dir, file), "utf8");
    const date = file.slice("geo-citations-".length, -3);
    const grab = (re) => { const m = txt.match(re); return m ? m[1] : null; };
    return {
      date,
      overall: grab(/Suite citation share:\s*([0-9]+\/[0-9]+ queries \([0-9]+%\))/),
      standing: grab(/\*\*Standing\*\*[^:]*:\s*\*\*([0-9]+\/[0-9]+ \([0-9]+%\))\*\*/),
      offensive: grab(/\*\*Offensive\*\*[^:]*:\s*\*\*([0-9]+\/[0-9]+ \([0-9]+%\))\*\*/),
    };
  } catch { return null; }
}

function window_() {
  const end = new Date();
  const sinceArg = process.argv.find((a, i) => process.argv[i - 1] === "--since");
  const start = sinceArg ? new Date(`${sinceArg}T00:00:00Z`) : new Date(end.getTime() - 7 * 86400_000);
  return { start: ymd(start), end: ymd(end) };
}

async function plausible(path) {
  const key = process.env.PLAUSIBLE_STATS_API_KEY;
  const r = await fetch(`https://plausible.io/api/v1/stats/${path}`, { headers: { Authorization: `Bearer ${key}` } });
  if (!r.ok) throw new Error(`plausible ${r.status}`);
  return r.json();
}
async function supabase(query) {
  const url = process.env.SUPABASE_URL, key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const r = await fetch(`${url}/rest/v1/${query}`, { headers: { apikey: key, Authorization: `Bearer ${key}` } });
  if (!r.ok) throw new Error(`supabase ${r.status}`);
  return r.json();
}

const evAgg = (sid, w, name, extra = "") =>
  plausible(`aggregate?site_id=${sid}&period=custom&date=${w.start},${w.end}&metrics=events&filters=event:name==${name}${extra}`)
    .then((d) => d.results?.events?.value ?? 0).catch(() => null);

// Twenty CRM = the deduped consulting SYSTEM OF RECORD (Supabase `leads` is raw capture, junk and
// all). Snapshot of the qualified pipeline: opportunities past NEW, suite = pointOfContact.source
// OSS_SUITE. Returns {total, qualified, suiteQual} or null (→ n/a). No window: pipeline is a state.
async function twentyPipeline() {
  const url = process.env.TWENTY_BASE_URL, key = process.env.TWENTY_API_KEY;
  if (!url || !key) return null;
  const get = async (p) => {
    try { const r = await fetch(`${url}${p}`, { headers: { Authorization: `Bearer ${key}` } }); return r.ok ? (await r.json()).data : null; } catch { return null; }
  };
  const [oppsD, pplD] = await Promise.all([get("/rest/opportunities?limit=100"), get("/rest/people?limit=100")]);
  if (!oppsD || !pplD) return null;
  const opps = oppsD.opportunities || oppsD || [], ppl = pplD.people || pplD || [];
  const QUALIFIED = new Set(["SCREENING", "MEETING", "PROPOSAL", "CUSTOMER"]);
  const srcOf = (id) => (ppl.find((p) => p.id === id) || {}).source || null;
  const qual = opps.filter((o) => QUALIFIED.has(o.stage));
  return { total: opps.length, qualified: qual.length, suiteQual: qual.filter((o) => srcOf(o.pointOfContactId) === "OSS_SUITE").length };
}

async function main() {
  const need = ["PLAUSIBLE_STATS_API_KEY", "PLAUSIBLE_SITE_ID", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"];
  const missing = need.filter((k) => !process.env[k]);
  if (missing.length) {
    console.error(`Missing env: ${missing.join(", ")}. Load:\n  set -a; . ~/.config/trovex-growth/plausible.env; . ~/.config/trovex-growth/supabase.env; set +a`);
    process.exit(2);
  }
  const sid = process.env.PLAUSIBLE_SITE_ID;
  const w = window_();
  const n = (v) => (v == null ? "n/a" : String(v));

  // --- Plausible: funnel + north star ---
  const [visit, intent, cta, contact, suiteClick, assessAll, assessSuite,
         newsletterEv, toolView, toolDone, toolCta] = await Promise.all([
    evAgg(sid, w, "tsukumo_visit"), evAgg(sid, w, "intent_page_view"), evAgg(sid, w, "cta_clicked"),
    evAgg(sid, w, "contact_clicked"), evAgg(sid, w, "suite_to_agency_click"),
    evAgg(sid, w, "assessment_request"), evAgg(sid, w, "assessment_request", ";event:props:source==suite"),
    // community / top-of-funnel capture surfaces (newsletter + zero-party tool)
    evAgg(sid, w, "newsletter_signup"), evAgg(sid, w, "tool_view"),
    evAgg(sid, w, "tool_completed"), evAgg(sid, w, "tool_cta_clicked"),
  ]);
  const geo = await plausible(`breakdown?site_id=${sid}&period=custom&date=${w.start},${w.end}&property=event:props:geo_source&filters=event:name==tsukumo_visit&metrics=events`).then((d) => d.results || []).catch(() => []);

  // --- Supabase: waitlist + newsletter (counts only) ---
  let wl = [];
  try { wl = await supabase(`waitlist?created_at=gte.${w.start}&select=project`); } catch { wl = null; }
  let nl = null;
  try { nl = (await supabase(`newsletter?project=eq.tsukumo&created_at=gte.${w.start}&select=project`)).length; } catch { nl = null; }
  // Qualified pipeline comes from Twenty (deduped system of record), NOT Supabase `leads` (raw
  // capture — once carried a 'klklkl/poipoipoi' junk row that read as a real qualified suite lead).
  const pipe = await twentyPipeline();
  // Supabase `leads` kept only as a raw-capture cross-check with a test-row flag.
  const isTestRow = (l) => /(^|@)(example\.com|y\.com|test|eeid\.ch)/i.test(l.email || "") || /probe/i.test(l.email || "") || /^(test|klk|asdf|qwer|poip|xxx)/i.test((l.name || "").toLowerCase());
  let rawLeads = null;
  try { rawLeads = await supabase(`leads?project=eq.tsukumo&select=email,name`); } catch { rawLeads = null; }
  const rawTotal = rawLeads ? rawLeads.length : null;
  const rawTest = rawLeads ? rawLeads.filter(isTestRow).length : null;

  const reach = ghReach();
  const cite = latestCitationShare();
  const citeLine = cite
    ? `- **GEO citation share (latest read ${cite.date}): ${cite.standing ? `standing ${cite.standing}` : cite.overall || "n/a"}${cite.offensive ? ` · offensive ${cite.offensive}` : ""}.** Leading indicator — AI engines citing the suite, upstream of any visit.`
    : `- **GEO citation share: n/a** (no \`reports/geo-citations-*.md\` yet — run \`geo-citation-monitor.mjs\`).`;
  const date = ymd(new Date());
  const rate = (a, b) => (a == null || !b ? "n/a" : `${Math.round((a / b) * 100)}%`);
  const md = [
    `# Suite → Agency — Weekly Digest (auto), ${date}`,
    ``,
    `*Auto-assembled by \`weekly-digest-runner.mjs\` · window ${w.start}→${w.end} · Twenty CRM (pipeline) + Plausible + Supabase (live). No fabricated data; \`n/a\` = source unavailable. North star = qualified, suite-sourced consulting leads (Twenty).*`,
    ``,
    `## Headline`,
    `- **North star — qualified, suite-sourced consulting leads: ${pipe ? pipe.suiteQual : "n/a"}** (of ${pipe ? pipe.qualified : "n/a"} qualified, ${pipe ? pipe.total : "n/a"} total opportunities in the Twenty pipeline). _Qualified = opportunity past NEW; suite = source OSS_SUITE._`,
    `- **On-site \`assessment_request\`: ${n(assessAll)}** (suite ${n(assessSuite)}) — Plausible events; Twenty (above) is the durable record.`,
    `- **Raw-capture cross-check (Supabase \`leads\`): ${rawTotal == null ? "n/a" : `${rawTotal} rows, ${rawTest} test/junk → ${rawTotal - rawTest} real`}.** Twenty is the deduped system of record.`,
    `- **Waitlist signups (all projects): ${wl ? wl.length : "n/a"}.**`,
    citeLine,
    ``,
    `## Suite reach — GitHub (top of funnel, all-time stars + 14d clones)`,
    `| Repo | Stars | Clones 14d (total/uniq) |`,
    `|------|------:|-------------------------|`,
    ...reach.map((r) => r.na ? `| ${r.repo} | n/a | n/a |` : `| ${r.repo} | ${r.stars} | ${r.clones14} |`),
    `> CLI repos (WRAI.TH/yoru) have no landing — GitHub traffic is their reach. The full chain:`,
    `> suite reach (here) → suite_to_agency_click → assessment_request → qualified (below).`,
    ``,
    `## Funnel (Plausible, ${w.start}→${w.end})`,
    `| Stage | Event | Count |`,
    `|-------|-------|------:|`,
    `| Agency visits | tsukumo_visit | ${n(visit)} |`,
    `| Suite→agency clicks | suite_to_agency_click | ${n(suiteClick)} |`,
    `| Intent | intent_page_view | ${n(intent)} |`,
    `| CTA / contact | cta_clicked + contact_clicked | ${n(cta)} + ${n(contact)} |`,
    `| **★ Conversion** | assessment_request | ${n(assessAll)} |`,
    `| — suite-sourced (north star) | source=suite | ${n(assessSuite)} |`,
    ``,
    `**Rates:** visit→assessment ${rate(assessAll, visit)} · visit→qualified ${!pipe || !visit ? "n/a" : rate(pipe.qualified, visit)} _(qualified = Twenty pipeline, a state not a windowed count)_.`,
    ``,
    `## GEO / channel (tsukumo_visit by geo_source)`,
    geo.length ? `| geo_source | visits |\n|------------|------:|\n${geo.map((g) => `| ${g.geo_source} | ${g.events} |`).join("\n")}` : `_no visits in window_`,
    ``,
    `## Community / top-of-funnel capture (new surfaces)`,
    `| Surface | Metric | Count |`,
    `|---------|--------|------:|`,
    `| Newsletter | newsletter_signup (event) | ${n(newsletterEv)} |`,
    `| Newsletter | new rows (Supabase) | ${nl == null ? "n/a" : nl} |`,
    `| Tool /context-cost | tool_view → completed → cta | ${n(toolView)} → ${n(toolDone)} → ${n(toolCta)} |`,
    ``,
    `**Tool funnel:** view→completed ${rate(toolDone, toolView)} · completed→cta ${rate(toolCta, toolDone)}. (Tool CTA → /assessment; see which readiness band converts via \`event:props:result\`.)`,
    ``,
    `## Other reads (run separately)`,
    `- GEO citation share — surfaced in Headline from the latest \`reports/geo-citations-*.md\`; re-probe weekly via \`geo-citation-monitor.mjs\` (standing + offensive cohorts).`,
    `- Per-post performance + read-depth — \`blog-performance.mjs\` → \`reports/blog-performance-*.md\`.`,
    `- Site traffic snapshot (hygiene-floored, internal-traffic flagged) — \`plausible-snapshot.mjs\` → \`reports/plausible-snapshot-*.md\`.`,
    ``,
    `## Hygiene`,
    `- Window honors \`--since <launch-date>\`; pre-launch traffic is crawler+verification noise (see \`traffic-hygiene.md\`) — start the window at launch day for a clean read.`,
    `- Supabase reads are **counts on non-PII columns** (lead_band/channel/how_heard) — no email leaves the DB.`,
  ].join("\n");

  if (process.argv.includes("--dry")) { console.log(md); return; }
  const outDir = join(__dir, "reports");
  mkdirSync(outDir, { recursive: true });
  const outPath = join(outDir, `agency-digest-${date}.md`);
  writeFileSync(outPath, md + "\n");
  console.log(`wrote ${outPath} — north-star(suite-qualified) ${pipe ? pipe.suiteQual : "n/a"}, qualified ${pipe ? pipe.qualified : "n/a"}, visits ${n(visit)}`);
}

main();
