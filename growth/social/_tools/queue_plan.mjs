#!/usr/bin/env node
// queue_plan.mjs — deterministic Metricool queue planner (20/80 rule: the mechanical 80%).
//
// The AI lead writes the creative pool (angles + copy) and reviews the output.
// THIS SCRIPT does the mechanical part, free + reliable + no token burn:
//   - fills each day to the cadence FLOOR per brand/network
//   - assigns staggered slot times (no same-network-same-hour collision, vs plan AND the live queue)
//   - stamps UTM deterministically (mapped source, medium, campaign, content slug)
//   - builds carousel media URLs from a slug
//   - greps every string against the anti-slop ban-list
// It does NOT post. Output = plan.json (ready to schedule) + a summary + a violations report.
// Pushing to Metricool stays a reviewed step (so nothing fires unattended off a script bug).
//
// Usage: node queue_plan.mjs --from 2026-06-24 --days 3 [--queue queue-export.json] [--out plan.json]

import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const POOL = resolve(HERE, '../pool/posts.pool.json');
const MEDIA_BASE = 'https://bxdpevnqdnjcehewbiyg.supabase.co/storage/v1/object/public/media';

// --- config (mirrors memory social-cadence-daily v4 + social-format-priority) ---
const FLOOR = {
  founder: { twitter: 3, threads: 3, linkedin: 2 },
  company: { twitter: 2, threads: 1, linkedin: 1 },
};
const BLOG_ID = { founder: '6430128', company: '6430498' };
const PROPERTY = { founder: 'trovex', company: 'tsukumo' };
const SLOTS = {
  twitter: ['08:30', '10:00', '12:30', '15:00', '17:30', '20:00'],
  threads: ['09:00', '12:00', '16:00', '18:00', '20:30'],
  linkedin: ['09:00', '11:00', '14:00', '16:00'],
};
// utm_source must be a MAPPED value (analytics): x / linkedin known-good; threads may be unmapped → flagged.
const UTM_SOURCE = { twitter: 'x', linkedin: 'linkedin', threads: 'threads' };
const UNMAPPED_SOURCES = new Set(['threads']);

// anti-slop ban-list (the grep floor; the anti-ai-slop skill is the real gate on the creative side).
const BANNED = [
  'revolutionary', 'seamless', 'supercharge', 'unlock', 'ai-powered', 'game-changer',
  'cutting-edge', 'leverage', 'robust', 'streamline', 'elevate', 'comprehensive',
  'not just', 'not only', '~10x', "let's dive in", 'honest caveat', 'unpopular take',
];

// PORTFOLIO ROLE RATIO — brand-channel-direction v1.1, cmo chair-call #1 (LOCKED, revisit only w/ data).
// The ladder applies at the PORTFOLIO/week level, NOT per post. Each pool item carries a `role`.
// pre-launch ~0 audience → reach-heavy on purpose.
const ROLE_TARGET = { reach: 60, activation: 30, convert: 10 }; // % per account per ISO-week
const ROLE_TOL = 15; // pp deviation before it flags
// LINK-PLACEMENT per channel (v1.1 call #4): X=reply(descendant), LI=native/no-link (A/B the
// first-comment penalty), Threads=in-body. trovex surfaces ladder via ONE soft endplate link,
// NEVER a redirect/recanonical to tsukumo (geo cross-domain anti-dupe lock).

const args = parseArgs(process.argv.slice(2));
if (!args.from) die('need --from YYYY-MM-DD');
const DAYS = Number(args.days || 2);

const pool = JSON.parse(readFileSync(POOL, 'utf8'));
const liveQueue = args.queue ? JSON.parse(readFileSync(resolve(process.cwd(), args.queue), 'utf8')) : [];

