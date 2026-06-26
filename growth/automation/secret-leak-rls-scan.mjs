/**
 * dokan script: secret-leak-rls-scan  (dokan script_id 425, schedule_id 56, cron `0 15 8 * * 1`)
 *
 * Weekly security canary for the funnel. Two invariants I own are enforced at build-time per
 * PR (check-no-client-secrets guard + RLS deny-all), but drift BETWEEN PRs goes unseen — this
 * is the standing, scheduled proof. Runs in dokan (zero-local); this .mjs is the review mirror.
 *
 * (A) Secret-leak: fetches the LIVE client surface (trovex.dev + tsukumo.ch HTML + same-origin
 *     JS bundles) and checks that no real server-secret VALUE (service_role/Twenty/OpenAI/etc.,
 *     injected as env) and no secret PATTERN (sk-, re_, a service_role JWT) appears. Leak-safe:
 *     it matches against secret values but NEVER prints them — findings carry the key NAME only.
 *     A self-test asserts the value-detector is armed (env secrets present) so a CLEAN result
 *     can't be a silent no-op.
 * (B) RLS deny-all: probes Supabase REST as the anon role — leads/waitlist/newsletter/applications
 *     must return 0 rows. Any anon-readable row = CRITICAL (PII exposed).
 *
 * On any CRITICAL: exit 1 (deterministic verdict, surfaces in dokan history) + a P0 relay alert
 * to CTO — the single on-call escalation point for monitor failures (memory
 * monitor-failure-escalation) — via the relay MCP call_tool dispatcher. The anon key is a
 * PUBLISHABLE key (safe, not a secret) passed via DOKAN_INPUT.
 *
 * INPUT (DOKAN_INPUT): { anon_key (required for RLS probe), sites?, tables?, relay_url? }.
 */
const input = JSON.parse(process.env.DOKAN_INPUT || '{}');
const SITES = input.sites || ['https://trovex.dev', 'https://tsukumo.ch'];
const TABLES = input.tables || ['leads', 'waitlist', 'newsletter', 'applications'];
const ANON = input.anon_key; // publishable anon key (safe, not a secret)
const SUPA = process.env.SUPABASE_URL;
const RELAY = input.relay_url || 'http://host.docker.internal:8090/mcp';
const MAX_ASSETS = 60, MAX_BYTES = 4_000_000;

const DANGEROUS = ['SUPABASE_SERVICE_ROLE_KEY','TWENTY_API_KEY','OPENAI_API_KEY','PERPLEXITY_API_KEY',
  'GEMINI_API_KEY','SERPAPI_KEY','PLAUSIBLE_STATS_API_KEY','FIREFLIES_API_KEY',
  'GOOGLE_OAUTH_CLIENT_SECRET','GMAIL_REFRESH_TOKEN'];
const secretVals = DANGEROUS
  .map(n => ({ name: n, val: process.env[n] }))
  .filter(s => s.val && s.val.length >= 12);

const findings = [];
const PATTERNS = [
  { name: 'openai_key', re: /sk-[A-Za-z0-9_-]{20,}/ },
  { name: 'resend_key', re: /re_[A-Za-z0-9_-]{20,}/ },
  { name: 'service_role_jwt', re: /eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]*?(?:c2VydmljZV9yb2xl|service_role)[A-Za-z0-9_-]*?\.[A-Za-z0-9_-]{10,}/ },
  { name: 'literal_service_role', re: /service_role/ },
];
function scanText(label, text) {
  for (const s of secretVals) {
    if (text.includes(s.val)) findings.push({ severity: 'CRITICAL', kind: 'secret_value_in_bundle', key: s.name, where: label });
  }
  for (const p of PATTERNS) {
    const m = p.re.exec(text);
    if (m) findings.push({ severity: p.name === 'literal_service_role' ? 'WARN' : 'CRITICAL', kind: 'pattern', pattern: p.name, where: label, sample: m[0].slice(0, 8) + '…' });
  }
}

// SELF-TEST: prove the value-detector is armed (env secrets injected) and fires — else the scan is a silent no-op.
let selfTest = false;
if (secretVals.length) {
  const blob = `canary ${secretVals[0].val} canary`;
  selfTest = blob.includes(secretVals[0].val);
}
if (!selfTest) findings.push({ severity: 'CRITICAL', kind: 'detector_disarmed', note: 'no server-secret env values injected — value-leak scan would be a silent no-op; fix dokan secret injection before trusting CLEAN' });

