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

// pull every BODY copy string from a spec, each tagged with its field path (kicker/source excluded)
function copyFields(spec) {
  const out = [];
  const push = (path, v) => { if (typeof v === "string" && v.trim()) out.push({ path, v }); };
  const c = spec.cover || {};
  push("cover.title", c.title); push("cover.sub", c.sub);
  (spec.slides || []).forEach((s, i) => {
    const p = `slides[${i}]`;
    push(`${p}.title`, s.title); push(`${p}.body`, s.body);
    push(`${p}.heroValue`, s.heroValue); push(`${p}.heroLabel`, s.heroLabel);
    (s.items || []).forEach((it, j) => push(`${p}.items[${j}]`, it));
    (s.tiles || []).forEach((t, j) => { push(`${p}.tiles[${j}].value`, t.value); push(`${p}.tiles[${j}].label`, t.label); });
    (s.pairs || []).forEach((pr, j) => { push(`${p}.pairs[${j}].broke`, pr.broke); push(`${p}.pairs[${j}].fix`, pr.fix); });
    (s.data || []).forEach((d, j) => { push(`${p}.data[${j}].label`, d.label); push(`${p}.data[${j}].value`, d.value); });
  });
  const cta = spec.cta || {};
  push("cta.title", cta.title); push("cta.sub", cta.sub);
  return out;
}

let errors = 0, warns = 0;
const files = process.argv.slice(2).filter((a) => a.endsWith(".json"));
if (!files.length) { console.error("usage: lint_spec.mjs <spec.json> [...]"); process.exit(2); }

for (const file of files) {
  let spec;
  try { spec = JSON.parse(await readFile(file, "utf8")); }
  catch (e) { console.error(`✗ ${file}: invalid JSON — ${e.message}`); errors++; continue; }
  const slug = spec.slug || "(no slug)";
  const fields = copyFields(spec);
  const fileErrs = [];

  for (const { path, v } of fields) {
    if (DASH.test(v)) fileErrs.push(`${path}: em/en dash in body copy → de-dash (use ':' or '·'). «${v.match(/.{0,18}[—–].{0,18}/)[0].trim()}»`);
    for (const re of BANNED) if (re.test(v)) fileErrs.push(`${path}: banned phrase /${re.source}/ → ${re.source === "synergix" ? "remove" : "use public-beta / install + star"}. «${v.slice(0, 60)}»`);
  }
  // warns: overflow risk
  (spec.slides || []).forEach((s, i) => {
    if (s.heroValue && s.heroValue.length > 7) { console.warn(`⚠ ${slug} slides[${i}].heroValue "${s.heroValue}" is ${s.heroValue.length} chars — may clip at 230px`); warns++; }
  });
  const allTitles = [spec.cover?.title, ...(spec.slides || []).map((s) => s.title), spec.cta?.title].filter(Boolean);
  for (const t of allTitles) if (t.length > 52) { console.warn(`⚠ ${slug}: title "${t.slice(0,40)}…" is ${t.length} chars — shrinks small`); warns++; }

  if (fileErrs.length) { console.error(`✗ ${slug} (${file})`); fileErrs.forEach((e) => console.error(`    ${e}`)); errors += fileErrs.length; }
  else console.log(`✓ ${slug}`);
}

console.log(`\n${errors} error(s), ${warns} warning(s) across ${files.length} spec(s)`);
process.exit(errors ? 1 : 0);
