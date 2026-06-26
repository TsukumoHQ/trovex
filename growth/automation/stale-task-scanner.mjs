/**
 * dokan script: stale-task-scanner  (dokan, runtime node, schedule ~every 30min, feed_prev_result)
 *
 * Autonomy engine (CTO ask, TSU / task 96340509): find STALE relay tasks + emit `task-stale` so
 * wraith's notification rule fires a P0 nudge to the assignee → the board self-drives, no manual
 * chasing. This .mjs is the review mirror; the live script runs in dokan.
 *
 * READ: list active tasks via the relay MCP `call_tool` dispatcher (tools/call → call_tool →
 * {tool:'list_tasks', args:{...,status:'active',format:'json'}}). The relay answers
 * {result:{content:[{type:'text',text:'<json>'}]}} — we parse content[0].text.
 * EMIT (sink confirmed live 2026-06-26, wraith-dev): POST host.docker.internal:8090/api/notification-events
 *   {project, name:'task-stale', agent?, payload:{...}} → {"emitted":true,"event":"event:task-stale"}.
 *   wraith's rule routes it → P0 '⏰ stale <task>, move it' to `agent` (+ cto escalation when escalate=true).
 *
 * STALE thresholds (idle measured from `last_activity_at`, wraith's live field; CTO scope 2026-06-26):
 * CLAIMED work only — accepted >1.5h, in-progress >1.5h. PENDING is NOT nudged (unclaimed = no owner).
 * ESCALATE at ≥2× the threshold.
 * ASSIGNEE: profile_slug (native tasks) → else parse `**Lane:** <agent>` from the description →
 * else OMIT `agent` (Linear tasks are often unassigned; wraith default-routes). dispatched_by is the
 * dispatcher, never the assignee.
 *
 * ANTI-SPAM (feed_prev_result): prev_result.state.emitted = { task_id: tier } (1 = nudged once,
 * 2 = escalated). Emit only on first-cross, then re-emit ONCE when it crosses 2× (escalation) — never
 * every 30min into a flood. A task that goes un-stale (moved/done) drops out of the active list → its
 * entry is pruned, so a later regression re-nudges cleanly.
 *
 * TRANSPORT: relay reachable from the container at host.docker.internal:8090 (loopback-exempt; Bearer
 * only if RELAY_API_KEY). RUNTIME: node (dokan), no deps. exit 0 always (monitor; rides ::dokan:result::).
 * INPUT (DOKAN_INPUT, all optional): { dryRun, thresholds:{pending,accepted,inProgress}, relay_url,
 *   relay_base, prev_result }.
 */
const input = (() => { try { return JSON.parse(process.env.DOKAN_INPUT || '{}'); } catch { return {}; } })();
const prevState = (input.prev_result && input.prev_result.state) || null;
const DRY = !!input.dryRun;
const ONLY = input.onlyTaskId || null;          // controlled test: only this task is eligible to fire
const MAX_FIRE = Number.isInteger(input.maxFire) ? input.maxFire : 10; // burst guard/run (list is priority-sorted → nudge hottest first; rest fire next runs)
// CTO scope (2026-06-26): nudge only CLAIMED work (accepted + in-progress) idle >~1.5h. PENDING is
// NOT emitted — an unclaimed task has no owner to nudge (wraith resolves the assignee relay-side; we
// don't filter on it, we just don't nudge un-started tasks). pending kept here only as an opt-in override.
const TH = Object.assign({ accepted: 1.5, inProgress: 1.5 }, input.thresholds || {}); // hours
const RELAY = input.relay_url || 'http://host.docker.internal:8090/mcp';
const RELAY_BASE = input.relay_base || 'http://host.docker.internal:8090';
const NOW = Date.now();

async function http(url, opts = {}, ms = 12000) {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { ...opts, signal: ctl.signal }); } finally { clearTimeout(t); }
}
function authHeaders(extra = {}) {
  const h = { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream', ...extra };
  if (process.env.RELAY_API_KEY) h.Authorization = `Bearer ${process.env.RELAY_API_KEY}`;
  return h;
}

// call a relay tool via the call_tool DISPATCHER; returns the parsed tool result (or null).
async function callTool(tool, args) {
  const rpc = { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'call_tool', arguments: { tool, args } } };
  const r = await http(RELAY, { method: 'POST', headers: authHeaders(), body: JSON.stringify(rpc) });
  const txt = await r.text();
  let env; try { env = JSON.parse(txt); } catch { return null; }
  const text = env?.result?.content?.[0]?.text;
  if (!text) return null;
  try { return JSON.parse(text); } catch { return null; }
}

