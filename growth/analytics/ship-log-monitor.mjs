#!/usr/bin/env node
/**
 * SHIP-LOG MONITOR — feed the build-in-public (BIP) pillar from our OWN shipping.
 *
 * Pulls the real ships from the three public OSS repos (trovex + WRAI.TH + yoru): merged PRs
 * and published releases in a rolling window, filters to what's actually shippable (real
 * features / fixes / perf — drops chore/ci/docs/deps noise), and prints a ship-log feed.
 * social-lead + content-lead turn it into BIP content ("what we shipped this week", changelog
 * carousels, the dogfood meta). INHERENTLY HONEST: it's our own real merged PRs — no manual
 * tracking, no fabricated numbers. An empty window reads "no ships", not a guess.
 *
 * Auth: the `gh` CLI (must be logged in). No key in this script; gh handles auth. The 3 repos
 * are PUBLIC, so their PR titles are already public — but per the confidentiality rule we still
 * scrub/skip any title matching a client/internal name (CLIENT_SCRUB below; extend as needed).
 * No PII: repo-level merged-PR metadata only (title, number, author login, merge date).
 *
 * Output: STDOUT = the ship-log markdown (owner rule "rien en md, tout dans trovex" → pipe into
 * the trovex store; social/content read it there). STDERR = progress + a one-line summary.
 * Disk is OFF by default; `--save` writes reports/ship-log-<date>.md as an escape hatch.
 *
 * Usage:
 *   node growth/analytics/ship-log-monitor.mjs              # rolling last 7 days
 *   node growth/analytics/ship-log-monitor.mjs --days 1     # last 24h (daily cadence)
 *   node growth/analytics/ship-log-monitor.mjs --since 2026-06-15
 *   node growth/analytics/ship-log-monitor.mjs --save       # also write a disk report
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));
const ymd = (d) => d.toISOString().slice(0, 10);
const REPOS = ["TsukumoHQ/trovex", "TsukumoHQ/WRAI.TH", "TsukumoHQ/yoru"];

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : undefined;
}
const SAVE = process.argv.includes("--save");

// Window: --since wins, else --days back (default 7). A daily launchd run with the default
// 7-day window = a rolling weekly ship-log, refreshed each day.
function windowStart() {
  const since = arg("--since");
  if (since) return since;
  const days = Number(arg("--days") || 7);
  return ymd(new Date(Date.now() - days * 86400_000));
}

function gh(path) {
  try {
    return JSON.parse(execSync(`gh api ${path} 2>/dev/null`, { encoding: "utf8", maxBuffer: 8 * 1024 * 1024 }));
  } catch {
    return null; // repo missing / no access / rate-limited → report n/a, never fabricate
  }
}

// Confidentiality: skip any PR/release title that names a client/internal project. The 3 repos
// are public OSS so titles are already public, but this is the belt-and-suspenders scrub per the
// confidentiality-no-client-names rule. The client names themselves MUST NOT be committed (this
// script lives in the PUBLIC trovex repo — hardcoding them would itself leak the relationships).
// So the scrub list is loaded from an out-of-git env var, comma-separated, default empty:
//   CLIENT_SCRUB="acme,foo-corp"   (set via ~/.config/trovex-growth/ship-log.env, never in git)
const CLIENT_SCRUB = (process.env.CLIENT_SCRUB || "")
  .split(",")
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean);
const isConfidential = (title) => {
  const t = (title || "").toLowerCase();
  return CLIENT_SCRUB.some((name) => t.includes(name));
};

// Noise we never call a "ship": tooling, deps, docs-only, merge/revert churn. Conventional-commit
// prefix OR keyword. A title with NO recognized prefix is kept (could be a real ship) unless it
// trips a noise keyword.
const NOISE_PREFIX = /^(chore|ci|test|build|style|docs|refactor|deps|dependabot|revert)(\(|:|\s|\/)/i;
const NOISE_KEYWORD = /(bump |dependabot|merge branch|merge pull request|\bwip\b|^\s*revert\b|lint fix|typo)/i;
// Positive signal — a real ship for BIP purposes.
const SHIP_PREFIX = /^(feat|fix|perf)(\(|:|!)/i;

function classify(title) {
  if (SHIP_PREFIX.test(title)) {
    const kind = /^feat/i.test(title) ? "feature" : /^perf/i.test(title) ? "perf" : "fix";
    return { ship: true, kind };
  }
  if (NOISE_PREFIX.test(title) || NOISE_KEYWORD.test(title)) return { ship: false };
  // Untyped but substantive-looking title → keep as a generic ship.
  return { ship: true, kind: "other" };
}

function shipsForRepo(repo, start) {
  // Closed PRs, newest first; filter to merged within the window. (List API avoids the search
  // rate limit; 100 most-recent closed PRs comfortably covers a 7-day window at our volume.)
  const prs = gh(`repos/${repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100`);
  if (prs == null) return { repo, missing: true };
  const ships = [];
  let dropped = 0, confidential = 0;
  for (const p of prs) {
    if (!p.merged_at) continue;
    if (p.merged_at.slice(0, 10) < start) continue;
    const title = (p.title || "").trim();
    if (isConfidential(title)) { confidential++; continue; }
    const c = classify(title);
    if (!c.ship) { dropped++; continue; }
    ships.push({ num: p.number, title, kind: c.kind, mergedAt: p.merged_at.slice(0, 10), author: p.user?.login || "?" });
  }
  // Published releases in the window.
  const rels = gh(`repos/${repo}/releases?per_page=20`) || [];
  const releases = rels
    .filter((r) => !r.draft && r.published_at && r.published_at.slice(0, 10) >= start && !isConfidential(r.name || r.tag_name))
    .map((r) => ({ tag: r.tag_name, name: (r.name || "").trim(), date: r.published_at.slice(0, 10) }));
  ships.sort((a, b) => (a.mergedAt < b.mergedAt ? 1 : -1));
  return { repo, ships, releases, dropped, confidential };
}

const start = windowStart();
const today = ymd(new Date());
const repoName = (r) => r.split("/")[1];
const results = REPOS.map((r) => shipsForRepo(r, start));

const md = [];
const P = (s) => md.push(s);
P(`# Trovex Suite — Ship Log (build-in-public feed) — ${today}`);
P(``);
P(`*Window ${start}→${today} · auto-pulled from the public OSS repos (${REPOS.map(repoName).join(" · ")}) by \`ship-log-monitor.mjs\` via the GitHub API. Real merged PRs + releases only — no fabrication; an empty window reads "no ships". Noise (chore/ci/docs/deps/merge churn) filtered out; client/internal names scrubbed. social-lead + content-lead: this is the BIP source — turn it into "what we shipped" posts / changelog carousels.*`);
P(``);

let totalShips = 0, totalReleases = 0, anyMissing = false;
for (const r of results) {
  if (r.missing) { anyMissing = true; P(`## ${repoName(r.repo)}`); P(`_GitHub API unavailable for \`${r.repo}\` (missing/no-access/rate-limited) → **n/a**._`); P(``); continue; }
  totalShips += r.ships.length;
  totalReleases += r.releases.length;
  P(`## ${repoName(r.repo)} — ${r.ships.length} ship${r.ships.length === 1 ? "" : "s"}${r.releases.length ? ` · ${r.releases.length} release${r.releases.length === 1 ? "" : "s"}` : ""}`);
  if (r.releases.length) {
    for (const rel of r.releases) P(`- 🏷️ **Release ${rel.tag}**${rel.name && rel.name !== rel.tag ? ` — ${rel.name}` : ""} (${rel.date})`);
  }
  if (!r.ships.length) {
    P(`_No shippable PR merged in this window (a real zero)._`);
  } else {
    const icon = { feature: "✨", fix: "🔧", perf: "⚡", other: "•" };
    for (const s of r.ships) P(`- ${icon[s.kind] || "•"} ${s.title} (#${s.num}, ${s.mergedAt})`);
  }
  if (r.dropped || r.confidential) P(`<sub>filtered: ${r.dropped} noise${r.confidential ? `, ${r.confidential} confidential-scrubbed` : ""}</sub>`);
  P(``);
}

P(`---`);
P(`**Suite total this window: ${totalShips} ship${totalShips === 1 ? "" : "s"}${totalReleases ? ` + ${totalReleases} release${totalReleases === 1 ? "" : "s"}` : ""}.**${anyMissing ? " _(one or more repos read n/a — total is a floor.)_" : ""} The honest dogfood feed: we ship in public, we measure in public.`);

const out = md.join("\n");
process.stdout.write(out + "\n");
process.stderr.write(`ship-log: ${totalShips} ships, ${totalReleases} releases across ${REPOS.length} repos (window ${start}→${today})\n`);

if (SAVE) {
  const dir = join(__dir, "reports");
  mkdirSync(dir, { recursive: true });
  const f = join(dir, `ship-log-${today}.md`);
  writeFileSync(f, out + "\n");
  process.stderr.write(`ship-log: saved ${f}\n`);
}
