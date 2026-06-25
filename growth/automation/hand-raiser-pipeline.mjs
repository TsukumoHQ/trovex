/**
 * dokan script: hand-raiser-pipeline (zero live send; commitTwenty writes DRAFTS to the CRM)
 *
 * cmo redirect (5219587a / GO doc 2fcc61ce): the lead machine's contact source is
 * HAND-RAISERS (people who gave us their email: Calendly bookings, contact/form fills,
 * newsletter + waitlist signups) — NOT stargazers (those are a cold prioritization
 * signal, handled by lead-pipeline.mjs). Same engine: enrich → cheap-LLM ICP classify →
 * score → tier A/B/C → ::dokan:result:: (the tiered queue donna works).
 *
 * ⛔ NO SEND (hard invariant): reads → scores → tiers → drafts → (commitTwenty) writes a
 * Person + a 'Setter draft' Note to Twenty = donna's queue. It NEVER sends outreach — there
 * is NO email/Gmail/Telegram/Calendly-send path in this script. Sending is donna's separate,
 * human-gated step. commitTwenty=true (the CRM write) is owner-approved; live OUTREACH stays
 * a separate human action. commitTwenty=false (default) = plan-only, writes nothing.
 *
 * RUNTIME: node (dokan). No external deps — global fetch.
 * INPUT  : env DOKAN_INPUT (JSON), all optional:
 *   { tables:["leads","waitlist","newsletter"], perTable:200, maxClassify:60,
 *     model:"gpt-4o-mini", sinceDays:0, sinceMinutes:0, commitTwenty:false }
 *
 * TWO RUN MODES (same script):
 *   - DAILY FULL (sched 40, 06:23, commitTwenty:false): visibility backstop — scores the
 *     whole queue, emits ::dokan:result::, writes nothing.
 *   - 10-MIN POLLER (commitTwenty:true, sinceMinutes:15, tables:["leads"]): the near-real-time
 *     commit path — only rows created in the last `sinceMinutes` window are read, so a brand-new
 *     booking lands in donna's Twenty queue in ~10min instead of ~24h. The window (15min) is
 *     DELIBERATELY WIDER than the 10-min cron interval so a delayed run never leaves a gap that
 *     drops a booked lead (never-miss). The ~5min overlap means a lead can be processed by two
 *     consecutive runs — so writes are made idempotent at the source: Person via 3-state email
 *     dedup (never a dup Person), Note via a 'Setter draft' existence check (never a dup Note).
 *     Net: at-least-once runs, exactly-once Person + Note.
 * SECRETS (dokan store → env): SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (read the consented
 *   hand-raiser rows; service-role bypasses RLS, server-only — injected as a dokan secret,
 *   never in source), OPENAI_API_KEY (the cheap classify). Degrades to a null verdict, never
 *   throws, if a key is absent.
 * OUTPUT : `::dokan:result::<json>` = { generated, counts, leads:[{email,tier,score,...}] }.
 *
 * HONESTY: consented first-party data only. Underivable field = null. The LLM verdict is
 * stored with its reason; we never invent company/teamIntent/score.
 */

function input() { try { return JSON.parse(process.env.DOKAN_INPUT || "{}"); } catch { return {}; } }

const PERSONAL_DOMAINS = /(^|\.)(gmail|googlemail|outlook|hotmail|live|proton(mail)?|yahoo|ymail|icloud|me|aol|gmx|mail|yandex|qq|163)\./;

function sb() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  return url && key ? { url: url.replace(/\/+$/, ""), key } : null;
}

// Read consented hand-raiser rows from one Supabase table. Best-effort: [] on any failure.
async function readTable(c, table, perTable, sinceISO) {
  // Columns differ per table; select '*' and normalize in code (avoids a 400 on a missing col).
  let path = `/rest/v1/${table}?select=*&order=created_at.desc&limit=${perTable}`;
  if (sinceISO) path += `&created_at=gte.${sinceISO}`;
  try {
    const res = await fetch(`${c.url}${path}`, {
      headers: { apikey: c.key, Authorization: `Bearer ${c.key}`, Accept: "application/json" },
    });
    if (!res.ok) return [];
    const rows = await res.json();
    return Array.isArray(rows) ? rows : [];
  } catch { return []; }
}