async function emit(body) {
  if (DRY) return { dry: true };
  try {
    const r = await http(`${RELAY_BASE}/api/notification-events`, { method: 'POST', headers: authHeaders(), body: JSON.stringify(body) });
    const txt = await r.text(); let j; try { j = JSON.parse(txt); } catch { j = { raw: txt.slice(0, 120) }; }
    return { ok: r.ok && j.emitted === true, resp: j };
  } catch (e) { return { ok: false, err: e.message }; }
}

function ageHours(iso) { const t = Date.parse(iso || ''); return t ? (NOW - t) / 3.6e6 : null; }
function thresholdFor(status) {
  // PENDING is intentionally NOT nudged (unclaimed = no owner). Opt back in only via input.thresholds.pending.
  if (status === 'pending') return TH.pending ?? null;
  if (status === 'accepted') return TH.accepted;
  if (status === 'in-progress') return TH.inProgress;
  return null; // blocked/in-review/done/cancelled are not "stale" here
}
function resolveAgent(t) {
  // assigned_to is the clean relay agent (wraith populated it); profile_slug next; lane-parse the
  // description as a last resort; else omit (wraith resolves relay-side via linear_routing).
  const direct = (t.assigned_to || t.claimed_by || t.profile_slug || '').trim();
  if (direct) return direct;
  const m = /\*\*Lane:\*\*\s*`?([a-z0-9][a-z0-9-]+)`?/i.exec(t.description || '');
  return m ? m[1].toLowerCase() : null;
}

(async () => {
  const list = await callTool('list_tasks', { project: 'trovex-growth', as: 'fullstack-lead', status: 'active', format: 'json', limit: 200 });
  if (!list || !Array.isArray(list.tasks)) {
    console.log(`::dokan:result:: ${JSON.stringify({ error: 'list_tasks_unreadable', state: prevState || {} })}`);
    console.log('stale-scanner: could not read active tasks');
    return; // exit 0 — a transient read miss is not a crash; next tick retries
  }

  const prevEmitted = (prevState && prevState.emitted) || {};
  const emitted = {};
  const stale = [];
  const fired = [];

  for (const t of list.tasks) {
    const th = thresholdFor(t.status);
    if (th == null) continue;
    // idle = time since the last agent activity (wraith's live `last_activity_at`, bumped on every status
    // transition/claim). Fallback to dispatched_at only if the field is missing. This is TRUE idle, not board-age.
    const age = ageHours(t.last_activity_at || t.dispatched_at);
    if (age == null || age < th) continue;

    const escalate = age >= th * 2;
    const tier = escalate ? 2 : 1;
    const prevTier = prevEmitted[t.id] || 0;
    emitted[t.id] = prevTier;                             // carry forward; only bump on an ACTUAL emit
    stale.push({ id: t.id, key: t.linear_key, status: t.status, ageH: Math.round(age * 10) / 10, tier });

    if (tier <= prevTier) continue;                       // already nudged at this tier → no re-spam
    if (ONLY && t.id !== ONLY) continue;                  // controlled test: only the named task fires (others retry next run)
    if (fired.length >= MAX_FIRE) continue;               // burst guard — skipped tasks keep prevTier, fire next run

    const agent = resolveAgent(t);
    const body = {
      project: 'trovex-growth', name: 'task-stale', ...(agent ? { agent } : {}),
      payload: {
        task_id: t.id, linear_key: t.linear_key || null, title: t.title, status: t.status,
        dispatched_by: t.dispatched_by || null, age_hours: Math.round(age * 10) / 10,
        threshold_hours: th, escalate,
      },
    };
    const res = await emit(body);
    if (res.ok) emitted[t.id] = tier; // mark nudged only on a real success — a failed emit (or a dry run) retries / doesn't persist
    fired.push({ id: t.id, key: t.linear_key, status: t.status, ageH: Math.round(age * 10) / 10, escalate, agent: agent || null, sent: DRY ? 'dry' : !!res.ok });
  }

  const result = { scanned: list.tasks.length, stale: stale.length, fired: fired.length, dryRun: DRY, thresholds: TH, items: fired, state: { emitted } };
  console.log(`stale-scanner: ${stale.length} stale, ${fired.length} ${DRY ? 'would-fire (dry)' : 'fired'} of ${list.tasks.length} active`);
  console.log(`::dokan:result:: ${JSON.stringify(result)}`);
})();
