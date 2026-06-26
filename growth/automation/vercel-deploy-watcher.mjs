/**
 * dokan script: vercel-deploy-watcher  (dokan, runtime node, schedule ~every 4min, feed_prev_result)
 *
 * Owner ask (via CTO). Same monitor family as release-watcher (431) / IndexNow (432): poll the
 * Vercel REST API for the suite's PROD projects and relay-notify on a NEW terminal deploy state
 * (READY / ERROR / CANCELED). Catch a FAILED prod deploy fast (no ship-and-pray). Poll-only — a
 * Vercel webhook was declined (it needs a public endpoint = exposes the backbone); this is zero
 * surface. This .mjs is the review mirror; the live script runs in dokan.
 *
 * ROUTING (monitor-failure-escalation + CTO scope 2026-06-26: READY is the EXPECTED case, per-deploy
 * ping = noise). Defaults: ERROR/CANCELED → cto P1 (the actionable signal); READY → SUPPRESSED (no ping,
 * still in ::dokan:result::). Overridable via input (errorTo/readyTo/errorPrio/readyPrio/notifyReady).
 *
 * STATE (feed_prev_result): DOKAN_INPUT.prev_result.state = { <project>: <last-notified uid> }.
 * Notify ONLY when the latest prod deployment is in a NEW terminal state we haven't seen — never
 * re-spam BUILDING/QUEUED or an already-notified uid. First run with no prev = SEED (record the
 * current terminal uids silently, don't backfill-notify the whole history).
 *
 * TRANSPORT: the relay MCP is a `call_tool` DISPATCHER — a raw `tools/call name:'send_message'`
 * returns -32602. Must wrap: tools/call → name:'call_tool' → arguments:{tool:'send_message',args:{...}}.
 * Reachable from the container at host.docker.internal:8090 (loopback-exempt; Bearer only if
 * RELAY_API_KEY is set). VERCEL_TOKEN = dokan secret (read scope), injected as env, never inline.
 *
 * RUNTIME: node (dokan), no deps. exit 0 always (monitor; findings ride ::dokan:result::).
 * INPUT (DOKAN_INPUT, all optional): { projects:[{id,name}], team, errorTo, readyTo, errorPrio,
 *   readyPrio, relay_url, prev_result }.
 */
const input = (() => { try { return JSON.parse(process.env.DOKAN_INPUT || '{}'); } catch { return {}; } })();
const prevState = (input.prev_result && input.prev_result.state) || null;

const TEAM = input.team || 'team_5OLH1GrvOmFUOkTI0eyRjNnA';
// Suite PROD projects only (client/v0 projects on the same team are excluded by design).
const PROJECTS = Array.isArray(input.projects) && input.projects.length ? input.projects : [
  { id: 'prj_YF2512MDXaAn23E6K8if1dDAPyST', name: 'trovex' },        // trovex.dev
  { id: 'prj_YW34KOCOBduwBncf4JXNarFoc5zz', name: 'tsukumo' },       // tsukumo.ch
  { id: 'prj_PeKXCPHm64WPDx7nTf7SjIo4W9AG', name: 'yoru-app' },      // yoru.sh app
  { id: 'prj_ss5KhXDjmcIvLm5tophcoYjPsDnS', name: 'yoru-marketing' },// yoru.sh site
];
const ERROR_TO = input.errorTo || 'cto';
const READY_TO = input.readyTo || 'cto';
const ERROR_PRIO = input.errorPrio || 'P1';     // CTO 2026-06-26: ERROR/FAILED = the actionable signal → P1
const READY_PRIO = input.readyPrio || 'P3';
// CTO 2026-06-26: a prod deploy READY is the EXPECTED case — one ping per deploy is noise. Suppress by
// default (the run still records it in ::dokan:result::); opt back in via notifyReady (e.g. a digest later).
const NOTIFY_READY = input.notifyReady === true;
const RELAY = input.relay_url || 'http://host.docker.internal:8090/mcp';
const TERMINAL = new Set(['READY', 'ERROR', 'CANCELED']);

async function http(url, opts = {}, ms = 12000) {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { ...opts, signal: ctl.signal }); } finally { clearTimeout(t); }
}