// Normalize a raw row from any hand-raiser table into the common lead shape.
function normalize(row, table) {
  const email = String(row.email || "").trim().toLowerCase();
  const domain = email.includes("@") ? email.split("@")[1] : null;
  return {
    email,
    table,                                   // which surface they raised a hand on
    name: row.name || null,
    company: row.company || null,
    emailDomain: domain,
    companyDomain: domain && !PERSONAL_DOMAINS.test(domain) ? domain : null,
    role: row.role || null,
    source: row.source || row.geo_source || row.channel || null,
    teamSize: row.team_size || null,         // leads (contact form intake) — strong ICP signal
    aiUse: row.ai_use || null,               // leads — strong ICP signal
    utmSource: row.utm_source || null,
    createdAt: row.created_at || null,
  };
}

// Fuzzy ICP classification — ONE cheap LLM call. {fit, teamIntent, confidence, why}.
async function classify(lead, model) {
  const key = process.env.OPENAI_API_KEY;
  if (!key) return { fit: null, teamIntent: null, confidence: "low", why: "no_openai_key", model: null };
  const facts = [
    `raised_hand_via: ${lead.table}`,
    lead.name && `name: ${lead.name}`,
    lead.company && `company: ${lead.company}`,
    lead.companyDomain && `company_domain: ${lead.companyDomain}`,
    lead.role && `role: ${lead.role}`,
    lead.teamSize && `team_size: ${lead.teamSize}`,
    lead.aiUse && `ai_use: ${lead.aiUse}`,
    lead.source && `acquisition_source: ${lead.source}`,
  ].filter(Boolean).join("\n");
  const sys =
    "You qualify inbound hand-raisers for a consultancy that helps teams run AI coding agents in production. " +
    "ICP = an engineering TEAM (not a solo hobbyist) running or adopting AI coding agents at scale. " +
    "Judge ONLY from the given facts (they volunteered these). Do not invent. Thin facts → fit:false, low confidence. " +
    'Reply ONLY compact JSON: {"fit":boolean,"teamIntent":boolean,"confidence":"low|med|high","why":"<=140 chars"}';
  try {
    const res = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: model || "gpt-4o-mini", temperature: 0, max_tokens: 120,
        messages: [{ role: "system", content: sys }, { role: "user", content: facts }],
        response_format: { type: "json_object" },
      }),
    });
    if (!res.ok) return { fit: null, teamIntent: null, confidence: "low", why: `llm_${res.status}`, model };
    const v = JSON.parse((await res.json())?.choices?.[0]?.message?.content || "{}");
    return {
      fit: typeof v.fit === "boolean" ? v.fit : null,
      teamIntent: typeof v.teamIntent === "boolean" ? v.teamIntent : null,
      confidence: ["low", "med", "high"].includes(v.confidence) ? v.confidence : "low",
      why: String(v.why || "").slice(0, 140), model,
    };
  } catch { return { fit: null, teamIntent: null, confidence: "low", why: "llm_err", model }; }
}

// A CONFIRMED booked call (Calendly/assessment intake) is the hottest hand-raise signal —
// they already committed time. One definition, used by both the score and the draft template,
// so a Calendly/assessment source can never score as booked yet get the "please book" draft.
function isBooked(lead) {
  return lead.table === "leads" && /book|assessment|calendly/i.test(String(lead.source || ""));
}

// Deterministic score (0-100) + tier. Hand-raiser intent + ICP fit + signal strength.
function scoreAndTier(lead, v) {
  let s = 0;
  // Hand-raise intent by surface (a booked call >> a newsletter signup).
  if (lead.table === "leads") s += 25;            // contact/booking form
  else if (lead.table === "waitlist") s += 12;
  else if (lead.table === "newsletter") s += 8;
  if (v.fit === true) s += 35;
  if (v.teamIntent === true) s += 15;
  if (v.confidence === "high") s += 8; else if (v.confidence === "med") s += 4;
  if (lead.companyDomain) s += 8;                  // company email, not personal
  if (lead.teamSize) s += 5;                        // told us team size
  if (lead.aiUse) s += 4;                           // told us their agent usage
  if (isBooked(lead)) s += 35;                      // a confirmed booking → always actionable (≥A floor)
  s = Math.max(0, Math.min(100, s));
  return { score: s, tier: s >= 60 ? "A" : s >= 35 ? "B" : "C" };
}

