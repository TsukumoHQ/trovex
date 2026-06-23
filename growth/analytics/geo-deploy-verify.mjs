#!/usr/bin/env node
/**
 * GEO deploy-verify — post-merge check that shipped GEO pages are LIVE + carry their schema.
 *
 * Replaces a recurring MANUAL task (geo-lead used to curl each new/changed URL by hand after
 * every PR merge, then grep the served HTML for the expected JSON-LD @types). That's mechanical
 * and repeatable → it belongs on dokan (20/80 dogfood rule), not in agent tokens.
 *
 * What it does, per URL: GET it, assert HTTP 200, parse every <script type="application/ld+json">
 * block (must be valid JSON), and confirm the expected schema.org @types are present in the
 * SERVED HTML (not JS-injected — these pages are static). A page that 404s, or ships without its
 * QAPage/FAQPage/DefinedTerm/BreadcrumbList, is a silent GEO regression: the engine can't cite
 * what it can't crawl or parse.
 *
 * INPUT (env DOKAN_INPUT, double-encoded — JSON.parse twice; memory dokan-input-double-encoded):
 *   { "checks": [ { "url": "https://trovex.dev/answers/foo/", "types": ["QAPage","BreadcrumbList"] }, ... ] }
 *   `types` optional — omit to only assert 200 + valid JSON-LD.
 * Local dogfood (no DOKAN_INPUT): pass URLs as argv → asserts 200 + valid JSON-LD only.
 *   node geo-deploy-verify.mjs https://trovex.dev/answers/agent-memory-vs-rag/
 *
 * OUTPUT: prints `::dokan:result:: {json}` on stdout (dokan captures last line → POSTs to relay,
 * event-driven). Human-readable summary on stderr. Exit 0 = all pass; exit 1 = a VERDICT (≥1
 * regression) — per the dokan contract exit≠0 is a verdict, not a crash (runs once, no retry).
 */

const LD_RE = /<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
const TYPE_RE = /"@type"\s*:\s*"([^"]+)"/g;

function parseInput() {
  const raw = process.env.DOKAN_INPUT;
  if (raw) {
    // dokan double-encodes: DOKAN_INPUT is a JSON string whose content is itself JSON.
    let v = raw;
    try { v = JSON.parse(v); } catch { /* not encoded once */ }
    if (typeof v === "string") { try { v = JSON.parse(v); } catch { /* leave */ } }
    if (v && Array.isArray(v.checks)) return v.checks;
  }
  // Local fallback: argv URLs, 200 + valid-JSON-LD only.
  return process.argv.slice(2).map((url) => ({ url }));
}

async function checkOne({ url, types }) {
  const out = { url, status: 0, ok: false, ldBlocks: 0, typesFound: [], missing: [], error: null };
  try {
    const res = await fetch(url, { redirect: "manual", headers: { "user-agent": "geo-deploy-verify/1.0" } });
    out.status = res.status;
    const body = await res.text();
    const found = new Set();
    let m;
    while ((m = LD_RE.exec(body)) !== null) {
      out.ldBlocks++;
      try {
        JSON.parse(m[1]);
      } catch (e) {
        out.error = `invalid JSON-LD block: ${e.message}`;
      }
      let t;
      while ((t = TYPE_RE.exec(m[1])) !== null) found.add(t[1]);
    }
    out.typesFound = [...found];
    if (Array.isArray(types)) out.missing = types.filter((t) => !found.has(t));
    out.ok = out.status === 200 && !out.error && out.missing.length === 0;
  } catch (e) {
    out.error = String(e && e.message ? e.message : e);
  }
  return out;
}

const checks = parseInput();
if (!checks.length) {
  console.error("geo-deploy-verify: no URLs (DOKAN_INPUT.checks or argv). Nothing to do.");
  process.exit(0);
}

const results = [];
for (const c of checks) results.push(await checkOne(c));

const failed = results.filter((r) => !r.ok);
for (const r of results) {
  const tag = r.ok ? "OK " : "FAIL";
  const detail = r.ok
    ? `${r.ldBlocks} ld+json [${r.typesFound.join(", ")}]`
    : `status=${r.status}${r.error ? ` err=${r.error}` : ""}${r.missing.length ? ` missing-types=[${r.missing.join(", ")}]` : ""}`;
  console.error(`  ${tag} ${r.url}  ${detail}`);
}

const result = {
  ok: failed.length === 0,
  checked: results.length,
  failed: failed.length,
  regressions: failed.map((r) => ({ url: r.url, status: r.status, missing: r.missing, error: r.error })),
};
console.log(`::dokan:result:: ${JSON.stringify(result)}`);
process.exit(failed.length === 0 ? 0 : 1);