// index what's already scheduled (from a Metricool export): brand|network|date → count + taken HH:mm
const taken = {};
for (const p of liveQueue) {
  const brand = blogToBrand(p.blogId || p.brand);
  const net = p.network || p.providers?.[0]?.network;
  const dt = p.publicationDate?.dateTime || p.date;
  if (!brand || !net || !dt) continue;
  const day = dt.slice(0, 10), hm = dt.slice(11, 16);
  const k = `${brand}|${net}|${day}`;
  (taken[k] ||= { count: 0, times: new Set() });
  taken[k].count++; taken[k].times.add(hm);
}

const used = new Set();
const plan = [];
const violations = [];
const gaps = [];

for (let d = 0; d < DAYS; d++) {
  const day = addDays(args.from, d);
  for (const brand of Object.keys(FLOOR)) {
    for (const net of Object.keys(FLOOR[brand])) {
      const k = `${brand}|${net}|${day}`;
      const already = taken[k]?.count || 0;
      const need = Math.max(0, FLOOR[brand][net] - already);
      if (need === 0) continue;
      const slotTimes = SLOTS[net].filter((t) => !(taken[k]?.times.has(t)));
      const picks = pickItems(pool, brand, net, need, used);
      if (picks.length < need) gaps.push(`${day} ${brand}/${net}: floor ${FLOOR[brand][net]}, have ${already}, pool filled ${picks.length}/${need} — SHORT`);
      picks.forEach((item, i) => {
        used.add(item.id);
        const time = slotTimes[i] || SLOTS[net][(already + i) % SLOTS[net].length];
        plan.push(buildSpec(item, brand, net, day, time, violations));
      });
    }
  }
}

writeFileSync(resolve(process.cwd(), args.out || 'plan.json'), JSON.stringify(plan, null, 2));
console.log(summary(plan, gaps, violations));
if (violations.length || gaps.length) process.exit(1);

// --- helpers ---
function pickItems(pool, brand, net, need, used) {
  const cand = pool.filter((p) => p.brand === brand && p.network === net && !used.has(p.id) && !p.retired);
  // round-robin by pillar so a day isn't monothematic (ENFP variety).
  const byPillar = {};
  for (const c of cand) (byPillar[c.pillar] ||= []).push(c);
  const order = Object.keys(byPillar);
  const out = [];
  let i = 0;
  while (out.length < need && order.some((p) => byPillar[p].length)) {
    const bucket = byPillar[order[i % order.length]];
    if (bucket.length) out.push(bucket.shift());
    i++;
  }
  return out;
}

function buildSpec(item, brand, net, day, time, violations) {
  const link = item.link ? stampUtm(item.link, net, item.utmCampaign, item.utmContentSlug, violations, item.id) : null;
  const media = item.carouselSlug
    ? cardUrls(PROPERTY[brand], item.carouselSlug, item.cards)
    : (item.media || []);
  const text = net === 'linkedin' ? item.text : injectLink(item, link);
  const spec = {
    id: item.id, brand, blogId: BLOG_ID[brand], network: net, pillar: item.pillar, role: item.role || 'reach',
    date: `${day}T${time}:00`, timezone: 'Europe/Zurich',
    text: item.text,
    media,
    firstCommentText: net === 'linkedin' ? (item.firstComment ? stampFirstComment(item, link) : '') : '',
    descendants: net === 'linkedin' ? undefined : (link ? [linkReply(link)] : item.descendants),
  };
  scanSlop([item.text, ...(item.descendants || []), item.firstComment || ''], item.id, violations);
  if (net === 'linkedin' && (!media || !media.length)) violations.push(`${item.id}: linkedin post with NO visual (format-priority: LI always visual)`);
  return spec;
}