// A specific TRUE reason for [why-them], a short noun phrase from what the lead actually
// gave us — NEVER a guess (template rule 50a7eca6). No real signal → the generic clause.
function whyThem(lead) {
  if (lead.aiUse) return String(lead.aiUse).slice(0, 80);
  if (lead.teamSize) return `a ${String(lead.teamSize).slice(0, 30)} team running agents`;
  if (lead.company) return `${String(lead.company).slice(0, 40)}'s agent setup`;
  if (lead.companyDomain) return `your team at ${lead.companyDomain}`;
  return "running agents in production"; // generic clause — fair (they hand-raised here), not fabricated
}

// Fill a SETTER draft from the LOCKED templates (50a7eca6). This only stages text; nothing
// sends. S2 (booked-prep, no ask) for a confirmed booking; S3 (value-first → book) otherwise.
// Slots: [name] [why-them] [calendly]. Founder voice, ASK = book the call.
function buildSetterDraft(lead, bookUrl) {
  const name = (lead.name && lead.name.split(/\s+/)[0]) || "there";
  const booked = isBooked(lead);
  if (booked) {
    return {
      template: "S2-booked-prep",
      subject: "looking forward — quick prep",
      body: `Hi ${name}, looking forward to the call. No prep needed on your side. Two things I will likely dig into so we use the time well: (1) where your agents spend tokens today (rereading docs to find what is current is usually most of it), and (2) how many agents and teammates touch the same repo, since the cost compounds there. If you can eyeball those before we talk, great; if not, we cover it live. See you then.`,
    };
  }
  return {
    template: "S3-not-booked-book",
    subject: "worth a quick look?",
    body: `Hi ${name}, thanks for the interest. From what you described (${whyThem(lead)}), there is probably a real token cost hiding in how your agents reread context. Worth a 20 to 30 minute look at where that is happening in your setup? No pitch, just a read on whether it is worth fixing and how. Grab a time that works: ${bookUrl}.`,
  };
}

/* ── Twenty upsert (phase 2b) — port of src/lib/twenty.ts dedup (#468) ────────────
 * Mirror each scored A/B lead into Twenty as a Person + attach its setter draft as a Note
 * = donna's DRAFT-ONLY queue. NEVER contacts the prospect (outreach is a separate human step).
 * Dedup is the SAME 3-state paginated client-side match the route uses — Twenty's REST email
 * filter is unreliable, so only a confirmed "absent" creates; "unknown" skips (never a
 * false-negative dupe). Gated on input.commitTwenty so a test run can emit the plan without
 * touching the CRM. Both writes are idempotent: Person via 3-state email dedup (never a dup
 * Person), Note via twPersonHasDraftNote (skip if a 'Setter draft' Note already exists). */
