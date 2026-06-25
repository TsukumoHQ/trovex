/**
 * dokan script: indexnow-submit  (dokan script_id 432, schedule_id 63, cron `0 0 9 * * *` daily)
 *
 * Owner/CTO: all recurring automation runs ON DOKAN (not a Vercel hook/CI step). This pings
 * IndexNow (Bing/Yandex) with site URLs that CHANGED within the window, so fresh/updated pages
 * get re-crawled fast. Runs in dokan (zero-local); this .mjs is the review mirror.
 *
 * SCOPE: trovex.dev live (sched 63). tsukumo.ch to be added as a 2nd schedule (same script,
 * different input host/key) — it's the conversion surface per the Tsukumo=center re-align.
 *
 * KEY (NOT a secret): an IndexNow key is PUBLIC by design — the keyfile served at
 * https://<host>/<key>.txt IS the ownership proof. So the key is passed inline via DOKAN_INPUT
 * (or env INDEXNOW_KEY), no set_secret needed. trovex.dev key + keyfile are already live.
 *
 * NEW-detect: sitemap <lastmod> within `sinceHours` (daily = 24). 0 = submit all. dryRun builds
 * the payload without submitting. IndexNow dedupes server-side. exit-0 monitor.
 * INPUT (DOKAN_INPUT): { host, sitemap?, key, keyLocation?, sinceHours?, max?, dryRun? }.
 */
const input = JSON.parse(process.env.DOKAN_INPUT || '{}');
const HOST = input.host || 'trovex.dev';
const SITEMAP = input.sitemap || `https://${HOST}/sitemap.xml`;
const KEY = input.key || process.env.INDEXNOW_KEY || null;
const KEY_LOCATION = input.keyLocation || (KEY ? `https://${HOST}/${KEY}.txt` : null);
const SINCE_HOURS = Number(input.sinceHours) > 0 ? Number(input.sinceHours) : 0; // 0 = all urls in sitemap
const DRY = input.dryRun === true || !KEY; // no key → can't submit → dry
const MAX = Number(input.max) > 0 ? Number(input.max) : 10000;
const RELAY = input.relay_url || 'http://host.docker.internal:8090/mcp'; // for failure→CTO alerts
const cutoff = SINCE_HOURS > 0 ? Date.now() - SINCE_HOURS * 3600_000 : 0;

async function get(url) {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), 12000);
  try { const r = await fetch(url, { signal: ctl.signal, headers: { 'User-Agent': 'trovex-indexnow/1' } }); clearTimeout(t); return { status: r.status, text: r.ok ? await r.text() : null }; }
  catch (e) { clearTimeout(t); return { status: 0, err: String(e.cause?.code || e.name) }; }
}

// Parse <url><loc>..</loc><lastmod>..</lastmod></url> from a sitemap.
function parseSitemap(xml) {
  const out = [];
  const re = /<url>([\s\S]*?)<\/url>/gi; let m;
  while ((m = re.exec(xml))) {
    const block = m[1];
    const loc = (block.match(/<loc>\s*([^<]+?)\s*<\/loc>/i) || [])[1];
    const lm = (block.match(/<lastmod>\s*([^<]+?)\s*<\/lastmod>/i) || [])[1];
    if (loc) out.push({ loc: loc.trim(), lastmod: lm ? Date.parse(lm) : null });
  }
  return out;
}

// Failure escalation → CTO at P0 (memory monitor-failure-escalation). call_tool dispatcher.
// Success is SILENT (routine green = no notify, per the rule).
async function alertCto(line) {
  const rpc = { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'call_tool', arguments: { tool: 'send_message', args: {
    project: 'trovex-growth', as: 'fullstack-lead', to: 'cto', priority: 'P0', type: 'task', subject: line, content: line } } } };
  try { await fetch(RELAY, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream' }, body: JSON.stringify(rpc) }); } catch {}
}

const sm = await get(SITEMAP);
if (!sm.text) {
  await alertCto(`🔴 indexnow-submit (432) ${HOST}: sitemap fetch FAILED (${sm.status || sm.err}) ${SITEMAP}`);
  console.log(`::dokan:result:: ${JSON.stringify({ ok: false, error: `sitemap_fetch_${sm.status || sm.err}`, sitemap: SITEMAP })}`); process.exit(0);
}
const all = parseSitemap(sm.text);
const selected = (cutoff ? all.filter(u => u.lastmod && u.lastmod >= cutoff) : all).map(u => u.loc).slice(0, MAX);

let submit = { attempted: false };
if (selected.length && !DRY) {
  const body = { host: HOST, key: KEY, keyLocation: KEY_LOCATION, urlList: selected };
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), 15000);
  try {
    const r = await fetch('https://api.indexnow.org/indexnow', { method: 'POST', signal: ctl.signal, headers: { 'Content-Type': 'application/json; charset=utf-8' }, body: JSON.stringify(body) });
    clearTimeout(t);
    submit = { attempted: true, http_status: r.status, ok: r.status === 200 || r.status === 202 };
  } catch (e) { clearTimeout(t); submit = { attempted: true, ok: false, error: String(e.cause?.code || e.name) }; }
  // FAILURE (IndexNow rejected / unreachable) → CTO P0. Success = silent.
  if (!submit.ok) await alertCto(`🔴 indexnow-submit (432) ${HOST}: submit FAILED (${submit.http_status || submit.error}, ${selected.length} urls)`);
}

const result = { ok: true, host: HOST, sitemap_urls: all.length, selected: selected.length, window_hours: SINCE_HOURS || 'all', dryRun: DRY, key_present: !!KEY, submit, sample: selected.slice(0, 5) };
console.log(`indexnow: ${all.length} in sitemap, ${selected.length} selected, dry=${DRY}, submit=${JSON.stringify(submit)}`);
console.log(`::dokan:result:: ${JSON.stringify(result)}`);
