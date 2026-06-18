#!/usr/bin/env node
/**
 * Suite GitHub reach — the top-of-funnel "reach" signal for the OSS suite repos that have
 * NO web landing (WRAI.TH and yoru are CLIs; their surface is the GitHub repo, not a page).
 * A browser analytics module can't mount where there's no page, so suite reach for CLI tools
 * = GitHub stars / forks / views / clones. (trovex DOES have a landing — its reach is also in
 * Plausible via oss_surface_view; included here for the cross-property stars/clones picture.)
 *
 * Auth: uses the `gh` CLI (must be logged in with PUSH access to the repos — the traffic API
 * requires it). No key in this script; gh handles auth. No PII (repo-level counts only).
 *
 * Run:  node growth/analytics/github-suite-reach.mjs   # writes reports/suite-github-reach-<date>.md
 *       node growth/analytics/github-suite-reach.mjs --dry
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));
const ymd = (d) => d.toISOString().slice(0, 10);
const REPOS = ["Synergix-lab/WRAI.TH", "Synergix-lab/trovex", "Synergix-lab/yoru"];

function gh(path) {
  try {
    return JSON.parse(execSync(`gh api ${path} 2>/dev/null`, { encoding: "utf8" }));
  } catch {
    return null; // repo missing / no access — report n/a, never fabricate
  }
}

function repoRow(r) {
  const base = gh(`repos/${r}`);
  if (!base) return { repo: r, missing: true };
  const views = gh(`repos/${r}/traffic/views`);
  const clones = gh(`repos/${r}/traffic/clones`);
  const n = (v) => (v == null ? "n/a" : v);
  return {
    repo: r,
    stars: base.stargazers_count,
    forks: base.forks_count,
    views14: views ? `${views.count}/${views.uniques}` : "n/a",
    clones14: clones ? `${clones.count}/${clones.uniques}` : "n/a",
  };
}

const rows = REPOS.map(repoRow);
const date = ymd(new Date());
const md = [
  `# Suite GitHub Reach — ${date}`,
  ``,
  `*Top-of-funnel reach for the OSS suite repos (the surface for CLI tools with no landing). GitHub stars/forks + 14-day traffic (views, unique clones). \`gh\` CLI auth (push). No PII — repo-level counts only. n/a = repo absent or no access.*`,
  ``,
  `| Repo | Stars | Forks | Views 14d (total/uniq) | Clones 14d (total/uniq) |`,
  `|------|------:|------:|------------------------|-------------------------|`,
  ...rows.map((r) =>
    r.missing
      ? `| ${r.repo} | n/a | n/a | n/a | n/a (repo absent / no access) |`
      : `| ${r.repo} | ${r.stars} | ${r.forks} | ${r.views14} | ${r.clones14} |`),
  ``,
  `## Why this exists`,
  `WRAI.TH (and yoru, if a CLI) have **no web property**, so the browser analytics module`,
  `(\`oss_surface_view\` etc.) can't be ported there — there's no page to fire it. Their`,
  `top-of-funnel reach lives in **GitHub traffic**. The suite→agency hook for these repos is a`,
  `**UTM'd tsukumo link in the README** (\`utm_source=wraith&utm_medium=oss-suite&utm_campaign=consulting\`),`,
  `which tsukumo captures as \`tsukumo_visit{source=suite}\` — no repo-side analytics needed.`,
  ``,
  `## Honesty`,
  `- 14-day window is GitHub's max for the traffic API; pull weekly to build history (GitHub`,
  `  only retains 14d, so this report IS the archive).`,
  `- Stars/clones are reach (vanity-adjacent) — they matter only insofar as they precede`,
  `  suite→agency clicks and consulting leads. The north star stays \`assessment_request\` (suite).`,
  `- CLI install/adopt telemetry would be the truer \`oss_adopt\` signal but is **opt-in only**`,
  `  (the CLI runs on the user's machine) — a separate, consent-gated decision, not built here.`,
].join("\n");

if (process.argv.includes("--dry")) { console.log(md); }
else {
  const outDir = join(__dir, "reports");
  mkdirSync(outDir, { recursive: true });
  const outPath = join(outDir, `suite-github-reach-${date}.md`);
  writeFileSync(outPath, md + "\n");
  console.log(`wrote ${outPath}`);
}