async function latestProdDeploy(p) {
  const token = process.env.VERCEL_TOKEN;
  if (!token) return { name: p.name, err: 'no_token' };
  const url = `https://api.vercel.com/v6/deployments?projectId=${p.id}&teamId=${TEAM}&target=production&limit=3`;
  try {
    const r = await http(url, { headers: { Authorization: `Bearer ${token}`, 'User-Agent': 'dokan-vercel-deploy-watcher/1' } });
    if (!r.ok) return { name: p.name, err: `http_${r.status}` };
    const j = await r.json();
    const d = (j.deployments || [])[0];
    if (!d) return { name: p.name, none: true };
    const state = d.state || d.readyState || 'UNKNOWN';
    const m = d.meta || {};
    return {
      name: p.name, uid: d.uid, state,
      ref: m.githubCommitRef || null, sha: (m.githubCommitSha || '').slice(0, 7) || null,
      url: d.url ? `https://${d.url}` : null,
      inspector: d.inspectorUrl || null,
    };
  } catch (e) { return { name: p.name, err: String(e.cause?.code || e.name) }; }
}

async function notify(to, priority, subject, content) {
  const headers = { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream' };
  if (process.env.RELAY_API_KEY) headers.Authorization = `Bearer ${process.env.RELAY_API_KEY}`;
  const rpc = { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'call_tool', arguments: { tool: 'send_message', args: {
    project: 'trovex-growth', as: 'fullstack-lead', to, priority, type: 'notification', subject, content } } } };
  try { const r = await http(RELAY, { method: 'POST', headers, body: JSON.stringify(rpc) }); const txt = await r.text(); return !/"error"/.test(txt); }
  catch (e) { console.error('relay notify failed:', e.message); return false; }
}

function line(d) {
  const emoji = d.state === 'READY' ? '🟢' : d.state === 'CANCELED' ? '🟡' : '🔴';
  const commit = d.ref ? ` ${d.ref}${d.sha ? `@${d.sha}` : ''}` : '';
  const link = d.inspector || d.url || '';
  return `${emoji} ${d.name} prod deploy ${d.state} —${commit}${link ? ` · ${link}` : ''}`;
}

(async () => {
  const results = await Promise.all(PROJECTS.map(latestProdDeploy));
  const state = prevState ? { ...prevState } : {};
  const errors = results.filter((r) => r.err).map((r) => ({ name: r.name, err: r.err }));
  const seeding = !prevState;
  const notified = [];

  for (const d of results) {
    if (d.err || d.none || !TERMINAL.has(d.state)) continue; // skip blind/empty/in-flight
    if (state[d.name] === d.uid) continue;                   // already handled this terminal deploy
    state[d.name] = d.uid;                                   // record before notifying (no re-spam)
    if (seeding) continue;                                   // first run: record current, don't backfill
    const isFail = d.state === 'ERROR' || d.state === 'CANCELED';
    if (!isFail && !NOTIFY_READY) { notified.push({ name: d.name, state: d.state, uid: d.uid, to: null, sent: 'suppressed' }); continue; } // READY = expected, no ping
    const ok = await notify(isFail ? ERROR_TO : READY_TO, isFail ? ERROR_PRIO : READY_PRIO, `Vercel deploy ${d.state}: ${d.name}`, line(d));
    notified.push({ name: d.name, state: d.state, uid: d.uid, to: isFail ? ERROR_TO : READY_TO, sent: ok });
  }

  // BLIND = EVERY project fetch failed (token revoked / Vercel API down). EDGE-dedup via state._blind so a
  // persistent outage alerts ONCE (healthy→blind), not every tick — else a dead VERCEL_TOKEN spams cto every run.
  const blind = errors.length === PROJECTS.length;
  const wasBlind = !!(prevState && prevState._blind);
  state._blind = blind;
  let blindAlert = null;
  if (!seeding && blind && !wasBlind) {
    await notify('cto', 'P1', 'Vercel deploy-watcher BLIND', `🔴 vercel-deploy-watcher blind — all ${errors.length} fetches failed (${errors.map((e) => e.err).join(',')}). Check VERCEL_TOKEN (CLI OAuth tokens rotate — use a long-lived access token).`);
    blindAlert = 'blind';
  } else if (!seeding && !blind && wasBlind) {
    await notify('cto', 'P3', 'Vercel deploy-watcher recovered', `🟢 vercel-deploy-watcher can reach the Vercel API again.`);
    blindAlert = 'recovery';
  }

  const result = { checked: PROJECTS.length, seeding, blind, blindAlert, notified, errors, state };
  console.log(`vercel-deploy-watcher: ${notified.length} notified, ${errors.length} errors${seeding ? ' (seeded)' : ''}`);
  console.log(`::dokan:result:: ${JSON.stringify(result)}`);
})();
