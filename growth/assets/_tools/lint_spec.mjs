// lint_spec.mjs — deterministic preflight for carousel specs (20/80 rule). Enforces the
// brand-copy rules I otherwise hand-check every render, so a bad spec fails BEFORE it
// renders + uploads. Pure Node (no satori/resvg) — runs without the node_modules symlink.
//
// HARD errors (exit 1):
//   · em/en dash in BODY copy — the gen only de-dashes the eyebrow (kicker); every other
//     copy field renders raw, so a dash there ships a literal '—'. (memory: de-em-dash card copy)
//   · banned positioning phrases — we're PUBLIC beta (memory social-positioning-and-queue-regime)
//   · 'Synergix' anywhere (brand rule, no-synergix-mention)
// WARN (exit 0): overflow risk — long heroValue / long title shrink or clip.
//
// Eyebrow (kicker) + footer (source) are EXCLUDED from the dash check: the gen runs them
// through deMood()/`source:` so a dash there is fine and idiomatic.
//
// Usage:  node growth/assets/_tools/lint_spec.mjs growth/social/carousels/<slug>.json [...]
//         node growth/assets/_tools/lint_spec.mjs growth/social/carousels/*.json
import { readFile } from "node:fs/promises";

const DASH = /[—–]/;
const BANNED = [/private beta/i, /request access/i, /request beta access/i, /beta-waitlist/i, /#waitlist/i, /synergix/i];

// claim/honesty gate (sixty-percent-public-claim-standard + voice). The ~60% figure is
// MODELED; 'measured' is public ONLY once trovex.dev/method ships the signed disclosures
// (TSU-58) — until then any 'measured' on OUR surface is unbacked. EXTERNAL studies
// (METR/DORA/GitClear/Stanford/Apple/ETH/Veracode/arXiv) legitimately say 'measured' about
// THEIR result, so study-tagged fields are exempt from the measured/74% rules.
const STUDY = /arxiv|\bmetr\b|\bdora\b|gitclear|stanford|\bapple\b|\beth\b|veracode|slopcode|the research/i;
const CLAIM = [
  // [regex, study-exempt?, message]
  [/\bmeasured\b/i, true,  "our-claim 'measured' is unbacked until /method discloses → use 'modeled' (study numbers are exempt)"],
  [/~?\s*74\s*%/,    true,  "74% is the cherry-picked max, never the headline → lead with ~60% modeled median + range ~38-79%"],
  [/\bsame answers?\b/i, false, "unbacked answer-parity claim → drop 'same answer(s)'; keep only the token claim"],
  [/\bai[- ]powered\b/i, false, "banned hype term 'AI-powered' (voice) → name the mechanism"],
  [/\b(Trovex|Tsukumo|Wraith|Yoru|Dokan)\b/, false, "wordmark must be lowercase (TsukumoHQ org id excepted)"],
];
const TSUKUMO_HQ = /TsukumoHQ/; // GitHub org identifier — legit, not a wordmark violation

// pull every BODY copy string from a spec, each tagged with its field path (kicker/source excluded)
function copyFields(spec) {
  const out = [];
  const base = STUDY.test(`${spec.kicker || ""} ${spec.source || ""}`);
  const push = (path, v, study) => { if (typeof v === "string" && v.trim()) out.push({ path, v, study }); };
  const c = spec.cover || {};
  push("cover.title", c.title, base); push("cover.sub", c.sub, base);
  (spec.slides || []).forEach((s, i) => {
    const p = `slides[${i}]`;
    const st = base || STUDY.test(`${s.source || ""} ${s.title || ""}`);
    push(`${p}.title`, s.title, st); push(`${p}.body`, s.body, st);
    push(`${p}.heroValue`, s.heroValue, st); push(`${p}.heroLabel`, s.heroLabel, st);
    (s.items || []).forEach((it, j) => push(`${p}.items[${j}]`, it, st));
    (s.tiles || []).forEach((t, j) => { push(`${p}.tiles[${j}].value`, t.value, st); push(`${p}.tiles[${j}].label`, t.label, st); });
    (s.pairs || []).forEach((pr, j) => { push(`${p}.pairs[${j}].broke`, pr.broke, st); push(`${p}.pairs[${j}].fix`, pr.fix, st); });
    (s.data || []).forEach((d, j) => { push(`${p}.data[${j}].label`, d.label, st); push(`${p}.data[${j}].value`, d.value, st); });
  });
  const cta = spec.cta || {};
  push("cta.title", cta.title, base); push("cta.sub", cta.sub, base);
  return out;
}

// card specs (gen_card.mjs) = a JSON ARRAY of single cards. gen_card auto-de-dashes ALL
// copy, so the dash check is moot here — but banned positioning + Synergix are NOT
// auto-fixed, so those still MUST be caught before an auto-posted card ships.
function cardFields(cards) {
  const out = [];
  cards.forEach((c, i) => {
    const p = `card[${i}:${c.uuid ?? "?"}]`;
    const st = STUDY.test(`${c.source || ""} ${c.kicker || ""}`);
    const push = (path, v) => { if (typeof v === "string" && v.trim()) out.push({ path, v, study: st }); };
    push(`${p}.headline`, c.headline); push(`${p}.sub`, c.sub);
    push(`${p}.heroValue`, c.heroValue); push(`${p}.heroLabel`, c.heroLabel);
    (c.cols || []).forEach((col, j) => { push(`${p}.cols[${j}].head`, col.head); push(`${p}.cols[${j}].body`, col.body); });
    (c.data || []).forEach((d, j) => { push(`${p}.data[${j}].label`, d.label); push(`${p}.data[${j}].value`, d.value); });
    (c.lines || []).forEach((l, j) => { push(`${p}.lines[${j}].k`, l.k); push(`${p}.lines[${j}].v`, l.v); });
    (c.items || []).forEach((it, j) => { push(`${p}.items[${j}].t`, it.t); push(`${p}.items[${j}].note`, it.note); });
    if (c.before) { push(`${p}.before.label`, c.before.label); push(`${p}.before.value`, c.before.value); }
    if (c.after) { push(`${p}.after.label`, c.after.label); push(`${p}.after.value`, c.after.value); }
    push(`${p}.totalK`, c.totalK); push(`${p}.totalV`, c.totalV);
  });
  return out;
}

let errors = 0, warns = 0;
const files = process.argv.slice(2).filter((a) => a.endsWith(".json"));
if (!files.length) { console.error("usage: lint_spec.mjs <spec.json> [...]"); process.exit(2); }

for (const file of files) {
  let spec;
  try { spec = JSON.parse(await readFile(file, "utf8")); }
  catch (e) { console.error(`✗ ${file}: invalid JSON — ${e.message}`); errors++; continue; }
  const isCards = Array.isArray(spec); // card-spec file = array of single cards (gen_card.mjs)
  const slug = isCards ? `${spec.length} cards` : (spec.slug || "(no slug)");
  const fields = isCards ? cardFields(spec) : copyFields(spec);
  const fileErrs = [];

  for (const { path, v, study } of fields) {
    // dash is a HARD error only for carousels (gen_carousel renders body raw); gen_card auto-de-dashes
    if (!isCards && DASH.test(v)) fileErrs.push(`${path}: em/en dash in body copy → de-dash (use ':' or '·'). «${v.match(/.{0,18}[—–].{0,18}/)[0].trim()}»`);
    for (const re of BANNED) if (re.test(v)) fileErrs.push(`${path}: banned phrase /${re.source}/ → ${re.source === "synergix" ? "remove" : "use public-beta / install + star"}. «${v.slice(0, 60)}»`);
    // honesty/claim gate — study-tagged fields exempt where noted (external measurements are
    // real). A field that NAMES a study inline ("Stanford measured 35-40%") is exempt too.
    const fieldStudy = study || STUDY.test(v);
    for (const [re, studyExempt, msg] of CLAIM) {
      if (studyExempt && fieldStudy) continue;
      const target = re === CLAIM[4][0] ? v.replace(TSUKUMO_HQ, "") : v; // org id isn't a wordmark violation
      if (re.test(target)) fileErrs.push(`${path}: ${msg}. «${v.slice(0, 60)}»`);
    }
  }
  // warns: overflow risk (carousel-shaped only)
  (isCards ? [] : spec.slides || []).forEach((s, i) => {
    if (s.heroValue && s.heroValue.length > 7) { console.warn(`⚠ ${slug} slides[${i}].heroValue "${s.heroValue}" is ${s.heroValue.length} chars — may clip at 230px`); warns++; }
  });
  const allTitles = [spec.cover?.title, ...(spec.slides || []).map((s) => s.title), spec.cta?.title].filter(Boolean);
  for (const t of allTitles) if (t.length > 52) { console.warn(`⚠ ${slug}: title "${t.slice(0,40)}…" is ${t.length} chars — shrinks small`); warns++; }

  if (fileErrs.length) { console.error(`✗ ${slug} (${file})`); fileErrs.forEach((e) => console.error(`    ${e}`)); errors += fileErrs.length; }
  else console.log(`✓ ${slug}`);
}

console.log(`\n${errors} error(s), ${warns} warning(s) across ${files.length} spec(s)`);
process.exit(errors ? 1 : 0);
