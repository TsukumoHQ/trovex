#!/usr/bin/env node
// Voice + canon guard — dokan-ready (node runtime, fetch, no deps).
// Scans trovex's owned PUBLIC plain-text surfaces (README, llms.txt, llms-full.txt)
// for banned slop words and non-canonical trovex.dev/blog links (the blog lives
// ONLY at tsukumo.ch/blog), so a dokan cron's run-history flags voice/canon drift
// with zero tokens / no agent session.
//
// DOKAN_INPUT (optional JSON):
//   { "surfaces": [{ "name": "README", "url": "..." }], "strict": false }
// Default surfaces = README + the GEO llms files (raw/plain text, clean to scan).
//
// Exit semantics:
//   default (monitor)  -> always exit 0 (the RUN is healthy); findings in report.clean/violations.
//   strict=true (gate) -> exit 1 if any violation (for CI-style use).
//
// dokan: script_id 40, schedule_id 8, cron '0 0 9 * * *' (daily 09:00 UTC).

// Default = owned, plain-text public surfaces (clean to scan, no HTML noise).
// llms.txt / llms-full.txt are the GEO surfaces that drifted to trovex.dev/blog
// once already (#347) — monitor them so it can't recur silently.
const DEFAULT_SURFACES = [
  { name: "README", url: "https://raw.githubusercontent.com/TsukumoHQ/trovex/main/README.md" },
  { name: "llms.txt", url: "https://trovex.dev/llms.txt" },
  { name: "llms-full.txt", url: "https://trovex.dev/llms-full.txt" },
];

// Banned slop words (voice memory). Cleanly + deterministically detectable only.
const BANNED = [
  /\brevolutionary\b/i,
  /\bseamless(?:ly)?\b/i,
  /\bsupercharges?\b/i,
  /\bsupercharged\b/i,
  /\bunlocks?\b/i,
  /\bunlocked\b/i,
  /\bunlocking\b/i,
  /\bAI[-\s]powered\b/i,
  /\bgame[-\s]chang(?:er|ing)\b/i,
  /\bcutting[-\s]edge\b/i,
];

// Canon: the blog lives ONLY at tsukumo.ch/blog. Any trovex.dev/blog link = drift.
const NON_CANONICAL_BLOG = /trovex\.dev\/blog/i;

async function scan(surface) {
  const out = [];
  let text;
  try {
    const res = await fetch(surface.url, { headers: { "user-agent": "content-voice-guard/1.0" } });
    if (!res.ok) return [{ surface: surface.name, type: "FETCH", detail: "HTTP " + res.status }];
    text = await res.text();
  } catch (e) {
    return [{ surface: surface.name, type: "FETCH", detail: String((e && e.message) || e) }];
  }
  text.split("\n").forEach((line, i) => {
    for (const re of BANNED) {
      const m = line.match(re);
      if (m) out.push({ surface: surface.name, type: "BANNED", line: i + 1, hit: m[0], context: line.trim().slice(0, 120) });
    }
    if (NON_CANONICAL_BLOG.test(line)) {
      out.push({ surface: surface.name, type: "NON_CANONICAL_BLOG", line: i + 1, hit: "trovex.dev/blog", context: line.trim().slice(0, 120) });
    }
  });
  return out;
}

// dokan can DOUBLE-encode run input: env DOKAN_INPUT arrives as a JSON string
// whose content is itself the JSON (JSON.stringify run twice). Parse once; if
// the result is still a string, parse again. Handles single- and double-encoded.
let input = {};
try {
  let parsed = JSON.parse(process.env.DOKAN_INPUT || "{}");
  if (typeof parsed === "string") parsed = JSON.parse(parsed);
  if (parsed && typeof parsed === "object") input = parsed;
} catch (e) { /* default */ }
const surfaces = (Array.isArray(input.surfaces) && input.surfaces.length) ? input.surfaces : DEFAULT_SURFACES;
const strict = input.strict === true;

const violations = [];
for (const s of surfaces) violations.push(...await scan(s));

const report = {
  checked: surfaces.map((s) => s.name),
  clean: violations.length === 0,
  count: violations.length,
  violations,
  ts: new Date().toISOString(),
};
console.log(JSON.stringify(report, null, 2));

if (violations.length) {
  console.error("VOICE-GUARD: " + violations.length + " violation(s) found.");
  if (strict) process.exit(1);
} else {
  console.log("VOICE-GUARD: clean.");
}
process.exit(0);
