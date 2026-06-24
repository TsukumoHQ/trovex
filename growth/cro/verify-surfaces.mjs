#!/usr/bin/env node
// Conversion-surface health + GUARD monitor — dokan-ready (node runtime, fetch, no deps).
// Checks the live money surfaces AND asserts the conversion-critical markers are still
// present, so a dokan cron's run-history flags a regression with zero tokens / no agent
// session. (Local-run twin of growth/cro/verify-surfaces.sh.)
//
// Two marker kinds, because trovex ships static pages AND client-rendered SPAs:
//   - `want`  : substring(s) that must appear in the page's own HTML (static pages,
//               or a static <head>: meta/JSON-LD/OG).
//   - `chunk` : { re, want[] } — for SPA surfaces the conversion UI is in the JS bundle,
//               not the curl'd HTML. Pull the chunk URL matching `re` from the HTML, fetch
//               it, and assert every `want` substring is in the bundle. This is the
//               cro-conversion-guard: a silent break of the install command / share loop /
//               OG card stops being invisible.
//
// dokan contract: exit code IS the verdict (0=all ok, 1=≥1 surface down/regressed), and the
// `::dokan:result::` line is captured by dokan and POSTed to the relay — so a regression
// alerts EVENT-DRIVEN (no agent polling).
const SURFACES = [
  {
    label: "trovex landing",
    url: "https://trovex.dev/",
    // install command (the one above-fold CTA) + hero proof→/savings link (#425) must render.
    chunk: { re: /\/assets\/main-[A-Za-z0-9_-]+\.js/, want: ["uv tool install git+https://github.com/TsukumoHQ/trovex", "estimate-savings"] },
  },
  { label: "for/claude-code", url: "https://trovex.dev/for/claude-code/", want: ["qs-aha"] },
  { label: "for/quickstart.js", url: "https://trovex.dev/for/quickstart.js", want: ["command_copied"] },
  {
    label: "savings calculator",
    url: "https://trovex.dev/savings",
    // tool-specific OG card (#440) lives in the static <head>; the share loop is in the chunk.
    want: ["api/savings-card"],
    chunk: { re: /\/assets\/savings-[A-Za-z0-9_-]+\.js/, want: ["intent/post", "savings-badge"] },
  },
  // The OG card endpoint is load-bearing for the share loop — every shared /savings
  // link previews via it. If it 500s, shares preview broken silently. Assert it serves
  // a real raster (200 + image/png), not an error page that happens to return 200.
  { label: "savings-card OG endpoint", url: "https://trovex.dev/api/savings-card", contentType: "image/png" },
  { label: "tsukumo consulting", url: "https://tsukumo.ch/consulting" },
  { label: "tsukumo assessment", url: "https://tsukumo.ch/assessment" },
  { label: "wraith (violet)", url: "https://tsukumo.ch/wraith", want: ["wraith-scope"] },
];

const ua = { headers: { "user-agent": "trovex-cro-verify/2.0" } };
const lines = [];
let fail = 0;

async function check(s) {
  const r = await fetch(s.url, { ...ua, redirect: "follow" });
  if (!r.ok) return `FAIL ${s.label} HTTP ${r.status}`;
  if (s.contentType) {
    const ct = r.headers.get("content-type") || "";
    if (!ct.includes(s.contentType)) return `FAIL ${s.label} content-type:${ct || "none"}`;
  }
  const needsBody = s.want || s.chunk;
  const html = needsBody ? await r.text() : "";
  if (s.want) {
    const missing = s.want.filter((w) => !html.includes(w));
    if (missing.length) return `FAIL ${s.label} missing:${missing.join(",")}`;
  }
  if (s.chunk) {
    const m = html.match(s.chunk.re);
    if (!m) return `FAIL ${s.label} no-chunk:${s.chunk.re}`;
    const cr = await fetch(new URL(m[0], s.url).href, ua);
    if (!cr.ok) return `FAIL ${s.label} chunk HTTP ${cr.status}`;
    const js = await cr.text();
    const missing = s.chunk.want.filter((w) => !js.includes(w));
    if (missing.length) return `FAIL ${s.label} chunk-missing:${missing.join(",")}`;
  }
  return `ok   ${s.label}`;
}

for (const s of SURFACES) {
  try {
    const line = await check(s);
    if (line.startsWith("FAIL")) fail++;
    lines.push(line);
  } catch (e) {
    lines.push(`FAIL ${s.label} ${e.message}`);
    fail++;
  }
}

console.log(lines.join("\n"));
console.log(`-- ${SURFACES.length - fail} ok, ${fail} fail --`);
// Event-driven alert channel: dokan captures this + POSTs to the relay. alert=true only when
// a surface is down/regressed, so a healthy run is quiet and a regression pings.
console.log(`::dokan:result:: ${JSON.stringify({
  ok: fail === 0,
  alert: fail > 0,
  checked: SURFACES.length,
  failed: fail,
  down: lines.filter((l) => l.startsWith("FAIL")),
})}`);
process.exit(fail === 0 ? 0 : 1);