function twCfg() {
  const key = process.env.TWENTY_API_KEY;
  if (!key) return null;
  const base = (process.env.TWENTY_BASE_URL || "https://api.twenty.com").replace(/\/+$/, "");
  return { base, key };
}
async function twFetch(c, path, init) {
  try {
    return await fetch(`${c.base}${path}`, {
      ...init,
      headers: { Authorization: `Bearer ${c.key}`, "Content-Type": "application/json", Accept: "application/json", ...(init?.headers || {}) },
    });
  } catch { return null; }
}
// 3-state dedup by email (found / absent / unknown). Only "absent" authorizes create.
async function twFindPerson(c, email) {
  const target = String(email).trim().toLowerCase();
  if (!target) return { status: "unknown" };
  let cursor = null;
  for (let page = 0; page < 25; page++) {
    const qs = `/rest/people?limit=200${cursor ? `&starting_after=${encodeURIComponent(cursor)}` : ""}`;
    const res = await twFetch(c, qs, { method: "GET" });
    if (!res || !res.ok) return { status: "unknown" };
    const json = await res.json().catch(() => null);
    if (!json) return { status: "unknown" };
    const people = json.data?.people ?? [];
    for (const p of people) {
      const e = String(p.emails?.primaryEmail ?? "").trim().toLowerCase();
      if (e && e === target && p.id) return { status: "found", id: p.id };
    }
    const pageInfo = json.pageInfo ?? json.data?.pageInfo;
    if (!pageInfo) return people.length < 200 ? { status: "absent" } : { status: "unknown" };
    if (!pageInfo.hasNextPage || !pageInfo.endCursor) return { status: "absent" };
    cursor = pageInfo.endCursor;
  }
  return { status: "unknown" };
}
async function twCreatePerson(c, lead) {
  const parts = String(lead.name || lead.email.split("@")[0]).trim().split(/\s+/);
  const body = { name: { firstName: (parts.shift() || "").slice(0, 100), lastName: parts.join(" ").slice(0, 100) }, emails: { primaryEmail: lead.email } };
  const res = await twFetch(c, "/rest/people", { method: "POST", body: JSON.stringify(body) });
  if (!res || !res.ok) return null;
  const json = await res.json().catch(() => null);
  return json?.data?.createPerson?.id || json?.data?.id || null;
}
// Note-idempotency: true if the Person already has a 'Setter draft' Note, false if not,
// null if the read failed (caller fails OPEN = creates, to never-miss). Twenty REST: the
// person→notes relation is read via noteTargets filtered by targetPersonId (NOT personId,
// which 400s), depth=1 to embed each note's title (verified live, probe 1730).
async function twPersonHasDraftNote(c, personId) {
  const res = await twFetch(c, `/rest/noteTargets?filter=targetPersonId[eq]:${personId}&depth=1&limit=100`, { method: "GET" });
  if (!res || !res.ok) return null;
  const json = await res.json().catch(() => null);
  if (!json) return null;
  const targets = json.data?.noteTargets ?? [];
  return targets.some((t) => String(t?.note?.title || "").startsWith("Setter draft"));
}
async function twAttachDraftNote(c, personId, lead) {
  const md = [
    `Tier ${lead.tier} (score ${lead.score}) — ${lead.draft.template}`,
    `Hand-raise: ${lead.table}${lead.source ? ` (${lead.source})` : ""}`,
    lead.verdict?.why ? `ICP: ${lead.verdict.why}` : "",
    ``,
    `Subject: ${lead.draft.subject}`,
    ``,
    lead.draft.body,
    ``,
    `— DRAFT, not sent. Live send = owner GO.`,
  ].filter((x) => x !== undefined).join("\n");
  const res = await twFetch(c, "/rest/notes", { method: "POST", body: JSON.stringify({ title: `Setter draft — ${lead.tier}`, bodyV2: { markdown: md } }) });
  if (!res || !res.ok) return false;
  const json = await res.json().catch(() => null);
  const noteId = json?.data?.createNote?.id || json?.data?.id;
  if (!noteId) return false;
  await twFetch(c, "/rest/noteTargets", { method: "POST", body: JSON.stringify({ noteId, targetPersonId: personId }) });
  return true;
}
// Upsert one drafted lead. Returns {email, action}. Best-effort: a failure marks 'error',
// never throws. commit=false => compute the plan (find only), write nothing.
async function twUpsertLead(c, lead, commit) {
  try {
    const found = await twFindPerson(c, lead.email);
    if (found.status === "unknown") return { email: lead.email, action: "skip_unknown" };
    if (!commit) return { email: lead.email, action: found.id ? "would_update" : "would_create" };
    let personId = found.id || null;
    if (!personId) personId = await twCreatePerson(c, lead);
    if (!personId) return { email: lead.email, action: "error_no_person" };
    // tier is the sole responsibility of analytics scorer 422 (single source of truth) —
    // 395 NO LONGER PATCHes Person.tier here (avoids two writers racing the same field).
    // Note-idempotency (exactly-once notes): skip if a 'Setter draft' Note already exists for
    // this Person, so overlapping poller windows can't append a duplicate. Fail-open on a read
    // error (has === null) → create, since a missed draft is worse than a rare dup.
    const has = await twPersonHasDraftNote(c, personId);
    if (has === true) return { email: lead.email, action: found.id ? "updated" : "created", noted: false, noteSkipped: "exists" };
    const noted = await twAttachDraftNote(c, personId, lead);
    return { email: lead.email, action: found.id ? "updated" : "created", noted };
  } catch {
    return { email: lead.email, action: "error" };
  }
}

