#!/usr/bin/env node
/**
 * Social per-variant readout — the test→measure→reproduce engine on the social volume auto-post.
 *
 * social-lead tags EVERY post's outbound link with `utm_content=brand_net_hook_fmt_angle_len`
 * (positional, closed vocab — locked 2026-06-20). This reads Plausible by `visit:utm_content`,
 * parses the variant code, and rolls reach + funnel signal up PER DIMENSION so we can see which
 * hook / format / angle / length / brand / network actually drives the funnel → WINNERS to
 * reproduce, LOSERS to kill. Segmented by campaign (beta-waitlist = trovex tool, agency-launch).
 *
 * HONESTY: prints exactly what the Stats API returns. A variant/dimension with no data reads
 * `n/a` (or 0), never a guess. Posts that just started ramping ⇒ mostly n/a early — that's the
 * honest baseline, not a miss. A malformed utm_content is bucketed as `unparsed`, not silently
 * dropped, so tagging gaps are visible.
 *
 * SCOPE: Plausible half only (link-clicks via utm_content visits + goal conversions). NATIVE
 * ENGAGEMENT (impressions / likes / reshares) lives in Metricool — there is NO Metricool API key
 * in env, so a runner can't pull it. That column reads `n/a (metricool)` until METRICOOL_API_KEY
 * lands; until then fold engagement in via the metricool MCP (getAnalyticsDataByMetrics) each cycle.
 *
 * Keys: PLAUSIBLE_STATS_API_KEY + PLAUSIBLE_SITE_ID (out-of-git). For the trovex.dev tool funnel
 * pass --site trovex.dev (or set PLAUSIBLE_SITE_ID to it); default = the configured site.
 *
 * Output: prints the readout to STDOUT (owner rule: rien en md → pipe into trovex_write).
 *         `--save` also drops reports/social-variant-<date>.md. `--since YYYY-MM-DD` sets the window.
 *
 * Usage:  set -a; . ~/.config/trovex-growth/plausible.env; set +a
 *         node growth/analytics/social-variant-readout.mjs --since 2026-06-20
 *         node growth/analytics/social-variant-readout.mjs --site trovex.dev --since 2026-06-20
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));
const API = "https://plausible.io/api/v1/stats";

// The locked variant taxonomy (positional). Keep IN SYNC with social-lead's tagging contract.
const DIMS = ["brand", "net", "hook", "fmt", "angle", "len"];
const VOCAB = {
  brand: ["founder", "company"],
  net: ["x", "li", "th"],
  hook: ["question", "stat", "contrarian", "story", "howto"],
  fmt: ["single", "thread", "carousel", "image", "text"],
  angle: ["tokencost", "ssot", "geo", "consulting", "proof", "meta"],
  len: ["short", "mid", "long"],
};
// Funnel goals that count as "signal" (the point of a post). Tool funnel = waitlist; agency = assessment.
const GOALS = ["waitlist_submitted", "assessment_request", "github_clicked"];

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def;
}
function ymd(d) { return d.toISOString().slice(0, 10); }

async function q(key, site, path) {
  const url = `${API}/${path}${path.includes("?") ? "&" : "?"}site_id=${encodeURIComponent(site)}`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${key}` } });
  if (!res.ok) throw new Error(`HTTP ${res.status} on ${path.split("?")[0]}`);
  return (await res.json()).results || [];
}

// Parse a positional utm_content code into {brand,net,hook,fmt,angle,len} or null if malformed.
function parseVariant(code) {
  if (!code) return null;
  const parts = String(code).toLowerCase().split("_");
  if (parts.length !== DIMS.length) return null;
  const out = {};
  for (let i = 0; i < DIMS.length; i++) {
    const d = DIMS[i];
    if (!VOCAB[d].includes(parts[i])) return null; // unknown value = treat as unparsed (visible)
    out[d] = parts[i];
  }
  return out;
}

async function main() {
  const key = process.env.PLAUSIBLE_STATS_API_KEY;
  const site = arg("--site", process.env.PLAUSIBLE_SITE_ID);
  if (!key || !site) {
    console.error("Missing PLAUSIBLE_STATS_API_KEY / PLAUSIBLE_SITE_ID. Load:\n  set -a; . ~/.config/trovex-growth/plausible.env; set +a");
    process.exit(2);
  }
  const since = arg("--since", ymd(new Date(Date.now() - 7 * 864e5)));
  const today = ymd(new Date());
  const range = `period=custom&date=${since},${today}`;

  // Reach per variant (a visit carrying utm_content = someone clicked the post link).
  const reach = await q(key, site, `breakdown?${range}&property=visit:utm_content&metrics=visitors,pageviews&limit=200`);
  // Conversions per variant, one breakdown per goal (goal filter changes the population to converters).
  const goalRows = {};
  for (const g of GOALS) {
    try {
      goalRows[g] = await q(key, site, `breakdown?${range}&property=visit:utm_content&metrics=visitors&filters=event:goal==${encodeURIComponent(g)}&limit=200`);
    } catch { goalRows[g] = null; } // goal not configured on this site ⇒ n/a, not 0
  }
  const convOf = (g, code) => {
    if (!goalRows[g]) return null;
    const r = goalRows[g].find((x) => x.utm_content === code);
    return r ? r.visitors : 0;
  };

  // Build per-variant records.
  const records = reach.map((r) => {
    const code = r.utm_content || "(none)";
    const v = parseVariant(code);
    const conv = {};
    let signal = 0;
    for (const g of GOALS) { const c = convOf(g, code); conv[g] = c; if (typeof c === "number") signal += c; }
    return { code, variant: v, visitors: r.visitors || 0, conv, signal, parsed: !!v };
  });

  const totalReach = records.reduce((a, r) => a + r.visitors, 0);
  const unparsed = records.filter((r) => !r.parsed && r.code !== "(none)");

  // Per-dimension rollup: for each dim value, sum reach + signal across parsed variants.
  function rollup(dim) {
    const acc = {};
    for (const val of VOCAB[dim]) acc[val] = { reach: 0, signal: 0, n: 0 };
    for (const r of records) {
      if (!r.variant) continue;
      const val = r.variant[dim];
      acc[val].reach += r.visitors; acc[val].signal += r.signal; acc[val].n += 1;
    }
    return Object.entries(acc)
      .map(([val, x]) => ({ val, ...x, cvr: x.reach ? +(100 * x.signal / x.reach).toFixed(1) : null }))
      .sort((a, b) => (b.signal - a.signal) || (b.reach - a.reach));
  }

  const date = today;
  const md = [];
  md.push(`# Social per-variant readout — ${date}  (site: ${site})`);
  md.push(``);
  md.push(`*Owner: analytics-lead · window ${since}→${today} · Plausible by utm_content. Variant taxonomy locked w/ social-lead (\`brand_net_hook_fmt_angle_len\`). Honest: no data reads n/a/0; malformed tags bucketed \`unparsed\`, not dropped. Native engagement (impressions/likes/reshares) = n/a here (no Metricool API key) → fold via metricool MCP each cycle.*`);
  md.push(``);
  md.push(`**Tagged reach this window: ${totalReach} link-visits across ${records.filter((r) => r.parsed).length} parsed variant(s).**`);
  if (totalReach === 0) md.push(`\n_Zero tagged reach yet — posts just ramping, or utm_content not landing. Honest early baseline; re-run as volume accrues._`);
  if (unparsed.length) md.push(`\n⚠️ **${unparsed.length} unparsed utm_content** (tagging drift — fix at source): ${unparsed.map((u) => `\`${u.code}\``).slice(0, 8).join(", ")}`);
  md.push(``);

  // Winners/losers per dimension.
  md.push(`## By dimension — winners (reproduce) → losers (kill)`);
  md.push(`*Sorted by funnel signal (waitlist+assessment+github_clicked converters), then reach. CVR = signal/reach.*`);
  for (const dim of DIMS) {
    const rows = rollup(dim).filter((r) => r.n > 0);
    md.push(``);
    md.push(`### ${dim}`);
    if (!rows.length) { md.push(`_n/a — no parsed variants carry this dimension yet._`); continue; }
    md.push(`| ${dim} | posts | reach | signal | CVR% |`);
    md.push(`|------|------:|------:|------:|-----:|`);
    for (const r of rows) md.push(`| ${r.val} | ${r.n} | ${r.reach} | ${r.signal} | ${r.cvr ?? "n/a"} |`);
  }
  md.push(``);

  // Per-variant detail (top by signal then reach).
  md.push(`## Per-variant detail`);
  const parsed = records.filter((r) => r.parsed).sort((a, b) => (b.signal - a.signal) || (b.visitors - a.visitors));
  if (!parsed.length) {
    md.push(`_No parsed variants with data yet._`);
  } else {
    md.push(`| variant (utm_content) | reach | waitlist | assessment | github | engagement |`);
    md.push(`|------|------:|------:|------:|------:|:--:|`);
    for (const r of parsed.slice(0, 40)) {
      const c = (g) => (r.conv[g] === null ? "n/a" : r.conv[g]);
      md.push(`| \`${r.code}\` | ${r.visitors} | ${c("waitlist_submitted")} | ${c("assessment_request")} | ${c("github_clicked")} | n/a (metricool) |`);
    }
  }
  md.push(``);
  md.push(`## How to run`);
  md.push(`- \`set -a; . ~/.config/trovex-growth/plausible.env; set +a\` then \`node social-variant-readout.mjs --since <date>\`. Default site = configured; pass \`--site trovex.dev\` for the tool funnel.`);
  md.push(`- Report prints to stdout → trovex_write (no disk .md by default; \`--save\` to keep one).`);
  md.push(`- Native engagement: until METRICOOL_API_KEY is in env, pull getAnalyticsDataByMetrics + getBestTimeToPostByNetwork via the metricool MCP and graft the engagement column.`);

  const out = md.join("\n");
  console.log(out);
  process.stderr.write(`reach ${totalReach}, parsed variants ${records.filter((r) => r.parsed).length}, unparsed ${unparsed.length}\n`);
  if (process.argv.includes("--save")) {
    const outDir = join(__dir, "reports");
    mkdirSync(outDir, { recursive: true });
    const outPath = join(outDir, `social-variant-${date}.md`);
    writeFileSync(outPath, out + "\n");
    process.stderr.write(`also saved ${outPath} (--save)\n`);
  }
}

main();
