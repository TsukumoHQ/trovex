/**
 * dokan script: release-watcher  (dokan script_id 431, schedule_id 61, cron `0 0 * * * *` hourly)
 *
 * Owner flag (via CTO): cmo wasn't being told when a suite repo cut a release (trovex 0.11.1,
 * dokan v0.1.0 shipped with zero auto-notify). This polls GitHub Releases for the 4 public
 * suite repos and relay-notifies cmo on a fresh release. Runs in dokan (zero-local); this
 * .mjs is the review mirror.
 *
 * NEW-detect: a release whose published_at is within the `sinceMinutes` window. No persistent
 * store, so the window is ≥ the cron interval (never-miss); a rare duplicate notify on the
 * overlap is acceptable for a low-frequency event (a release notif is cheap, a missed one isn't).
 * If dups ever annoy, upgrade to relay get_memory/set_memory for a last-seen-tag-per-repo store.
 *
 * TRANSPORT: the relay MCP exposes a `call_tool` DISPATCHER — a raw `tools/call name:'send_message'`
 * returns -32602. Must wrap: tools/call → name:'call_tool' → arguments:{tool:'send_message',args:{...}}.
 * Reachable from the container at host.docker.internal:8090 (loopback-exempt, no key).
 *
 * RUNTIME: node (dokan), no deps. GitHub Releases API is unauthenticated (all 4 repos public;
 * 60 req/h limit, 4 calls/run = fine). exit-0 monitor (findings ride ::dokan:result::).
 * INPUT (DOKAN_INPUT, all optional): { repos:[...], sinceMinutes:70, notifyTo:'cmo', relay_url }.
 */
const input = JSON.parse(process.env.DOKAN_INPUT || '{}');
const REPOS = input.repos || ['TsukumoHQ/trovex', 'TsukumoHQ/dokan', 'TsukumoHQ/WRAI.TH', 'TsukumoHQ/yoru'];
const SINCE_MIN = Number(input.sinceMinutes) > 0 ? Number(input.sinceMinutes) : 70; // > hourly cron
const NOTIFY_TO = input.notifyTo || 'cmo';
const RELAY = input.relay_url || 'http://host.docker.internal:8090/mcp';
const cutoff = Date.now() - SINCE_MIN * 60000;

async function ghReleases(slug) {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), 12000);
  try {
    const r = await fetch(`https://api.github.com/repos/${slug}/releases?per_page=5`, {
      signal: ctl.signal, headers: { 'Accept': 'application/vnd.github+json', 'User-Agent': 'trovex-release-watcher/1' },
    });
    clearTimeout(t);
    if (!r.ok) return { slug, err: `http_${r.status}` };
    const arr = await r.json();
    return { slug, releases: Array.isArray(arr) ? arr : [] };
  } catch (e) { clearTimeout(t); return { slug, err: String(e.cause?.code || e.name) }; }
}

// relay send via the call_tool DISPATCHER (raw name:send_message → -32602; must wrap).
// monitor-failure-escalation: success/info → cmo P2; failure → CTO P0 (single on-call).
async function notify(subject, content, to = NOTIFY_TO, priority = 'P2') {
  const rpc = { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'call_tool', arguments: { tool: 'send_message', args: {
    project: 'trovex-growth', as: 'fullstack-lead', to, priority, type: 'notification', subject, content } } } };
  try {
    const r = await fetch(RELAY, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream' }, body: JSON.stringify(rpc) });
    const txt = await r.text();
    return !/"error"/.test(txt);
  } catch (e) { return false; }
}

const fresh = [];
const errors = [];
for (const slug of REPOS) {
  const res = await ghReleases(slug);
  if (res.err) { errors.push({ slug, err: res.err }); continue; }
  for (const rel of res.releases) {
    if (rel.draft) continue;
    const pub = Date.parse(rel.published_at || rel.created_at || '');
    if (pub && pub >= cutoff) {
      fresh.push({ repo: slug, tag: rel.tag_name, name: rel.name || rel.tag_name, url: rel.html_url, prerelease: !!rel.prerelease, published_at: rel.published_at });
    }
  }
}

let notified = 0;
for (const f of fresh) {
  // SUCCESS/info (a new release = a win) → cmo at P2.
  const ok = await notify(
    `\u{1F680} New release: ${f.repo} ${f.tag}${f.prerelease ? ' (pre)' : ''}`,
    `${f.repo} cut a release.\n- tag: ${f.tag}\n- name: ${f.name}\n- published: ${f.published_at}\n- ${f.url}`,
    NOTIFY_TO, 'P2');
  if (ok) notified++;
}

// FAILURE (a repo's releases couldn't be fetched) → CTO at P0, terse one-liner (monitor-failure-escalation).
if (errors.length) {
  await notify(`\u{1F534} release-watcher (431) FETCH FAIL: ${errors.map(e => `${e.slug}=${e.err}`).join(', ')}`,
    `release-watcher couldn't reach: ${JSON.stringify(errors)}`, 'cto', 'P0');
}

const result = { window_min: SINCE_MIN, repos: REPOS.length, fresh: fresh.length, notified, notifyTo: NOTIFY_TO, errors, releases: fresh };
console.log(`release-watcher: ${fresh.length} fresh, ${notified} notified (window ${SINCE_MIN}min)`);
console.log(`::dokan:result:: ${JSON.stringify(result)}`);
