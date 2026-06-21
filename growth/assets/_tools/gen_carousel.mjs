// gen_carousel.mjs — render a carousel spec (growth/social/carousels/<slug>.json) to
// portrait (LinkedIn 1080x1350) + square (X 1080x1080) PNG slides, upload to Supabase
// storage (bucket `media`, kind:carousel) and index in public.media_assets.
//
// VISUAL SYSTEM = owner-approved 'data-editorial' (memory visual-system-locked). The
// headline carries the real CLAIM; the number IS the design (delta bars when a slide
// ships `data`); palette goes beyond green-on-black (signal red for findings, green
// reserved for trovex wins). NO slide counters, NO all-caps mood labels, NO empty
// canvas. Display = Archivo (static, repo _fonts); body = Fira Sans; data/eyebrow = Fira
// Code. Tone by audience: company/evidence leans red, founder/product leans green.
//
// Honesty: renders the spec verbatim (attributed study figures + first-party ~60%). No
// fabricated metrics/logos/testimonials, no Synergix.
//
// Deps: satori + @resvg/resvg-js must resolve (symlink a node_modules up-tree; never commit it).
// Creds (upload): ~/.config/trovex-growth/supabase.env (SUPABASE_URL + SERVICE_ROLE_KEY).
//   set -a; . ~/.config/trovex-growth/supabase.env; set +a
//
// Usage:
//   node growth/assets/_tools/gen_carousel.mjs growth/social/carousels/study-metr-slower.json
//   node growth/assets/_tools/gen_carousel.mjs growth/social/carousels/*.json   # batch
//   flags: --no-upload (render only)  --out <dir> (also write PNGs locally for review)
//
// Optional spec fields for the chart treatment (per cover/slide):
//   "data": [ { "label": "measured, with AI", "value": "-19%", "pct": 48, "tone": "red" }, ... ]
//   tone ∈ red | redGhost | green | soft   ·   "source": "METR, n=16, 246 tasks" (footer citation)
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SYS = join(homedir(), "Library", "Fonts");
const REPOFONT = join(HERE, "..", "_fonts");
const fonts = [
  { name: "Archivo", data: await readFile(join(REPOFONT, "Archivo-800.ttf")), weight: 800, style: "normal" },
  { name: "Archivo", data: await readFile(join(REPOFONT, "Archivo-600.ttf")), weight: 600, style: "normal" },
  { name: "Fira Sans", data: await readFile(join(SYS, "FiraSans-Medium.otf")), weight: 500, style: "normal" },
  { name: "Fira Code", data: await readFile(join(SYS, "FiraCode-Regular.ttf")), weight: 400, style: "normal" },
];
const C = { bg:"#0c0d10", panel:"#101216", ink:"#f3f0e9", soft:"#8b8f98", faint:"#5f636b", rule:"#23262d", track:"#181a1f", green:"#22c55e" };
// AUTO-POST = GREEN uniformly (owner-locked autopost-green-antislop). Red dropped:
// legacy tones red/redGhost map to green / muted-soft so old data blocks stay valid.
const TONE = { red:C.green, redGhost:C.soft, green:C.green, soft:C.soft, ink:C.ink };
// faint dot-grid texture on the dark canvas (teardown refinement #2: kills the flat-void feel, Linear-style restraint)
const DOT = `data:image/svg+xml;base64,${Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44"><circle cx="2" cy="2" r="1.3" fill="#ffffff" fill-opacity="0.028"/></svg>').toString("base64")}`;
const h = (t, p, ...k) => ({ type: t, props: { ...p, children: k.length <= 1 ? k[0] : k } });

const SHAPES = {
  portrait: { w:1080, h:1350, pad:84, eb:20, sub:30, foot:20, mark:26, big:104 },
  square:   { w:1080, h:1080, pad:80, eb:19, sub:27, foot:19, mark:25, big:88 },
};
const brandFor = (a) => (a === "founder" ? "trovex" : "tsukumo");
const propertyFor = (a) => (a === "founder" ? "trovex" : "tsukumo");
const accentFor = () => C.green; // GREEN for all auto-post (owner-locked). violet stays only on the wrai.th SITE (gen_brand_gallery), never auto-post.
const deMood = (s) => (s || "").replace(/\s*[—–-]\s*/g, " · "); // kill em-dash mood-dash in eyebrows

