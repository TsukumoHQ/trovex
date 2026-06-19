#!/usr/bin/env node
/**
 * Plausible site snapshot — ONE honest read of tsukumo.ch (aggregate + sources + pages +
 * goals + countries) so "what's the traffic?" is a repeatable command, not an ad-hoc curl.
 *
 * HONESTY is the whole point. Two guards, both enforced here:
 *   1. Hygiene date-floor. Everything before HYGIENE_START is crawler + our own e2e
 *      verification (see traffic-hygiene.md) — NOT organic. The reader refuses to silently
 *      blend it: --since defaults to the floor, and if you ask for an earlier window it
 *      prints a loud BASELINE-NOISE banner instead of a clean number.
 *   2. Internal-traffic tell. Implausibly low bounce / high duration ⇒ the window is still
 *      mostly us (team browsers without localStorage.plausible_ignore + UA-spoofed headless).
 *      The reader flags it so nobody quotes test traffic as demand.
 *
 * No fabricated data: prints exactly what the Stats API returns; a metric with no data reads
 * 0/—, never a guess.
 *
 * Keys: PLAUSIBLE_STATS_API_KEY + PLAUSIBLE_SITE_ID from env (out-of-git).
 *
 * Usage:  set -a; . ~/.config/trovex-growth/plausible.env; set +a
 *         node growth/analytics/plausible-snapshot.mjs                 # clean window (since hygiene floor)
 *         node growth/analytics/plausible-snapshot.mjs --since 2026-06-18
 *         node growth/analytics/plausible-snapshot.mjs --since 2026-06-01   # earlier ⇒ noise banner
 *         node growth/analytics/plausible-snapshot.mjs --save            # also write reports/plausible-snapshot-<date>.md
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));
const API = "https://plausible.io/api/v1/stats";

// First date from which a read can be called "organic-ish": distribution/launch start. Before
// this, traffic is documented baseline-noise (crawler + our verification) — see traffic-hygiene.md.
// Bump this to the real distribution date once launch fires.
const HYGIENE_START = "2026-06-18";

function ymd(d) { return d.toISOString().slice(0, 10); }
function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : undefined;
}

async function q(key, site, path) {
  const res = await fetch(`${API}/${path}&site_id=${site}`, { headers: { Authorization: `Bearer ${key}` } });
  if (!res.ok) throw new Error(`plausible ${res.status} on ${path.split("?")[0]}`);
  return (await res.json()).results;
}

async function main() {
  const key = process.env.PLAUSIBLE_STATS_API_KEY;
  const site = process.env.PLAUSIBLE_SITE_ID;
  if (!key || !site) {
    console.error("Missing PLAUSIBLE_STATS_API_KEY / PLAUSIBLE_SITE_ID. Load:\n  set -a; . ~/.config/trovex-growth/plausible.env; set +a");
    process.exit(2);
  }
  const today = ymd(new Date());
  const since = arg("--since") || HYGIENE_START;
  const range = `period=custom&date=${since},${today}`;
  const beforeFloor = since < HYGIENE_START;

  const [agg, sources, pages, countries, goals] = await Promise.all([
    q(key, site, `aggregate?${range}&metrics=visitors,visits,pageviews,bounce_rate,visit_duration`),
    q(key, site, `breakdown?${range}&property=visit:source&metrics=visitors,pageviews&limit=15`),
    q(key, site, `breakdown?${range}&property=event:page&metrics=visitors,pageviews&limit=15`),
    q(key, site, `breakdown?${range}&property=visit:country&metrics=visitors&limit=10`),
    q(key, site, `breakdown?${range}&property=event:goal&metrics=visitors,events&limit=20`),
  ]);

  const v = (m) => (agg[m] ? agg[m].value : 0);
  const bounce = v("bounce_rate");
  const dur = v("visit_duration");
  // Internal-traffic tell: real cold traffic rarely bounces <20% or averages >4min.
  const looksInternal = v("visits") > 0 && (bounce < 20 || dur > 240);

  const out = [];
  const p = (s) => out.push(s);

  p(`# Plausible snapshot — ${site} — ${since} → ${today}`);
  p("");
  p(`*Owner: analytics-lead · Plausible Stats API · prints exactly what the API returns, no fabrication.*`);
  p("");
  if (beforeFloor) {
    p(`> ⚠️ **BASELINE-NOISE WINDOW.** \`--since ${since}\` is before the hygiene floor (${HYGIENE_START}).`);
    p(`> Pre-floor traffic = crawler + our own e2e verification, **not organic** (traffic-hygiene.md). Do NOT report as demand.`);
    p("");
  }
  if (looksInternal) {
    p(`> ⚠️ **Likely mostly internal/test traffic.** bounce ${bounce}% · avg ${Math.round(dur)}s (~${(dur / 60).toFixed(1)}min)`);
    p(`> — implausible for cold traffic. Almost certainly team browsers (no \`localStorage.plausible_ignore\`) + UA-spoofed headless. Treat as a wiring check, not demand.`);
    p("");
  }
  p(`**Visitors ${v("visitors")} · Visits ${v("visits")} · Pageviews ${v("pageviews")} · Bounce ${bounce}% · Avg ${Math.round(dur)}s**`);
  p("");

  const tbl = (title, rows, cols) => {
    p(`## ${title}`);
    if (!rows || !rows.length) { p("_no data_"); p(""); return; }
    p(`| ${cols.map((c) => c.h).join(" | ")} |`);
    p(`|${cols.map(() => "---").join("|")}|`);
    for (const r of rows) p(`| ${cols.map((c) => r[c.k] ?? "—").join(" | ")} |`);
    p("");
  };

  tbl("Sources", sources, [{ h: "Source", k: "source" }, { h: "Visitors", k: "visitors" }, { h: "Pageviews", k: "pageviews" }]);
  tbl("Top pages", pages, [{ h: "Page", k: "page" }, { h: "Visitors", k: "visitors" }, { h: "Pageviews", k: "pageviews" }]);
  tbl("Countries", countries, [{ h: "Country", k: "country" }, { h: "Visitors", k: "visitors" }]);
  tbl("Conversions (goals)", goals, [{ h: "Goal", k: "goal" }, { h: "Visitors", k: "visitors" }, { h: "Events", k: "events" }]);

  if (!goals || !goals.length) {
    out.splice(out.length - 1, 0, "_No goals configured or no conversions in window._");
  }

  const md = out.join("\n");
  console.log(md);

  if (process.argv.includes("--save")) {
    const dir = join(__dir, "reports");
    mkdirSync(dir, { recursive: true });
    const path = join(dir, `plausible-snapshot-${today}.md`);
    writeFileSync(path, md + "\n");
    console.error(`\nwrote ${path}`);
  }
}

main().catch((e) => { console.error(String(e)); process.exit(1); });
