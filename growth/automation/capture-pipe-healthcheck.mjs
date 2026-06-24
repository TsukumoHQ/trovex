/**
 * dokan script: capture-pipe-healthcheck
 *
 * The funnel's capture endpoints are load-bearing — if one silently 5xx's or starts
 * accepting junk, leads vanish with no error anyone sees. This probes each on a schedule
 * and emits a pass/fail verdict (::dokan:result::) so a regression surfaces in dokan run
 * history instead of by chance. dogfood + 20/80: deterministic, no agent tokens.
 *
 * What "healthy" means per endpoint: a POST of an EMPTY/invalid body must return a typed
 * 4xx (validation working) — NOT a 5xx (broken) and NOT a 2xx (accepting junk). The GET on
 * the Calendly webhook must be 405 (route deployed, POST-only). Anything else = FAIL.
 *
 * RUNTIME: node (dokan). No deps — global fetch.
 * INPUT  : env DOKAN_INPUT (JSON), optional { timeoutMs: 12000 }.
 * OUTPUT : `::dokan:result::<json>` = { ok, checked, fails:[...], probes:[{name,url,method,
 *          code,expect,pass}] }. Exit code non-zero when any probe fails (so the run shows
 *          as failed in dokan, not just a buried field).
 */

const PROBES = [
  { name: "trovex_waitlist", url: "https://trovex.dev/api/waitlist", method: "POST", body: "{}", ok: (c) => c >= 400 && c < 500 },
  { name: "tsukumo_contact", url: "https://tsukumo.ch/api/contact", method: "POST", body: "{}", ok: (c) => c >= 400 && c < 500 },
  { name: "tsukumo_newsletter", url: "https://tsukumo.ch/api/newsletter", method: "POST", body: "{}", ok: (c) => c >= 400 && c < 500 },
  // Calendly webhook: GET must be 405 (deployed, POST-only) — confirms the booking→Twenty route is live.
  { name: "tsukumo_calendly_webhook", url: "https://tsukumo.ch/api/calendly-webhook", method: "GET", body: null, ok: (c) => c === 405 },
  // Prod sites up.
  { name: "trovex_home", url: "https://trovex.dev/", method: "GET", body: null, ok: (c) => c === 200 },
  { name: "tsukumo_home", url: "https://tsukumo.ch/", method: "GET", body: null, ok: (c) => c === 200 },
];

function input() { try { return JSON.parse(process.env.DOKAN_INPUT || "{}"); } catch { return {}; } }

async function probe(p, timeoutMs) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  let code = 0;
  try {
    const res = await fetch(p.url, {
      method: p.method,
      headers: p.body ? { "Content-Type": "application/json" } : undefined,
      body: p.body ?? undefined,
      signal: ctrl.signal,
      redirect: "manual",
    });
    code = res.status;
  } catch {
    code = 0; // network error / timeout
  } finally {
    clearTimeout(t);
  }
  const pass = p.ok(code);
  return { name: p.name, url: p.url, method: p.method, code, expect: p.ok.toString().replace(/\s+/g, " "), pass };
}

async function main() {
  const timeoutMs = Number(input().timeoutMs) > 0 ? Number(input().timeoutMs) : 12000;
  const probes = [];
  for (const p of PROBES) probes.push(await probe(p, timeoutMs));
  const fails = probes.filter((x) => !x.pass).map((x) => `${x.name}=${x.code}`);
  const result = { ok: fails.length === 0, checked: probes.length, fails, probes };
  console.log(`::dokan:result::${JSON.stringify(result)}`);
  if (fails.length) process.exit(1); // surface as a failed run in dokan
}

main().catch((e) => {
  console.log(`::dokan:result::${JSON.stringify({ ok: false, error: String((e && e.message) || e) })}`);
  process.exit(1);
});