function wordmark(word, fs) {
  return h("div",{style:{display:"flex",alignItems:"center",gap:"11px",fontFamily:"Fira Code",fontSize:`${fs}px`,color:C.ink}},
    h("div",{style:{width:`${Math.round(fs*0.62)}px`,height:`${Math.round(fs*0.62)}px`,backgroundColor:C.green}}), h("span",{},word));
}
const eyebrow = (s,fs) => h("div",{style:{fontFamily:"Fira Code",fontSize:`${fs}px`,color:C.soft,letterSpacing:"0.03em"}}, deMood(s));

// headline: accent substring colored; word-level spans wrap cleanly; Archivo display
function titleEl(full, accent, fs, accentColor) {
  const idx = accent ? full.indexOf(accent) : -1;
  const segs = idx === -1 ? [{t:full,a:false}]
    : [{t:full.slice(0,idx),a:false},{t:accent,a:true},{t:full.slice(idx+accent.length),a:false}];
  const words = [];
  for (const s of segs) for (const w of s.t.split(" ")) { if (w==="") continue; words.push({w,a:s.a}); }
  return h("div",{style:{display:"flex",flexWrap:"wrap",fontFamily:"Archivo",fontWeight:800,fontSize:`${fs}px`,lineHeight:0.98,letterSpacing:"-0.035em"}},
    ...words.map(({w,a}) => h("span",{style:{color:a?accentColor:C.ink,marginRight:"0.24em"}}, w)));
}
const body = (s,fs) => h("div",{style:{fontFamily:"Fira Sans",fontWeight:500,fontSize:`${fs}px`,lineHeight:1.4,color:C.soft,maxWidth:"880px"}}, s);

function bars(data) {
  return h("div",{style:{display:"flex",flexDirection:"column",gap:"22px"}},
    ...data.map(d => h("div",{style:{display:"flex",flexDirection:"column",gap:"9px"}},
      h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"baseline"}},
        h("div",{style:{fontFamily:"Fira Code",fontSize:"20px",color:C.soft}}, d.label),
        h("div",{style:{fontFamily:"Archivo",fontWeight:800,fontSize:"30px",color:TONE[d.tone]||C.ink,letterSpacing:"-0.02em"}}, d.value)),
      h("div",{style:{display:"flex",height:"26px",backgroundColor:C.track,borderRadius:"2px"}},
        h("div",{style:{width:`${Math.max(3,Math.min(100,d.pct))}%`,backgroundColor:TONE[d.tone]||C.soft,borderRadius:"2px"}})))));
}

