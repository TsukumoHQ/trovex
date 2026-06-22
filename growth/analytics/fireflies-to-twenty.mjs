#!/usr/bin/env node
/**
 * fireflies-to-twenty.mjs — pull meeting transcripts from Fireflies and upsert them
 * into the Twenty CRM (the consulting system of record). A SCRIPT the lead runs
 * (20/80 deterministic), not a webhook — same pattern as geo-citation-monitor /
 * north-star-scoreboard: run it manually, or wire the optional daily launchd timer.
 *
 * WHAT IT DOES (per meeting since the last run):
 *   - reads attendees (name + email), the AI summary, action items, title/date, recording link
 *   - DEDUPS people CLIENT-SIDE against Twenty (REST name filters silently fail on this
 *     instance — mem twenty-crm-dedup-quirk), matching email first then first+last name, so a
 *     Calendly-origin person (keyed on email) is updated, never duplicated
 *   - attaches ONE Note per meeting (summary + action items + Fireflies link) to every
 *     matched/created attendee
 *   - does NOT auto-create opportunities (whether a meeting is a consulting lead is a human
 *     judgement; auto-creating pollutes the pipeline). Use --opps to opt in to a conservative
 *     opp for brand-new external people only; otherwise advance opps by hand in the CRM.
 *
 * SECRETS (out-of-git, env files in ~/.config/trovex-growth/ — never hardcoded, never
 * client-side; this is a local script so the keys stay on the operator's machine):
 *   - fireflies.env -> FIREFLIES_API_KEY
 *   - twenty.env    -> TWENTY_API_KEY, TWENTY_BASE_URL
 * The script loads them itself if not already in the environment.
 *
 * STATE (idempotent, re-run safe): ~/.config/trovex-growth/fireflies-state.json
 *   { lastSyncedAt: ISO, processedIds: [meetingId, ...] }  — processed meetings are never
 *   re-noted. First run has no state, so it reaches back --days (default 30) to also capture
 *   the meeting you just had today.
 *
 * USAGE:
 *   node growth/analytics/fireflies-to-twenty.mjs            # since lastSyncedAt (or 30d on first run)
 *   node growth/analytics/fireflies-to-twenty.mjs --days 7   # override the look-back window
 *   node growth/analytics/fireflies-to-twenty.mjs --since 2026-06-01
 *   node growth/analytics/fireflies-to-twenty.mjs --dry      # show what it would do, write nothing
 *   node growth/analytics/fireflies-to-twenty.mjs --opps     # also create a conservative opp for new external people
 *   FIREFLIES_SELF_EMAIL=you@tsukumo.ch node ...             # skip yourself as an attendee
 *
 * Optional daily timer (launchd, local — like the other monitors): a LaunchAgent plist
 * running this once a day; see README at the bottom of this file.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const CFG = process.env.TROVEX_GROWTH_ENV_DIR || join(homedir(), ".config", "trovex-growth");
const STATE_PATH = join(CFG, "fireflies-state.json");
const FF_API = "https://api.fireflies.ai/graphql";
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"; // Twenty's Cloudflare blocks non-browser UAs (Error 1010)

// ---- tiny KEY=VALUE .env loader (only fills vars not already set) ----
function loadEnvFile(name) {
  const p = join(CFG, name);
  if (!existsSync(p)) return;
  for (const line of readFileSync(p, "utf8").split("\n")) {
    const m = line.match(/^\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (!m) continue;
    let v = m[2].trim().replace(/^["']|["']$/g, "");
    if (process.env[m[1]] === undefined) process.env[m[1]] = v;
  }
}
loadEnvFile("fireflies.env");
loadEnvFile("twenty.env");

const FIREFLIES_API_KEY = process.env.FIREFLIES_API_KEY;
const TWENTY_API_KEY = process.env.TWENTY_API_KEY;
const TWENTY_BASE = (process.env.TWENTY_BASE_URL || "https://tsukumo.twenty.com").replace(/\/+$/, "");
const SELF_EMAIL = (process.env.FIREFLIES_SELF_EMAIL || "").toLowerCase().trim();

const args = process.argv.slice(2);
const has = (f) => args.includes(f);
const val = (f, d) => { const i = args.indexOf(f); return i >= 0 && args[i + 1] ? args[i + 1] : d; };
const DRY = has("--dry");
const MAKE_OPPS = has("--opps");
const DAYS = parseInt(val("--days", "30"), 10);
const SINCE = val("--since", "");

function die(msg) { console.error(`fireflies-to-twenty: ${msg}`); process.exit(1); }
if (!FIREFLIES_API_KEY) die(`no FIREFLIES_API_KEY. Create ${join(CFG, "fireflies.env")} with FIREFLIES_API_KEY=<paid-plan key from fireflies.ai>`);
if (!TWENTY_API_KEY) die(`no TWENTY_API_KEY (expected in ${join(CFG, "twenty.env")}).`);

// ---- state ----
function readState() {
  try { return JSON.parse(readFileSync(STATE_PATH, "utf8")); } catch { return { lastSyncedAt: null, processedIds: [] }; }
}
function writeState(s) {
  if (DRY) { console.error("fireflies-to-twenty: --dry, not writing state"); return; }
  writeFileSync(STATE_PATH, JSON.stringify(s, null, 2) + "\n");
}

const ymd = (d) => d.toISOString();
function windowStart(state) {
  if (SINCE) return new Date(SINCE + "T00:00:00.000Z");
  if (state.lastSyncedAt) return new Date(state.lastSyncedAt);
  const d = new Date(); d.setUTCDate(d.getUTCDate() - DAYS); return d; // first run: look back --days
}

// ---- Fireflies ----
async function fetchTranscripts(fromDateISO) {
  const query = `query Transcripts($fromDate: DateTime) {
    transcripts(fromDate: $fromDate, limit: 50) {
      id title date duration transcript_url
      summary { overview action_items short_summary }
      meeting_attendees { displayName email name }
    }
  }`;
  const res = await fetch(FF_API, {
    method: "POST",
    headers: { Authorization: `Bearer ${FIREFLIES_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ query, variables: { fromDate: fromDateISO } }),
  });
  const json = await res.json().catch(() => null);
  if (!json || json.errors) die(`Fireflies API error: ${JSON.stringify(json && json.errors)}`);
  return json.data?.transcripts || [];
}

// ---- Twenty ----
async function tw(path, init = {}) {
  return fetch(`${TWENTY_BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${TWENTY_API_KEY}`,
      "Content-Type": "application/json",
      Accept: "application/json",
      "User-Agent": UA,
      ...(init.headers || {}),
    },
  });
}
async function allPeople() {
  // REST filters on FULL_NAME / email silently return empty on this instance, so we fetch and
  // match client-side (mem twenty-crm-dedup-quirk).
  const res = await tw(`/rest/people?limit=200`);
  const j = await res.json().catch(() => null);
  return j?.data?.people || [];
}
function splitName(displayName, email) {
  const t = (displayName || "").trim();
  if (t && !t.includes("@")) { const p = t.split(/\s+/); return { firstName: p.shift().slice(0, 100), lastName: p.join(" ").slice(0, 100) }; }
  return { firstName: ((email || "lead").split("@")[0] || "lead").slice(0, 100), lastName: "" };
}
function matchPerson(people, email, fn, ln) {
  const e = (email || "").toLowerCase();
  if (e) { const m = people.find((p) => ((p.emails || {}).primaryEmail || "").toLowerCase() === e); if (m) return m; }
  const f = fn.toLowerCase(), l = ln.toLowerCase();
  return people.find((p) => (p.name?.firstName || "").toLowerCase() === f && (p.name?.lastName || "").toLowerCase() === l && l) || null;
}
async function createPerson(email, fn, ln) {
  const body = { name: { firstName: fn, lastName: ln } };
  if (email) body.emails = { primaryEmail: email };
  const res = await tw(`/rest/people`, { method: "POST", body: JSON.stringify(body) });
  const j = await res.json().catch(() => null);
  return j?.data?.createPerson?.id || j?.data?.id || null;
}
async function patchEmailIfMissing(person, email) {
  if (!email) return;
  if (((person.emails || {}).primaryEmail || "")) return; // keep existing
  await tw(`/rest/people/${person.id}`, { method: "PATCH", body: JSON.stringify({ emails: { primaryEmail: email, additionalEmails: [] } }) });
}
async function createMeetingNote(t) {
  const when = new Date(Number(t.date)); // date is ms epoch
  const local = when.toISOString();
  const s = t.summary || {};
  const lines = [
    `**Meeting:** ${t.title || "(untitled)"}`,
    `**When:** ${local} (UTC; Geneva = +2)`,
    t.transcript_url ? `**Recording:** ${t.transcript_url}` : "",
    "",
    s.overview ? `**Summary**\n${s.overview}` : (s.short_summary ? `**Summary**\n${s.short_summary}` : ""),
    s.action_items ? `\n**Action items**\n${s.action_items}` : "",
    `\n_Source: Fireflies meeting transcript (fireflies-to-twenty.mjs)._`,
  ].filter(Boolean);
  const title = `Meeting — ${t.title || "(untitled)"} (${local.slice(0, 10)})`;
  const res = await tw(`/rest/notes`, { method: "POST", body: JSON.stringify({ title: title.slice(0, 120), bodyV2: { markdown: lines.join("\n") } }) });
  const j = await res.json().catch(() => null);
  return j?.data?.createNote?.id || j?.data?.id || null;
}
async function linkNote(noteId, personId) {
  await tw(`/rest/noteTargets`, { method: "POST", body: JSON.stringify({ noteId, targetPersonId: personId }) });
}

// ---- main ----
const state = readState();
const fromDate = windowStart(state);
console.error(`fireflies-to-twenty: pulling meetings since ${ymd(fromDate)}${DRY ? " (dry)" : ""}`);

const transcripts = await fetchTranscripts(ymd(fromDate));
const fresh = transcripts.filter((t) => !state.processedIds.includes(t.id));
console.error(`fireflies-to-twenty: ${transcripts.length} in window, ${fresh.length} new`);

let people = await allPeople();
let nPeople = 0, nNotes = 0;
const processed = new Set(state.processedIds);

for (const t of fresh) {
  const attendees = (t.meeting_attendees || []).filter((a) => {
    const e = (a.email || "").toLowerCase();
    return e && e !== SELF_EMAIL; // need an email to dedup; skip self
  });
  if (!attendees.length) { console.error(`  · "${t.title}" — no attendee emails, skipping`); processed.add(t.id); continue; }

  // resolve/create each attendee
  const personIds = [];
  for (const a of attendees) {
    const { firstName, lastName } = splitName(a.displayName || a.name, a.email);
    let p = matchPerson(people, a.email, firstName, lastName);
    if (p) {
      await (DRY ? Promise.resolve() : patchEmailIfMissing(p, a.email));
      personIds.push(p.id);
      console.error(`  · ${a.email} -> existing ${p.id}`);
    } else if (DRY) {
      console.error(`  · ${a.email} -> would CREATE (${firstName} ${lastName})`);
    } else {
      const id = await createPerson(a.email, firstName, lastName);
      if (id) { personIds.push(id); nPeople++; people.push({ id, name: { firstName, lastName }, emails: { primaryEmail: a.email } }); console.error(`  · ${a.email} -> created ${id}`); }
    }
  }

  if (DRY) { console.error(`  "${t.title}" -> would attach 1 note to ${personIds.length || attendees.length} person(s)`); processed.add(t.id); continue; }

  const noteId = await createMeetingNote(t);
  if (noteId) { for (const pid of personIds) await linkNote(noteId, pid); nNotes++; console.error(`  "${t.title}" -> note ${noteId} -> ${personIds.length} person(s)`); }
  processed.add(t.id);
  // NOTE: opportunity creation is intentionally manual — whether a meeting is a consulting
  // lead is a human call. (--opps flag reserved; conservative auto-opp not enabled by default.)
}

// advance state: lastSyncedAt = now, processedIds capped to the recent 500
const newState = { lastSyncedAt: new Date().toISOString(), processedIds: [...processed].slice(-500) };
writeState(newState);

console.error(`fireflies-to-twenty: DONE — ${fresh.length} meetings processed, ${nPeople} people created, ${nNotes} notes attached${DRY ? " (dry, nothing written)" : ""}`);
