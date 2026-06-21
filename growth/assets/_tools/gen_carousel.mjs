// gen_carousel.mjs — render a carousel spec (growth/social/carousels/<slug>.json) to
// portrait (LinkedIn 1080x1350) + square (X 1080x1080) PNG slides, then upload each to
// Supabase storage (bucket `media`, kind:carousel) and index it in public.media_assets.
//
// House stack: satori + @resvg/resvg-js, Fira fonts, trovex/tsukumo terminal-restraint
// brand — flat stage #06080d, green #22c55e, lowercase wordmark. Typographic only (NO
// gpt-image text → no garble). Mirrors growth/assets/launch/trovex/_gen.mjs.
//
// Honesty: renders the spec verbatim. Numbers are the spec's attributed study figures /
// the first-party ~60%. No fabricated metrics, logos, testimonials. No Synergix.
//
// Audience drives brand + CTA: company → tsukumo wordmark + tsukumo.ch/assessment;
// founder → trovex wordmark + trovex.dev. Each spec sets cta.foot explicitly.
//
// Deps: satori + @resvg/resvg-js must resolve (symlink a node_modules up-tree, e.g.
//   ln -s <a-web-worktree>/node_modules ./node_modules   — transient, never commit it).
// Creds (upload): ~/.config/trovex-growth/supabase.env (SUPABASE_URL + SERVICE_ROLE_KEY).
//   set -a; . ~/.config/trovex-growth/supabase.env; set +a   — never print/commit.
//
// Usage:
//   node growth/assets/_tools/gen_carousel.mjs growth/social/carousels/study-metr-slower.json
//   node growth/assets/_tools/gen_carousel.mjs growth/social/carousels/*.json   # batch
//   flags: --no-upload (render only)  --out <dir> (also write PNGs locally for review)
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import { basename, dirname, join } from "node:path";

const F = join(homedir(), "Library", "Fonts");
const fonts = [
  { name: "Fira Sans", data: await readFile(join(F, "FiraSans-Bold.otf")), weight: 700, style: "normal" },
  { name: "Fira Code", data: await readFile(join(F, "FiraCode-Regular.ttf")), weight: 400, style: "normal" },
];
const C = { stage: "#06080d", card: "#11151f", border: "#222a39", fg: "#e6edf3", muted: "#9aa6b8", subtle: "#74808f", faint: "#5a6577", accent: "#22c55e" };
const h = (t, p, ...k) => ({ type: t, props: { ...p, children: k.length <= 1 ? k[0] : k } });

const SHAPES = {
  portrait: { w: 1080, h: 1350, pad: 88, kicker: 21, counter: 20, sub: 27, foot: 34, mark: 30 },
  square: { w: 1080, h: 1080, pad: 84, kicker: 20, counter: 19, sub: 25, foot: 32, mark: 28 },
};

const brandFor = (audience) => (audience === "founder" ? "trovex" : "tsukumo");
const propertyFor = (audience) => (audience === "founder" ? "trovex" : "tsukumo");

function wordmark(word, fs) {
  return h("div", { style: { display: "flex", alignItems: "center", gap: "12px", fontFamily: "Fira Code", fontSize: `${fs}px`, color: C.fg } },
    h("div", { style: { width: `${Math.round(fs * 0.6)}px`, height: `${Math.round(fs * 0.6)}px`, backgroundColor: C.accent } }), h("span", {}, word));
}
const label = (s, fs) => h("div", { style: { fontFamily: "Fira Code", fontSize: `${fs}px`, color: C.subtle, letterSpacing: "0.16em", textTransform: "uppercase" } }, s);

// title with the accent substring colored green; word-level spans so it wraps cleanly
function titleEl(full, accent, fs) {
  const idx = accent ? full.indexOf(accent) : -1;
  const segs = idx === -1
    ? [{ t: full, a: false }]
    : [{ t: full.slice(0, idx), a: false }, { t: accent, a: true }, { t: full.slice(idx + accent.length), a: false }];
  const words = [];
  for (const s of segs) for (const w of s.t.split(" ")) { if (w === "") continue; words.push({ w, a: s.a }); }
  return h("div", { style: { display: "flex", flexWrap: "wrap", fontFamily: "Fira Sans", fontWeight: 700, fontSize: `${fs}px`, lineHeight: 1.07, letterSpacing: "-0.02em" } },
    ...words.map(({ w, a }) => h("span", { style: { color: a ? C.accent : C.fg, marginRight: "0.26em" } }, w)));
}
const muted = (s, fs, color = C.muted) => h("div", { style: { fontFamily: "Fira Sans", fontWeight: 400, fontSize: `${fs}px`, lineHeight: 1.34, color, maxWidth: "900px" } }, s);

function frame(S, kids, footer) {
  return h("div", { style: { width: `${S.w}px`, height: `${S.h}px`, display: "flex", flexDirection: "column", backgroundColor: C.stage, color: C.fg, padding: `${S.pad}px`, fontFamily: "Fira Sans", position: "relative" } },
    h("div", { style: { position: "absolute", top: 0, left: 0, width: "100%", height: "6px", backgroundColor: C.accent } }),
    h("div", { style: { display: "flex", flexDirection: "column", flex: 1, justifyContent: "space-between" } }, ...kids, footer));
}

// title font size scaled to length so long headlines still fit
const tfs = (S, str) => {
  const base = S.h === 1350 ? 86 : 78;
  if (str.length > 34) return base - 22;
  if (str.length > 24) return base - 12;
  return base;
};

