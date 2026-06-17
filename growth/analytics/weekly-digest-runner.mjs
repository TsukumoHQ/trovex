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
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));
const ymd = (d) => d.toISOString().slice(0, 10);

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
  const [visit, intent, cta, contact, suiteClick, assessAll, assessSuite] = await Promise.all([
    evAgg(sid, w, "tsukumo_visit"), evAgg(sid, w, "intent_page_view"), evAgg(sid, w, "cta_clicked"),
    evAgg(sid, w, "contact_clicked"), evAgg(sid, w, "suite_to_agency_click"),
    evAgg(sid, w, "assessment_request"), evAgg(sid, w, "assessment_request", ";event:props:source==suite"),
  ]);
  const geo = await plausible(`breakdown?site_id=${sid}&period=custom&date=${w.start},${w.end}&property=event:props:geo_source&filters=event:name==tsukumo_visit&metrics=events`).then((d) => d.results || []).catch(() => []);

  // --- Supabase: leads (non-PII) + qualified bands + waitlist ---
  let leads = [], wl = [];
  try { leads = await supabase(`leads?project=eq.tsukumo&created_at=gte.${w.start}&select=lead_band,channel,how_heard`); } catch { leads = null; }
  try { wl = await supabase(`waitlist?created_at=gte.${w.start}&select=project`); } catch { wl = null; }
  const isSuite = (l) => l.channel === "oss_suite" || ["wraith", "trovex", "yoru"].includes((l.how_heard || "").toLowerCase());
  const band = (b) => (leads ? leads.filter((l) => l.lead_band === b).length : null);
  const qualified = leads ? leads.filter((l) => l.lead_band === "hot" || l.lead_band === "warm").length : null;
  const qualifiedSuite = leads ? leads.filter((l) => (l.lead_band === "hot" || l.lead_band === "warm") && isSuite(l)).length : null;

  const date = ymd(new Date());
  const rate = (a, b) => (a == null || !b ? "n/a" : `${Math.round((a / b) * 100)}%`);
  const md = [
    `# Suite → Agency — Weekly Digest (auto), ${date}`,
    ``,
    `*Auto-assembled by \`weekly-digest-runner.mjs\` · window ${w.start}→${w.end} · Plausible + Supabase (live). No fabricated data; \`n/a\` = source unavailable. North star = \`assessment_request\` where \`source=suite\`.*`,
    ``,
    `## Headline`,
    `- **North star — suite-sourced assessment requests: ${n(assessSuite)}.** All assessment requests: ${n(assessAll)}.`,
    `- **Qualified leads (hot+warm): ${n(qualified)}** (suite-attributed: ${n(qualifiedSuite)}). Bands — hot ${n(band("hot"))} · warm ${n(band("warm"))} · cold ${n(band("cold"))}.`,
    `- **Waitlist signups (all projects): ${wl ? wl.length : "n/a"}.**`,
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
    `**Rates:** visit→assessment ${rate(assessAll, visit)} · visit→qualified ${qualified == null || !visit ? "n/a" : rate(qualified, visit)}.`,
    ``,
    `## GEO / channel (tsukumo_visit by geo_source)`,
    geo.length ? `| geo_source | visits |\n|------------|------:|\n${geo.map((g) => `| ${g.geo_source} | ${g.events} |`).join("\n")}` : `_no visits in window_`,
    ``,
    `## Other reads (run separately)`,
    `- GEO citation share — \`geo-citation-monitor.mjs\` → \`reports/geo-citations-*.md\`.`,
    `- Per-post performance + read-depth — \`blog-performance.mjs\` → \`reports/blog-performance-*.md\`.`,
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
  console.log(`wrote ${outPath} — north-star(suite) ${n(assessSuite)}, qualified ${n(qualified)}, visits ${n(visit)}`);
}

main();
