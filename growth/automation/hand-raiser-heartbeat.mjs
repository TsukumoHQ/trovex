/**
 * dokan script: hand-raiser-heartbeat  (dokan, runtime node, schedule ~every 15min, feed_prev_result)
 *
 * Audit gap G3 (tsukumo audit cbbaedeb): the lead-machine poller 395 hard-fails LOUD (→ cto P0), but a
 * SILENT STALL — the schedule stops firing, 395 hangs, or the cron is disabled — has NO alarm; leads just
 * pile up unprocessed. This heartbeat watches 395's run recency via the dokan API and alerts CTO P0 when
 * 395 hasn't produced a run inside the expected window. This .mjs is the review mirror.
 *
 * SCOPE: catches a 395-specific stall while the rest of dokan still runs (the common case). It does NOT
 * catch a total dokan-scheduler death (this script would be dead too) — host/infra health is infra-watch 437.
 *
 * CHECK: GET {dokanBase}/api/runs?limit=200 (Bearer DOKAN_TOKEN) → newest run for script_id=SCRIPT_ID.
 * 395 runs every 10min (sched 58), so age > maxAgeMin (default 25 = ≥2 missed ticks) = STALL. No 395 run in
 * the last 200 runs at all = definitely stalled.
 *
 * ESCALATION (monitor-failure-escalation): STALL → cto P0 (terse one-liner), ONCE (healthy→stalled edge).
 * RECOVERY → cto P3 (stalled→healthy edge). No re-spam while stalled. A fetch-fail to the dokan API is
 * AMBIGUOUS (can't determine) → log + exit 0, no alert (next tick retries) — never false-alarm.
 *
 * TRANSPORT: relay at host.docker.internal:8090 (call_tool dispatcher; Bearer only if RELAY_API_KEY).
 * RUNTIME: node (dokan), no deps. exit 0 always (monitor). DOKAN_TOKEN = dokan secret (env-injected).
 * INPUT (DOKAN_INPUT, all optional): { scriptId, maxAgeMin, dokanBase, relay_url, prev_result }.
 */
const input = (() => { try { return JSON.parse(process.env.DOKAN_INPUT || '{}'); } catch { return {}; } })();
const prevState = (input.prev_result && input.prev_result.state) || null;
const SCRIPT_ID = Number.isInteger(input.scriptId) ? input.scriptId : 395;
const MAX_AGE_MIN = Number(input.maxAgeMin) > 0 ? Number(input.maxAgeMin) : 25;
const DOKAN_BASE = input.dokanBase || 'http://host.docker.internal:8088';
const ALERT_TO = input.alertTo || 'cto'; // override for a controlled delivery test
const RELAY = input.relay_url || 'http://host.docker.internal:8090/mcp';
const NOW = Date.now();

async function http(url, opts = {}, ms = 12000) {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { ...opts, signal: ctl.signal }); } finally { clearTimeout(t); }
}
async function notify(priority, subject, content) {
  const headers = { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream' };
  if (process.env.RELAY_API_KEY) headers.Authorization = `Bearer ${process.env.RELAY_API_KEY}`;
  const rpc = { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'call_tool', arguments: { tool: 'send_message', args: {
    project: 'trovex-growth', as: 'fullstack-lead', to: ALERT_TO, priority, type: 'notification', subject, content } } } };
  try { const r = await http(RELAY, { method: 'POST', headers, body: JSON.stringify(rpc) }); const txt = await r.text(); return !/"error"/.test(txt); }
  catch (e) { console.error('relay notify failed:', e.message); return false; }
}

(async () => {
  const token = process.env.DOKAN_TOKEN;
  let runs = null;
  try {
    const r = await http(`${DOKAN_BASE}/api/runs?limit=200`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (r.ok) { const j = await r.json(); runs = Array.isArray(j.recent) ? j.recent : []; }
  } catch (e) { /* ambiguous — handled below */ }

  if (runs == null) {
    // Could not read the dokan API — ambiguous, never false-alarm. Carry prev state forward.
    console.log(`::dokan:result:: ${JSON.stringify({ error: 'runs_unreadable', state: prevState || {} })}`);
    console.log('hand-raiser-heartbeat: dokan /api/runs unreadable — no verdict this tick');
    return;
  }

  const mine = runs.filter((r) => Number(r.script_id) === SCRIPT_ID);
  const latest = mine.reduce((acc, r) => {
    const t = Date.parse(r.created_at || '');
    return t && (!acc || t > acc.t) ? { t, id: r.run_id, status: r.status } : acc;
  }, null);

  const ageMin = latest ? (NOW - latest.t) / 60000 : Infinity;
  const stalled = ageMin > MAX_AGE_MIN;
  const wasStalled = !!(prevState && prevState.stalled);

  let alerted = null;
  if (stalled && !wasStalled) {
    const ageStr = latest ? `${Math.round(ageMin)}min` : `none in last ${runs.length} runs`;
    await notify('P0', `🔴 lead-machine ${SCRIPT_ID} STALLED`, `🔴 hand-raiser-pipeline ${SCRIPT_ID} has not run in ${ageStr} (expected ~every 10min). Leads piling up unprocessed — check sched 58 + the executor.`);
    alerted = 'stall';
  } else if (!stalled && wasStalled) {
    await notify('P3', `🟢 lead-machine ${SCRIPT_ID} recovered`, `🟢 hand-raiser-pipeline ${SCRIPT_ID} is running again (last run ${Math.round(ageMin)}min ago).`);
    alerted = 'recovery';
  }

  const result = { script_id: SCRIPT_ID, latest_run_id: latest ? latest.id : null, age_min: latest ? Math.round(ageMin * 10) / 10 : null, max_age_min: MAX_AGE_MIN, stalled, alerted, state: { stalled } };
  console.log(`hand-raiser-heartbeat: ${SCRIPT_ID} ${stalled ? 'STALLED' : 'healthy'} (last run ${latest ? Math.round(ageMin) + 'min ago' : 'NONE'})${alerted ? ` → ${alerted}` : ''}`);
  console.log(`::dokan:result:: ${JSON.stringify(result)}`);
})();