// ---- BIP layouts (owner build-in-public lane). Set spec.layout + per-slide fields. ----
// stat-tiles: slide.tiles=[{value,label}]  ·  changelog: slide.items=["…"]  ·  before-after: slide.pairs=[{broke,fix}]
function tilesEl(tiles) {
  return h("div",{style:{display:"flex",flexWrap:"wrap",gap:"20px"}},
    ...tiles.map(t => h("div",{style:{display:"flex",flexDirection:"column",gap:"6px",width:"calc(50% - 10px)",border:`1px solid ${C.rule}`,backgroundColor:C.panel,borderRadius:"12px",padding:"26px 28px"}},
      h("div",{style:{fontFamily:"Archivo",fontWeight:800,fontSize:"58px",color:C.green,letterSpacing:"-0.03em",lineHeight:1}}, t.value),
      h("div",{style:{fontFamily:"Fira Code",fontSize:"20px",color:C.soft}}, t.label))));
}
function changelogEl(items) {
  return h("div",{style:{display:"flex",flexDirection:"column",gap:"18px"}},
    ...items.map(it => h("div",{style:{display:"flex",alignItems:"flex-start",gap:"18px"}},
      h("div",{style:{width:"14px",height:"14px",backgroundColor:C.green,marginTop:"10px",flexShrink:0}}),
      h("div",{style:{fontFamily:"Fira Sans",fontWeight:500,fontSize:"33px",color:C.ink,lineHeight:1.25}}, it))));
}
function pairsEl(pairs) {
  return h("div",{style:{display:"flex",flexDirection:"column",gap:"24px"}},
    ...pairs.map(p => h("div",{style:{display:"flex",alignItems:"stretch",gap:"22px"}},
      h("div",{style:{display:"flex",flexDirection:"column",gap:"8px",flex:1,border:`1px solid ${C.rule}`,backgroundColor:C.panel,borderRadius:"10px",padding:"22px 24px"}},
        h("div",{style:{fontFamily:"Fira Code",fontSize:"18px",color:C.soft}},"broke"), h("div",{style:{fontFamily:"Fira Sans",fontWeight:500,fontSize:"25px",color:C.soft}}, p.broke)),
      h("div",{style:{display:"flex",alignItems:"center",color:C.green,fontSize:"34px"}},"→"),
      h("div",{style:{display:"flex",flexDirection:"column",gap:"8px",flex:1,border:`1px solid ${C.green}`,backgroundColor:"rgba(34,197,94,0.06)",borderRadius:"10px",padding:"22px 24px"}},
        h("div",{style:{fontFamily:"Fira Code",fontSize:"18px",color:C.green}},"the fix"), h("div",{style:{fontFamily:"Fira Sans",fontWeight:500,fontSize:"25px",color:C.ink}}, p.fix)))));
}
function layoutBody(spec, slide, S, ac) {
  const t = slide.title ? [titleEl(slide.title, slide.accent, tfs(S, slide.title), ac)] : [];
  if (slide.tiles) return [...t, tilesEl(slide.tiles)];
  if (slide.items) return [...t, changelogEl(slide.items)];
  if (slide.pairs) return [...t, pairsEl(slide.pairs)];
  return [titleEl(slide.title, slide.accent, tfs(S, slide.title), ac), body(slide.body, S.sub), ...(slide.data ? [bars(slide.data)] : [])];
}

const tfs = (S, str) => { const b=S.big; if(str.length>40) return b-30; if(str.length>26) return b-16; return b; };

function frame(S, headerRight, kids, footL, footR) {
  return h("div",{style:{width:`${S.w}px`,height:`${S.h}px`,display:"flex",flexDirection:"column",justifyContent:"space-between",backgroundColor:C.bg,backgroundImage:`url(${DOT})`,backgroundRepeat:"repeat",padding:`${S.pad}px`,fontFamily:"Fira Sans"}},
    h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"center",borderBottom:`1px solid ${C.rule}`,paddingBottom:"22px"}},
      kids.mark, headerRight || h("div",{},"")),
    h("div",{style:{display:"flex",flexDirection:"column",gap:"26px",flex:1,justifyContent:kids.align||"center",paddingTop:kids.align==="flex-start"?"48px":"0"}}, ...kids.body),
    h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"center",borderTop:`1px solid ${C.rule}`,paddingTop:"22px"}},
      h("div",{style:{fontFamily:"Fira Code",fontSize:`${S.foot}px`,color:C.soft}}, footL||""),
      h("div",{style:{fontFamily:"Fira Code",fontSize:`${S.foot}px`,color:footR && footR.accent ? C.green : C.ink}}, footR ? footR.text : "")));
}

function footerSource(spec, slide) {
  const src = (slide && slide.source) || spec.source;
  return src ? `source: ${src}` : ""; // blank unless a real citation exists (eyebrow already carries the kicker)
}