async function main() {
  const cfg = input();
  const tables = Array.isArray(cfg.tables) && cfg.tables.length ? cfg.tables : ["leads", "waitlist", "newsletter"];
  const perTable = Number(cfg.perTable) > 0 ? Number(cfg.perTable) : 200;
  const maxClassify = Number(cfg.maxClassify) > 0 ? Number(cfg.maxClassify) : 60;
  const model = cfg.model || "gpt-4o-mini";
  const bookUrl = cfg.bookUrl || "https://tsukumo.ch/book?utm_source=donna&utm_medium=outbound";
  // sinceMinutes (poller window) takes precedence over sinceDays (daily). null = full table.
  const sinceISO = Number(cfg.sinceMinutes) > 0
    ? new Date(Date.now() - Number(cfg.sinceMinutes) * 6e4).toISOString()
    : Number(cfg.sinceDays) > 0 ? new Date(Date.now() - Number(cfg.sinceDays) * 864e5).toISOString() : null;

  const c = sb();
  if (!c) { console.log(`::dokan:result::${JSON.stringify({ error: "no_supabase_secret" })}`); return; }

  // 1. read + normalize hand-raisers; dedup by email (keep the hottest surface seen)
  const byEmail = new Map();
  const SURFACE_RANK = { leads: 3, waitlist: 2, newsletter: 1 };
  for (const table of tables) {
    for (const row of await readTable(c, table, perTable, sinceISO)) {
      const lead = normalize(row, table);
      if (!lead.email || !lead.email.includes("@")) continue;
      const prev = byEmail.get(lead.email);
      // keep the row from the highest-intent surface; merge a couple of useful fields
      if (!prev || (SURFACE_RANK[table] || 0) > (SURFACE_RANK[prev.table] || 0)) {
        byEmail.set(lead.email, { ...(prev || {}), ...lead });
      } else {
        prev.company = prev.company || lead.company;
        prev.teamSize = prev.teamSize || lead.teamSize;
        prev.aiUse = prev.aiUse || lead.aiUse;
      }
    }
  }
  const all = [...byEmail.values()];

  // 2-4. classify the highest pre-signal first (cap LLM spend), score, tier
  const ranked = all
    .map((l) => ({ l, pre: (l.companyDomain ? 2 : 0) + (l.teamSize ? 2 : 0) + (l.aiUse ? 1 : 0) + (l.table === "leads" ? 2 : 0) }))
    .sort((a, b) => b.pre - a.pre);
  const leads = [];
  let classified = 0;
  for (const { l } of ranked) {
    let v = { fit: null, teamIntent: null, confidence: "low", why: "not_classified", model: null };
    if (classified < maxClassify) { v = await classify(l, model); classified++; }
    const { score, tier } = scoreAndTier(l, v);
    // Stage a setter DRAFT for the actionable tiers (A = owner-surface, B = donna-setter).
    // C = hold/nurture, no draft. Text only, nothing sends.
    const draft = tier === "A" || tier === "B" ? buildSetterDraft(l, bookUrl) : null;
    leads.push({ ...l, verdict: v, score, tier, draft });
  }
  leads.sort((a, b) => b.score - a.score);

  const counts = {
    handRaisers: all.length, classified,
    A: leads.filter((l) => l.tier === "A").length,
    B: leads.filter((l) => l.tier === "B").length,
    C: leads.filter((l) => l.tier === "C").length,
  };

  // PHASE 2b: upsert each drafted (A/B) lead into Twenty — Person (3-state dedup) + the
  // setter draft as a Note = donna's DRAFT-ONLY queue. commitTwenty=false (default) emits
  // the plan without writing; true writes Person+Note. NO SEND regardless: drafts only,
  // nothing is ever sent to the prospect (outreach is a separate human step).
  const commitTwenty = cfg.commitTwenty === true;
  const drafted = leads.filter((l) => l.draft);
  let twenty = { configured: false, commit: commitTwenty, attempted: 0, results: [] };
  const tc = twCfg();
  if (tc && drafted.length) {
    twenty.configured = true;
    twenty.attempted = drafted.length;
    for (const l of drafted) twenty.results.push(await twUpsertLead(tc, l, commitTwenty));
  } else if (tc) {
    twenty.configured = true; // no drafted leads this run (e.g. all tier C) — nothing to upsert
  }

  // sent:false is the hard invariant (no outreach path); committed reflects the Twenty CRM write.
  console.log(`::dokan:result::${JSON.stringify({ generated: new Date().toISOString(), sent: false, committed: commitTwenty, tables, model, counts, twenty, leads })}`);
}

main().catch((e) => console.log(`::dokan:result::${JSON.stringify({ error: String((e && e.message) || e) })}`));
