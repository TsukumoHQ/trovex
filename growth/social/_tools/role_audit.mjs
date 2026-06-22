#!/usr/bin/env node
// role_audit.mjs — DOKAN-ready. Audits a LIVE Metricool queue against the locked role ratio.
//
// 20/80: the deterministic 80% (classify + tally) runs free in a dokan container; the lead spends
// tokens only reading the verdict. No LLM, no network, pure function of the input.
//
// INPUT (dokan contract): env DOKAN_INPUT = JSON string, one of:
//   { "brand": "founder"|"company", "data": [ ...getScheduledPosts items... ] }
//   { "exports": [ {brand, data:[...]}, ... ] }   // audit both brands at once
// Locally you can also pipe the JSON as argv[2] or via DOKAN_INPUT.
//
// OUTPUT: per account per ISO-week role mix (reach/activation/convert) vs the LOCKED 60/30/10
// (brand-channel-direction v1.1, cmo chair-call #1), flagging weeks off-target (±15pp, n>=5).

const ROLE_TARGET = { reach: 60, activation: 30, convert: 10 };
const ROLE_TOL = 15;

// role classifier — heuristic on the strongest CTA present (hard sell wins).
// CONVERT: consulting booking (/assessment, /consulting, "book the assessment", "a straight read on your").
// ACTIVATION: product adoption (github.com/TsukumoHQ, trovex.dev root/install, "clone it", "three commands", "install").
// REACH: everything else (no link / /answers / /blog / /readiness / POV / study authority).
function classify(post) {
  const blob = [
    post.text || '',
    post.firstCommentText || '',
    ...(post.descendants || []).map((d) => d.text || ''),
  ].join(' \n ').toLowerCase();
  if (/\/assessment|\/consulting|book the assessment|a straight read on your|straight read on your setup/.test(blob)) return 'convert';
  if (/github\.com\/tsukumohq|trovex\.dev\/?(\?|#|\s|$)|clone it|three commands|uv tool install|trovex index/.test(blob)) return 'activation';
  return 'reach';
}

function brandOf(post, fallback) {
  const id = String(post.blogId || '');
  if (id === '6430128') return 'founder';
  if (id === '6430498') return 'company';
  return fallback || 'unknown';
}

function isoWeek(iso) {
  const d = new Date(iso.slice(0, 10) + 'T00:00:00Z');
  const day = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - day + 3);
  const firstThu = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
  const week = 1 + Math.round(((d - firstThu) / 86400000 - 3 + ((firstThu.getUTCDay() + 6) % 7)) / 7);
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

function readInput() {
  const raw = process.env.DOKAN_INPUT || process.argv[2];
  if (!raw) { console.error('no DOKAN_INPUT'); process.exit(2); }
  const j = JSON.parse(raw);
  if (Array.isArray(j.exports)) return j.exports;
  return [{ brand: j.brand, data: j.data || j.posts || [] }];
}

const exports_ = readInput();
const weeks = {}; // `${brand}|${week}` -> {reach,activation,convert,n}
for (const ex of exports_) {
  for (const post of ex.data || []) {
    if (post.draft) continue;
    const dt = post.publicationDate?.dateTime || post.date;
    if (!dt) continue;
    const brand = brandOf(post, ex.brand);
    const role = classify(post);
    const k = `${brand}|${isoWeek(dt)}`;
    (weeks[k] ||= { reach: 0, activation: 0, convert: 0, n: 0 });
    weeks[k][role]++; weeks[k].n++;
  }
}

let out = `ROLE AUDIT vs locked ${ROLE_TARGET.reach}/${ROLE_TARGET.activation}/${ROLE_TARGET.convert} (reach/activation/convert), ±${ROLE_TOL}pp:\n`;
const offWeeks = [];
for (const k of Object.keys(weeks).sort()) {
  const w = weeks[k];
  const pct = (r) => Math.round((w[r] / w.n) * 100);
  const off = ['reach', 'activation', 'convert'].filter((r) => Math.abs(pct(r) - ROLE_TARGET[r]) > ROLE_TOL);
  out += `  ${k}: ${pct('reach')}/${pct('activation')}/${pct('convert')} (n=${w.n})${off.length && w.n >= 5 ? '  ⚠ off: ' + off.join(',') : ''}\n`;
  if (off.length && w.n >= 5) offWeeks.push(k);
}
out += offWeeks.length ? `\nOFF-TARGET: ${offWeeks.join(', ')} — rebalance before they fire.\n` : '\nclean: every week on target.\n';
console.log(out);
process.exit(offWeeks.length ? 1 : 0);
