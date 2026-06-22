#!/usr/bin/env node
// Conversion-surface health monitor — dokan-ready (node runtime, fetch, no deps).
// Checks the live money surfaces; exits non-zero if any is down or missing its
// on-brand marker, so a dokan cron's run-history flags a regression with zero
// tokens / no agent session. (Local-run twin of growth/cro/verify-surfaces.sh.)
const SURFACES = [
  { label: "trovex landing", url: "https://trovex.dev/" },
  { label: "for/claude-code", url: "https://trovex.dev/for/claude-code/", want: "qs-aha" },
  { label: "for/quickstart.js", url: "https://trovex.dev/for/quickstart.js", want: "command_copied" },
  { label: "tsukumo consulting", url: "https://tsukumo.ch/consulting" },
  { label: "tsukumo assessment", url: "https://tsukumo.ch/assessment" },
  { label: "wraith (violet)", url: "https://tsukumo.ch/wraith", want: "wraith-scope" },
];

const ua = { headers: { "user-agent": "trovex-cro-verify/1.0" } };
let fail = 0;
const lines = [];
for (const s of SURFACES) {
  try {
    const r = await fetch(s.url, { ...ua, redirect: "follow" });
    if (!r.ok) { lines.push(`FAIL ${s.label} HTTP ${r.status}`); fail++; continue; }
    if (s.want) {
      const body = await r.text();
      if (!body.includes(s.want)) { lines.push(`FAIL ${s.label} missing:${s.want}`); fail++; continue; }
    }
    lines.push(`ok   ${s.label}`);
  } catch (e) {
    lines.push(`FAIL ${s.label} ${e.message}`); fail++;
  }
}
console.log(lines.join("\n"));
console.log(`-- ${SURFACES.length - fail} ok, ${fail} fail --`);
process.exit(fail === 0 ? 0 : 1);
