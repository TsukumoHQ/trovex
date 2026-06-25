/**
 * dokan script: standup-bot  (dokan script_id 424)
 *
 * ⚠️ SUPERSEDED (2026-06-25) by cmo's standup-bot 429 (schedule 60). 424 + schedule 55 were
 * UNSCHEDULED: the relay MCP changed to a `call_tool` DISPATCHER, so 424's direct
 * `tools/call name:'send_message'` started returning -32602 'tool not found' (it worked at
 * build time, before the relay refactor). 429 is the canonical standup-bot. This mirror is
 * kept for reference only, with the transport corrected below to the call_tool pattern.
 *
 * cmo's idle-enforcement tool. Broadcasts a P0 STANDUP to every trovex-growth agent every
 * 2h, 06:00–20:00. Agents thread their 4-line reply to cmo; cmo culls whoever is idle.
 *
 * Why a dokan cron and not a local launchd job: zero-local rule — recurring runs live in
 * dokan, this .mjs is the review mirror only (do NOT run locally).
 *
 * Mechanism (the non-obvious part): the relay's MCP endpoint is a mark3labs StreamableHTTP
 * server mounted at /mcp with WithStateLess(true) — so a single JSON-RPC `tools/call` POST
 * works with NO initialize/session handshake. The relay binds 127.0.0.1 only, but a dokan
 * container reaches it at host.docker.internal:8090 (colima forwards host loopback, so the
 * relay sees the connection as 127.0.0.1 = loopback-exempt → no RELAY_API_KEY needed). The
 * container's docker gateway IP (172.17.0.1) is refused. We send as:'cmo' (executive, so
 * to:'*' broadcast is allowed). RELAY_API_KEY is honored if ever set (forward-compat for an
 * exposed, authed relay), but is not required today.
 *
 * INPUT (DOKAN_INPUT, all optional): { relay_url, project, as, to, subject, content }.
 */
const input = JSON.parse(process.env.DOKAN_INPUT || '{}');
const RELAY = input.relay_url || 'http://host.docker.internal:8090/mcp';
const PROJECT = input.project || 'trovex-growth';
const AS = input.as || 'cmo';            // executive → to:'*' broadcast allowed
const TO = input.to || '*';              // '*' = broadcast to every agent in the project
const SUBJECT = input.subject || 'STANDUP (auto 2h)';
const BODY = input.content ||
  'STANDUP auto. Réponds à cmo, 4 lignes: 1) SHIPPED depuis le dernier (PR#/doc). 2) BLOCKER ou none. 3) NEXT que tu prends now (no idle, northstar = machine à lead + reach). 4) DOGFOOD: dokan script (test+receipt+zero-local+tag) ? trovex SSOT ?';

const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream' };
if (process.env.RELAY_API_KEY) headers['Authorization'] = `Bearer ${process.env.RELAY_API_KEY}`;

// The relay MCP exposes a `call_tool` DISPATCHER, not the tools directly — wrap send_message.
const rpc = {
  jsonrpc: '2.0', id: 1, method: 'tools/call',
  params: { name: 'call_tool', arguments: { tool: 'send_message', args: {
    project: PROJECT, as: AS, to: TO, priority: 'P0', type: 'task', subject: SUBJECT, content: BODY,
  } } },
};

function parseMcp(text) {
  const t = text.trim();
  if (t.startsWith('{')) { try { return JSON.parse(t); } catch {} }
  for (const ln of t.split('\n')) {
    const s = ln.trim();
    if (s.startsWith('data:')) { try { return JSON.parse(s.slice(5).trim()); } catch {} }
  }
  return null;
}

const ctl = new AbortController();
const timer = setTimeout(() => ctl.abort(), 15000);
let out;
try {
  const r = await fetch(RELAY, { method: 'POST', headers, body: JSON.stringify(rpc), signal: ctl.signal });
  clearTimeout(timer);
  const text = await r.text();
  const json = parseMcp(text);
  const rpcErr = json && json.error;
  const toolErr = json && json.result && json.result.isError;
  const ok = r.status >= 200 && r.status < 300 && !rpcErr && !toolErr;
  out = { ok, http_status: r.status, to: TO, project: PROJECT, as: AS,
          rpc_error: rpcErr || null, tool_is_error: !!toolErr,
          raw: ok ? undefined : text.slice(0, 600) };
  console.log(`standup send → ${RELAY} as=${AS} to=${TO} : ${ok ? 'OK' : 'FAIL'} (http ${r.status})`);
} catch (e) {
  clearTimeout(timer);
  out = { ok: false, error: String(e.cause?.code || e.name || e.message), to: TO, relay: RELAY };
  console.log(`standup send FAILED: ${out.error}`);
}
console.log(`::dokan:result:: ${JSON.stringify(out)}`);
if (!out.ok) process.exit(1); // nonzero = deterministic verdict (send failed), surfaced to operator