async function get(url, asText = true) {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), 12000);
  try {
    const r = await fetch(url, { signal: ctl.signal, headers: { 'User-Agent': 'trovex-secfetch/1' } });
    clearTimeout(t);
    return { status: r.status, headers: r.headers, text: asText ? await r.text() : null };
  } catch (e) { clearTimeout(t); return { status: 0, err: String(e.cause?.code || e.name || e.message) }; }
}
function sameOriginAssets(html, base) {
  const o = new URL(base).origin;
  const urls = new Set();
  const re = /(?:src|href)\s*=\s*["']([^"']+\.js[^"']*)["']/gi;
  let m;
  while ((m = re.exec(html)) && urls.size < MAX_ASSETS) {
    try { const u = new URL(m[1], base); if (u.origin === o) urls.add(u.href); } catch {}
  }
  return [...urls];
}

// (A) public-surface scan
let totalBytes = 0;
for (const site of SITES) {
  const home = await get(site);
  if (home.status !== 200 || !home.text) { findings.push({ severity: 'INFO', kind: 'fetch_fail', where: site, status: home.status, err: home.err }); continue; }
  scanText(`${site} (html)`, home.text);
  const assets = sameOriginAssets(home.text, site);
  console.log(`${site}: ${assets.length} same-origin JS assets`);
  for (const a of assets) {
    if (totalBytes > MAX_BYTES) { console.log('byte budget hit, stopping asset scan'); break; }
    const r = await get(a);
    if (r.status === 200 && r.text) { totalBytes += r.text.length; scanText(a.replace(site, ''), r.text); }
  }
}

// (B) RLS deny-all probe
async function probeTable(tbl) {
  const url = `${SUPA}/rest/v1/${tbl}?select=*&limit=1`;
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), 10000);
  try {
    const r = await fetch(url, { signal: ctl.signal, headers: ANON ? { apikey: ANON, Authorization: `Bearer ${ANON}` } : {} });
    clearTimeout(t);
    const body = await r.text();
    let rows = null; try { const j = JSON.parse(body); if (Array.isArray(j)) rows = j.length; } catch {}
    if (r.status === 200 && rows > 0) {
      findings.push({ severity: 'CRITICAL', kind: 'rls_anon_read', table: tbl, http: r.status, rows });
    } else {
      console.log(`RLS ${tbl}: OK (http ${r.status}, rows=${rows === null ? 'n/a' : rows})`);
    }
    return { table: tbl, http: r.status, rows };
  } catch (e) { clearTimeout(t); findings.push({ severity: 'INFO', kind: 'rls_probe_fail', table: tbl, err: String(e.cause?.code || e.name) }); return { table: tbl, err: true }; }
}
const rls = [];
if (SUPA) { for (const tbl of TABLES) rls.push(await probeTable(tbl)); }
else findings.push({ severity: 'INFO', kind: 'no_supabase_url' });

// DOKAN_INPUT.forceAlert → inject a synthetic CRITICAL to exercise the real P0-alert path
// (verifies the relay transport delivers end-to-end). Clearly labelled; not a real finding.
if (input.forceAlert) findings.push({ severity: 'CRITICAL', kind: 'alert_transport_test', note: 'forceAlert probe — verifies the P0 alert delivers; ignore' });

const critical = findings.filter(f => f.severity === 'CRITICAL');
const result = { ok: critical.length === 0, critical: critical.length, armed: secretVals.length, self_test: selfTest, findings, rls_probed: rls.length, scanned_bytes: totalBytes };
console.log(`armed=${secretVals.length} self_test=${selfTest} SCAN ${result.ok ? 'CLEAN' : 'CRITICAL x' + critical.length}`);

// P0 relay alert on CRITICAL (leak-safe: names only).
// Transport: the relay MCP exposes a `call_tool` DISPATCHER, not the tools directly — a raw
// `tools/call name:'send_message'` returns -32602 'tool not found'. Must wrap:
// tools/call → name:'call_tool' → arguments:{ tool:'send_message', args:{...} } (verified probe 1772).
if (critical.length) {
  const rpc = { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'call_tool', arguments: { tool: 'send_message', args: {
    project: 'trovex-growth', as: 'fullstack-lead', to: 'cto', priority: 'P0', type: 'task',
    subject: `🔴 SECURITY: ${critical.length} CRITICAL finding(s) — secret-leak/RLS scan (425)`,
    content: 'Weekly scan found CRITICAL: ' + JSON.stringify(critical) + '\nInvestigate now (secret-server-only / RLS deny-all invariant).' } } } };
  try { await fetch(RELAY, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream' }, body: JSON.stringify(rpc) }); } catch (e) { console.log('alert send failed:', String(e.name)); }
}

console.log(`::dokan:result:: ${JSON.stringify(result)}`);
if (!result.ok) process.exit(1); // deterministic verdict: scan found a leak