function coverCard(spec, S) {
  const word = brandFor(spec.audience);
  return frame(S, [
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, wordmark(word, S.mark), label(spec.kicker, S.kicker)),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "30px", flex: 1, justifyContent: "center" } },
      titleEl(spec.cover.title, spec.cover.accent, tfs(S, spec.cover.title)),
      muted(spec.cover.sub, S.sub)),
  ], h("div", { style: { display: "flex", justifyContent: "flex-end", fontFamily: "Fira Code", fontSize: `${S.counter}px`, color: C.subtle, letterSpacing: "0.12em" } }, "swipe →"));
}

function slideCard(spec, slide, idx, total, S) {
  const word = brandFor(spec.audience);
  const counter = `${String(idx).padStart(2, "0")} / ${String(total).padStart(2, "0")}`;
  return frame(S, [
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, label(spec.kicker, S.kicker), h("div", { style: { fontFamily: "Fira Code", fontSize: `${S.counter}px`, color: C.accent, letterSpacing: "0.12em" } }, counter)),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "28px", flex: 1, justifyContent: "center" } },
      titleEl(slide.title, slide.accent, tfs(S, slide.title)),
      muted(slide.body, S.sub)),
  ], wordmark(word, S.mark));
}

function ctaCard(spec, S) {
  const word = brandFor(spec.audience);
  return frame(S, [
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, wordmark(word, S.mark), label("your move", S.kicker)),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "28px", flex: 1, justifyContent: "center" } },
      titleEl(spec.cta.title, spec.cta.accent, tfs(S, spec.cta.title)),
      muted(spec.cta.sub, S.sub)),
  ], h("div", { style: { display: "flex", alignItems: "center", gap: "16px", fontFamily: "Fira Code", fontSize: `${S.foot}px`, color: C.accent, borderTop: `1px solid ${C.border}`, paddingTop: "26px" } },
    h("div", { style: { width: "14px", height: "14px", backgroundColor: C.accent } }), h("span", {}, spec.cta.foot)));
}

function cardsFor(spec) {
  const total = 1 + spec.slides.length + 1; // cover + slides + cta
  const out = [{ name: "00-cover", el: (S) => coverCard(spec, S) }];
  spec.slides.forEach((sl, i) => {
    out.push({ name: `${String(i + 1).padStart(2, "0")}-slide`, el: (S) => slideCard(spec, sl, i + 1, spec.slides.length, S) });
  });
  out.push({ name: `${String(spec.slides.length + 1).padStart(2, "0")}-cta`, el: (S) => ctaCard(spec, S) });
  return out;
}

async function render(el, S) {
  const svg = await satori(el, { width: S.w, height: S.h, fonts });
  return new Resvg(svg, { fitTo: { mode: "width", value: S.w } }).render().asPng();
}

// ---- Supabase upload ----
const SB_URL = process.env.SUPABASE_URL;
const SB_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
async function upload(property, kind, slug, variant, path, png, w, hgt, title, tags) {
  const objUrl = `${SB_URL}/storage/v1/object/media/${path}`;
  const r1 = await fetch(objUrl, { method: "POST", headers: { Authorization: `Bearer ${SB_KEY}`, apikey: SB_KEY, "Content-Type": "image/png", "x-upsert": "true" }, body: png });
  if (!r1.ok && r1.status !== 200) throw new Error(`storage ${r1.status} ${await r1.text()}`);
  const publicUrl = `${SB_URL}/storage/v1/object/public/media/${path}`;
  const row = { property, kind, slug, variant, path, url: publicUrl, width: w, height: hgt, title, tags, generator: "gen_carousel.mjs" };
  const r2 = await fetch(`${SB_URL}/rest/v1/media_assets?on_conflict=property,kind,slug,variant`, {
    method: "POST",
    headers: { Authorization: `Bearer ${SB_KEY}`, apikey: SB_KEY, "Content-Type": "application/json", Prefer: "resolution=merge-duplicates,return=minimal" },
    body: JSON.stringify(row),
  });
  if (!r2.ok) throw new Error(`index ${r2.status} ${await r2.text()}`);
  return publicUrl;
}

// ---- main ----
const args = process.argv.slice(2);
const noUpload = args.includes("--no-upload");
const outIdx = args.indexOf("--out");
const outDir = outIdx !== -1 ? args[outIdx + 1] : null;
const specFiles = args.filter((a, i) => a.endsWith(".json") && (outIdx === -1 || i !== outIdx + 1));
if (!specFiles.length) { console.error("no spec .json given"); process.exit(1); }
if (!noUpload && (!SB_URL || !SB_KEY)) { console.error("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not in env — source supabase.env or pass --no-upload"); process.exit(1); }

for (const file of specFiles) {
  const spec = JSON.parse(await readFile(file, "utf8"));
  const property = propertyFor(spec.audience);
  const cards = cardsFor(spec);
  if (outDir) await mkdir(join(outDir, spec.slug), { recursive: true });
  const urls = [];
  for (const card of cards) {
    for (const shapeName of ["portrait", "square"]) {
      const S = SHAPES[shapeName];
      const png = await render(card.el(S), S);
      const variant = `${shapeName}-${card.name}`;
      const path = `${property}/carousel/${spec.slug}/${variant}.png`;
      if (outDir) await writeFile(join(outDir, spec.slug, `${variant}.png`), png);
      if (!noUpload) {
        const url = await upload(property, "carousel", spec.slug, variant, path, png, S.w, S.h, spec.kicker, ["carousel", spec.audience, spec.slug]);
        urls.push(url);
      }
    }
  }
  console.log(`✓ ${spec.slug} (${spec.audience}) — ${cards.length} slides ×2 shapes = ${cards.length * 2} PNG${noUpload ? " (render-only)" : ", uploaded"}`);
  if (urls.length) console.log(`  base: ${SB_URL}/storage/v1/object/public/media/${property}/carousel/${spec.slug}/`);
}
console.log("DONE");