function coverCard(spec, S) {
  const ac = accentFor(spec.audience);
  return frame(S, eyebrow(spec.kicker, S.eb), {
    mark: wordmark(brandFor(spec.audience), S.mark),
    body: [ titleEl(spec.cover.title, spec.cover.accent, tfs(S, spec.cover.title), ac), body(spec.cover.sub, S.sub), ...(spec.cover.data ? [bars(spec.cover.data)] : []) ],
  }, footerSource(spec, spec.cover), { text: spec.cta.foot, accent:false });
}
function slideCard(spec, slide, S) {
  const ac = accentFor(spec.audience);
  const dataLed = !!(slide.tiles || slide.items || slide.pairs);
  return frame(S, eyebrow(spec.kicker, S.eb), {
    mark: wordmark(brandFor(spec.audience), S.mark),
    body: layoutBody(spec, slide, S, ac),
    align: dataLed ? "flex-start" : "center", // top-1% rhythm: data/list cards pin content high, not floating mid-card
  }, footerSource(spec, slide), { text: spec.cta.foot, accent:false });
}
function ctaCard(spec, S) {
  return frame(S, h("div",{}), {
    mark: wordmark(brandFor(spec.audience), S.mark),
    body: [ titleEl(spec.cta.title, spec.cta.accent, tfs(S, spec.cta.title), C.green), body(spec.cta.sub, S.sub) ],
  }, "", { text: spec.cta.foot, accent:true });
}

function cardsFor(spec) {
  const out = [{ name:"00-cover", el:(S)=>coverCard(spec,S) }];
  spec.slides.forEach((sl,i)=> out.push({ name:`${String(i+1).padStart(2,"0")}-slide`, el:(S)=>slideCard(spec,sl,S) }));
  out.push({ name:`${String(spec.slides.length+1).padStart(2,"0")}-cta`, el:(S)=>ctaCard(spec,S) });
  return out;
}

async function render(el, S) {
  const svg = await satori(el, { width:S.w, height:S.h, fonts });
  return new Resvg(svg, { fitTo:{mode:"width",value:S.w} }).render().asPng();
}

const SB_URL = process.env.SUPABASE_URL, SB_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
async function upload(property, slug, variant, path, png, w, hgt, title, tags) {
  const r1 = await fetch(`${SB_URL}/storage/v1/object/media/${path}`, { method:"POST", headers:{ Authorization:`Bearer ${SB_KEY}`, apikey:SB_KEY, "Content-Type":"image/png", "x-upsert":"true" }, body:png });
  if (!r1.ok && r1.status !== 200) throw new Error(`storage ${r1.status} ${await r1.text()}`);
  const url = `${SB_URL}/storage/v1/object/public/media/${path}`;
  const r2 = await fetch(`${SB_URL}/rest/v1/media_assets?on_conflict=property,kind,slug,variant`, { method:"POST",
    headers:{ Authorization:`Bearer ${SB_KEY}`, apikey:SB_KEY, "Content-Type":"application/json", Prefer:"resolution=merge-duplicates,return=minimal" },
    body: JSON.stringify({ property, kind:"carousel", slug, variant, path, url, width:w, height:hgt, title, tags, generator:"gen_carousel.mjs" }) });
  if (!r2.ok) throw new Error(`index ${r2.status} ${await r2.text()}`);
  return url;
}

const args = process.argv.slice(2);
const noUpload = args.includes("--no-upload");
const outIdx = args.indexOf("--out"), outDir = outIdx !== -1 ? args[outIdx+1] : null;
const specFiles = args.filter((a,i)=> a.endsWith(".json") && (outIdx===-1 || i!==outIdx+1));
if (!specFiles.length) { console.error("no spec .json given"); process.exit(1); }
if (!noUpload && (!SB_URL || !SB_KEY)) { console.error("source supabase.env or pass --no-upload"); process.exit(1); }

for (const file of specFiles) {
  const spec = JSON.parse(await readFile(file, "utf8"));
  const property = propertyFor(spec.audience), cards = cardsFor(spec);
  if (outDir) await mkdir(join(outDir, spec.slug), { recursive:true });
  for (const card of cards) {
    for (const shape of ["portrait","square"]) {
      const S = SHAPES[shape], png = await render(card.el(S), S);
      const variant = `${shape}-${card.name}`, path = `${property}/carousel/${spec.slug}/${variant}.png`;
      if (outDir) await writeFile(join(outDir, spec.slug, `${variant}.png`), png);
      if (!noUpload) await upload(property, spec.slug, variant, path, png, S.w, S.h, deMood(spec.kicker), ["carousel", spec.audience, spec.slug]);
    }
  }
  console.log(`✓ ${spec.slug} (${spec.audience}) — ${cards.length} cards ×2${noUpload?" (render-only)":", uploaded"}`);
}
console.log("DONE");
