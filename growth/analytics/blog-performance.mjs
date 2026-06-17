#!/usr/bin/env node
/**
 * Per-blog-post performance read — turns "we published N posts" into "these few drive the
 * funnel." Pulls what's live (Plausible per-post sessions) and leaves GSC rank + AI-citation
 * as documented-pending columns (need their own access). No fabricated data: a post with no
 * traffic reads 0, not a guess.
 *
 * Sources:
 *   - Plausible Stats API (LIVE): pageviews + visitors per /blog/<slug>. Reads
 *     PLAUSIBLE_STATS_API_KEY + PLAUSIBLE_SITE_ID from env (out-of-git).
 *   - GSC (PENDING): impressions / avg position per post — needs a Search Console API
 *     credential + a verified property. Spec in blog-performance.md; column left blank.
 *   - AI citation (PARTIAL): a /blog/ URL appearing in geo-citation-monitor output. Per-post
 *     citation needs the post→target-query map (geo-lead owns); column noted.
 *
 * Usage:  set -a; . ~/.config/trovex-growth/plausible.env; set +a
 *         node growth/analytics/blog-performance.mjs            # writes reports/blog-performance-<date>.md
 *         node growth/analytics/blog-performance.mjs --dry      # print only
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));
const SITE = "tsukumo.ch";
const SITEMAP = "https://tsukumo.ch/sitemap.xml";

function ymd(d) { return d.toISOString().slice(0, 10); }

async function blogSlugs() {
  const xml = await (await fetch(SITEMAP)).text();
  const urls = [...xml.matchAll(/https:\/\/tsukumo\.ch\/blog\/([a-z0-9-]+)/g)].map((m) => m[1]);
  // unique, drop the category index (not a post)
  return [...new Set(urls)].filter((s) => s !== "category").sort();
}

async function plausiblePages(key) {
  const end = new Date();
  const start = new Date(end.getTime() - 30 * 86400_000);
  const url = `https://plausible.io/api/v1/stats/breakdown?site_id=${SITE}` +
    `&period=custom&date=${ymd(start)},${ymd(end)}&property=event:page&metrics=visitors,pageviews&limit=500`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${key}` } });
  if (!res.ok) throw new Error(`plausible ${res.status}`);
  const data = await res.json();
  const map = new Map();
  for (const r of data.results || []) {
    if (r.page && r.page.startsWith("/blog/")) map.set(r.page, { pageviews: r.pageviews, visitors: r.visitors });
  }
  return { map, start: ymd(start), end: ymd(end) };
}

async function main() {
  const key = process.env.PLAUSIBLE_STATS_API_KEY;
  if (!key) {
    console.error("No PLAUSIBLE_STATS_API_KEY. Load: set -a; . ~/.config/trovex-growth/plausible.env; set +a");
    process.exit(2);
  }
  const slugs = await blogSlugs();
  const { map, start, end } = await plausiblePages(key);

  const rows = slugs.map((slug) => {
    const p = map.get(`/blog/${slug}`) || { pageviews: 0, visitors: 0 };
    return { slug, pageviews: p.pageviews, visitors: p.visitors };
  }).sort((a, b) => b.pageviews - a.pageviews || a.slug.localeCompare(b.slug));

  const totalPv = rows.reduce((s, r) => s + r.pageviews, 0);
  const withTraffic = rows.filter((r) => r.pageviews > 0).length;
  const date = ymd(new Date());

  const md = [
    `# Per-Blog-Post Performance — ${date}`,
    ``,
    `*Owner: analytics-lead · Plausible window ${start}→${end} (LIVE) · GSC + AI-citation columns pending access (see blog-performance.md). No fabricated data — a post with no traffic reads 0.*`,
    ``,
    `**${slugs.length} posts · ${withTraffic} with any pageviews · ${totalPv} total blog pageviews (window).** Pre-launch: counts are tiny and mostly crawler/verification traffic, not organic readers — this is the baseline, re-read after a distribution push.`,
    ``,
    `| # | Post | Pageviews | Visitors | AI-cited? | GSC pos | Sessions→lead |`,
    `|--:|------|----------:|---------:|:---------:|--------:|---------------|`,
    ...rows.map((r, i) =>
      `| ${i + 1} | \`${r.slug}\` | ${r.pageviews} | ${r.visitors} | ‹pending› | ‹GSC› | ‹funnel› |`),
    ``,
    `## How to read / fill`,
    `- **Pageviews/Visitors** are live (Plausible). Rank by these once organic traffic arrives; the top few are where content/geo double down, the zero-traffic tail is rework-or-cut.`,
    `- **AI-cited?** — run \`geo-citation-monitor.mjs\` with the post→target-query map (geo-lead owns the wording); mark a post cited when its URL appears in an engine's citations.`,
    `- **GSC pos** — Google Search Console per-page avg position + impressions. Needs a Search`,
    `  Console API credential (OAuth service account) + a verified \`tsukumo.ch\` property —`,
    `  flagged to cmo. Once keyed, add a GSC pull here (Search Analytics API, dimension=page).`,
    `- **Sessions→lead** — per-landing-path conversion (entry_page=/blog/X → assessment_request).`,
    `  Needs a Plausible funnel (entry_page → goal); v2 once there's traffic to power it.`,
  ].join("\n");

  if (process.argv.includes("--dry")) { console.log(md); return; }
  const outDir = join(__dir, "reports");
  mkdirSync(outDir, { recursive: true });
  const outPath = join(outDir, `blog-performance-${date}.md`);
  writeFileSync(outPath, md + "\n");
  console.log(`wrote ${outPath} — ${withTraffic}/${slugs.length} posts with traffic, ${totalPv} pageviews`);
}

main();