function stampUtm(url, net, campaign, slug, violations, id) {
  const src = UTM_SOURCE[net];
  if (UNMAPPED_SOURCES.has(src)) violations.push(`${id}: utm_source='${src}' may be UNMAPPED in analytics — confirm`);
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}utm_source=${src}&utm_medium=social&utm_campaign=${campaign || 'public-beta'}&utm_content=${slug || id}`;
}
function cardUrls(prop, slug, cards = 3) {
  const n = cards;
  const names = ['portrait-00-cover'];
  for (let i = 1; i < n - 1; i++) names.push(`portrait-0${i}-slide`);
  names.push(`portrait-0${n - 1}-cta`);
  return names.map((v) => `${MEDIA_BASE}/${prop}/carousel/${slug}/${v}.png`);
}
function linkReply(link) { return { text: link, providers: [{ network: 'twitter' }], twitterData: { tags: [] } }; }
function injectLink() { return undefined; } // X/Threads keep link in a reply, not body
function stampFirstComment(item, link) { return item.firstComment.replace('{{link}}', link || ''); }

function scanSlop(strings, id, violations) {
  const hay = strings.join(' \n ').toLowerCase();
  for (const w of BANNED) if (hay.includes(w)) violations.push(`${id}: anti-slop banned term "${w}"`);
  const em = (strings.join('').match(/—/g) || []).length;
  if (em > strings.length) violations.push(`${id}: em-dash overuse (${em})`);
}

function summary(plan, gaps, violations) {
  const tally = {};
  for (const s of plan) { const k = `${s.date.slice(0, 10)} ${s.brand}/${s.network}`; tally[k] = (tally[k] || 0) + 1; }
  let out = `\nPLAN: ${plan.length} posts\n`;
  for (const k of Object.keys(tally).sort()) out += `  ${k}: +${tally[k]}\n`;

  // role ratio per account per ISO-week (LOCKED 60/30/10; this plan's additions only — caveat below).
  const byWeek = {};
  for (const s of plan) {
    const k = `${s.brand}|${isoWeek(s.date.slice(0, 10))}`;
    (byWeek[k] ||= { reach: 0, activation: 0, convert: 0, n: 0 });
    byWeek[k][s.role] = (byWeek[k][s.role] || 0) + 1; byWeek[k].n++;
  }
  out += `\nROLE MIX (target ${ROLE_TARGET.reach}/${ROLE_TARGET.activation}/${ROLE_TARGET.convert} reach/activation/convert, ±${ROLE_TOL}pp; planned adds only):\n`;
  for (const k of Object.keys(byWeek).sort()) {
    const w = byWeek[k];
    const pct = (r) => Math.round((w[r] / w.n) * 100);
    const line = `${k}: ${pct('reach')}/${pct('activation')}/${pct('convert')} (n=${w.n})`;
    const off = ['reach', 'activation', 'convert'].filter((r) => Math.abs(pct(r) - ROLE_TARGET[r]) > ROLE_TOL);
    out += `  ${line}${off.length ? '  ⚠ off: ' + off.join(',') : ''}\n`;
    if (off.length && w.n >= 5) violations.push(`${k}: role mix ${pct('reach')}/${pct('activation')}/${pct('convert')} off target on ${off.join(',')} (ladder up at PORTFOLIO level)`);
  }

  if (gaps.length) out += `\nFLOOR GAPS (pool short — write more angles):\n  ${gaps.join('\n  ')}\n`;
  if (violations.length) out += `\nVIOLATIONS (fix before scheduling):\n  ${violations.join('\n  ')}\n`;
  if (!gaps.length && !violations.length) out += '\nclean: floor met, role mix on target, no violations.\n';
  return out;
}

function isoWeek(iso) {
  const d = new Date(iso + 'T00:00:00Z');
  const day = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - day + 3);
  const firstThu = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
  const week = 1 + Math.round(((d - firstThu) / 86400000 - 3 + ((firstThu.getUTCDay() + 6) % 7)) / 7);
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

function parseArgs(a) { const o = {}; for (let i = 0; i < a.length; i++) if (a[i].startsWith('--')) o[a[i].slice(2)] = a[i + 1]?.startsWith('--') || a[i + 1] === undefined ? true : a[++i]; return o; }
function addDays(iso, n) { const d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
function blogToBrand(v) { if (v === '6430128' || v === 'founder') return 'founder'; if (v === '6430498' || v === 'company') return 'company'; return null; }
function die(m) { console.error('error: ' + m); process.exit(2); }
