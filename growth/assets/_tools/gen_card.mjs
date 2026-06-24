// gen_card.mjs — single social data-card (NOT a carousel). For X (square 1080x1080) +
// Threads (portrait 1080x1350). Same locked data-editorial system as gen_carousel
// (visual-system-locked): Archivo display, dark #0c0d10, GREEN accent (autopost-green-
// antislop), DOT texture, lowercase wordmark. One card = one claim. Honest numbers only,
// no Synergix, no client names, de-em-dashed copy.
//
// Reads a specs JSON: [{uuid, brand:"founder"|"company", shape:"square"|"portrait",
//   layout:"quote"|"stat"|"bars"|"twocol"|"checklist"|"receipt", kicker, headline, accent, sub, ...}]
//   checklist adds: items:[{t, note?}] — green-check rows (rollback/audit/readiness lists)
//   compare adds: before:{label?,value}, after:{label?,value} — struck old → green arrow → new
// Renders each → Supabase media/<property>/social/<uuid>/<shape>.png, prints uuid→URL.
//
// Deps (satori/resvg) resolve via render.sh symlink. Creds: supabase.env.
// Run:  growth/assets/_tools/render.sh gen_card.mjs growth/social/cards/<file>.json [--no-upload --out /tmp/c]
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
const DOT = `data:image/svg+xml;base64,${Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44"><circle cx="2" cy="2" r="1.3" fill="#ffffff" fill-opacity="0.028"/></svg>').toString("base64")}`;
const h = (t, p, ...k) => ({ type: t, props: { ...p, children: k.length <= 1 ? k[0] : k } });
const deDash = (s) => (s || "").replace(/\s*[—–]\s*/g, " · "); // de-em-dash card copy

const SHAPES = {
  square:   { w:1080, h:1080, pad:80, big:96, mark:25, sub:28, foot:19, eb:19 },
  portrait: { w:1080, h:1350, pad:84, big:104, mark:26, sub:30, foot:20, eb:20 },
};
const brandFor = (b) => (b === "founder" ? "trovex" : "tsukumo");
const domainFor = (b) => (b === "founder" ? "trovex.dev" : "tsukumo.ch");
const tfs = (S, str) => { const n = (str||"").length; if (n > 64) return S.big - 34; if (n > 42) return S.big - 18; return S.big; };

function wordmark(word, fs) {
  return h("div",{style:{display:"flex",alignItems:"center",gap:"11px",fontFamily:"Fira Code",fontSize:`${fs}px`,color:C.ink}},
    h("div",{style:{width:`${Math.round(fs*0.62)}px`,height:`${Math.round(fs*0.62)}px`,backgroundColor:C.green}}), h("span",{},word));
}
// founder account is DE-BRANDED (owner): keep the accent (green square mark) but drop the
// product NAME — no 'trovex'/'tsukumo' wordmark text, no domain footer. company stays branded.
const markOnly = (fs) => h("div",{style:{display:"flex",width:`${Math.round(fs*0.62)}px`,height:`${Math.round(fs*0.62)}px`,backgroundColor:C.green}});
// headline: accent substring colored green, word-level spans wrap
function headlineEl(full, accent, S) {
  const fs = tfs(S, full);
  const idx = accent ? full.indexOf(accent) : -1;
  const segs = idx === -1 ? [{t:full,a:false}] : [{t:full.slice(0,idx),a:false},{t:accent,a:true},{t:full.slice(idx+accent.length),a:false}];
  const words = [];
  for (const s of segs) for (const w of s.t.split(" ")) { if (w==="") continue; words.push({w,a:s.a}); }
  // attach trailing punctuation (a lone ".", "," etc after the accent) to the prior word — else it renders as a floating detached token
  for (let i = words.length - 1; i > 0; i--) if (/^[.,!?;:]+$/.test(words[i].w)) { words[i-1].w += words[i].w; words.splice(i, 1); }
  return h("div",{style:{display:"flex",flexWrap:"wrap",fontFamily:"Archivo",fontWeight:800,fontSize:`${fs}px`,lineHeight:0.99,letterSpacing:"-0.035em"}},
    ...words.map(({w,a})=>h("span",{style:{color:a?C.green:C.ink,marginRight:"0.24em"}}, w)));
}
const subEl = (s,S) => s ? h("div",{style:{fontFamily:"Fira Sans",fontWeight:500,fontSize:`${S.sub}px`,lineHeight:1.4,color:C.soft,maxWidth:"900px"}}, deDash(s)) : null;

function heroEl(c, S) {
  return h("div",{style:{display:"flex",flexDirection:"column",gap:"8px"}},
    h("div",{style:{fontFamily:"Archivo",fontWeight:800,fontSize:`${S.w===1080&&S.h===1350?210:180}px`,color:C.green,letterSpacing:"-0.05em",lineHeight:0.86}}, c.heroValue),
    h("div",{style:{fontFamily:"Archivo",fontWeight:800,fontSize:"46px",color:C.ink,letterSpacing:"-0.02em",lineHeight:1.05,maxWidth:"900px"}}, deDash(c.heroLabel)));
}
function barsEl(data) {
  return h("div",{style:{display:"flex",flexDirection:"column",gap:"24px"}},
    ...data.map(d => h("div",{style:{display:"flex",flexDirection:"column",gap:"10px"}},
      h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"baseline"}},
        h("div",{style:{fontFamily:"Fira Code",fontSize:"22px",color:C.soft}}, deDash(d.label)),
        h("div",{style:{fontFamily:"Archivo",fontWeight:800,fontSize:"34px",color:C.green,letterSpacing:"-0.02em"}}, d.value)),
      h("div",{style:{display:"flex",height:"28px",backgroundColor:C.track,borderRadius:"3px"}},
        h("div",{style:{width:`${Math.max(4,Math.min(100,d.pct))}%`,backgroundColor:C.green,borderRadius:"3px"}})))));
}
function twocolEl(cols) {
  return h("div",{style:{display:"flex",gap:"22px"}},
    ...cols.map((col,i)=>h("div",{style:{display:"flex",flexDirection:"column",gap:"12px",flex:1,border:`1px solid ${i===cols.length-1?C.green:C.rule}`,backgroundColor:i===cols.length-1?"rgba(34,197,94,0.06)":C.panel,borderRadius:"12px",padding:"28px 26px"}},
      h("div",{style:{fontFamily:"Fira Code",fontSize:"19px",color:i===cols.length-1?C.green:C.soft,letterSpacing:"0.02em"}}, deDash(col.head)),
      h("div",{style:{fontFamily:"Fira Sans",fontWeight:500,fontSize:"27px",color:C.ink,lineHeight:1.25}}, deDash(col.body)))));
}
// versus: honest comparison table — rows of {criterion, us, them, win?:'us'|'them'}.
// the winner cell per row is green (and `win` CAN be 'them' — show their strengths too).
function versusEl(c) {
  const cell = (txt, win) => h("div",{style:{display:"flex",flex:1,padding:"14px 16px",fontFamily:"Fira Sans",fontWeight:win?700:500,fontSize:"23px",lineHeight:1.22,color:win?C.green:C.ink}}, deDash(txt));
  const head = h("div",{style:{display:"flex",alignItems:"center",borderBottom:`1px solid ${C.rule}`,paddingBottom:"10px"}},
    h("div",{style:{display:"flex",flex:1.1,fontFamily:"Fira Code",fontSize:"18px",color:C.faint,padding:"0 16px"}}, ""),
    h("div",{style:{display:"flex",flex:1,alignItems:"center",gap:"9px",padding:"0 16px"}},
      h("div",{style:{width:"16px",height:"16px",backgroundColor:C.green}}), h("div",{style:{fontFamily:"Fira Code",fontSize:"20px",color:C.ink,letterSpacing:"0.02em"}}, deDash(c.versus.us))),
    h("div",{style:{display:"flex",flex:1,fontFamily:"Fira Code",fontSize:"20px",color:C.soft,padding:"0 16px",letterSpacing:"0.02em"}}, deDash(c.versus.them)));
  const rows = c.rows.map((r,i)=>h("div",{style:{display:"flex",alignItems:"stretch",borderTop:i?`1px solid ${C.track}`:"none"}},
    h("div",{style:{display:"flex",flex:1.1,padding:"14px 16px",fontFamily:"Fira Code",fontSize:"18px",color:C.soft}}, deDash(r.criterion)),
    cell(r.us, r.win==="us"), cell(r.them, r.win==="them")));
  const out = [head, ...rows];
  if (c.pick) out.push(h("div",{style:{display:"flex",borderTop:`1px solid ${C.rule}`,marginTop:"4px",paddingTop:"14px",fontFamily:"Fira Sans",fontWeight:500,fontSize:"22px",color:C.soft,lineHeight:1.3}}, deDash(c.pick)));
  return h("div",{style:{display:"flex",flexDirection:"column",border:`1px solid ${C.rule}`,backgroundColor:C.panel,borderRadius:"14px",padding:"22px 18px"}}, ...out);
}
function checklistEl(items) {
  const check = h("div",{style:{display:"flex",width:"34px",height:"34px",minWidth:"34px",borderRadius:"7px",border:`1.5px solid ${C.green}`,backgroundColor:"rgba(34,197,94,0.08)",alignItems:"center",justifyContent:"center"}},
    h("div",{style:{width:"9px",height:"16px",borderRight:`3px solid ${C.green}`,borderBottom:`3px solid ${C.green}`,transform:"rotate(45deg)",marginTop:"-3px"}}));
  return h("div",{style:{display:"flex",flexDirection:"column",gap:"22px"}},
    ...items.map(it=>{
      const txt = [h("div",{style:{fontFamily:"Archivo",fontWeight:800,fontSize:"31px",color:C.ink,letterSpacing:"-0.02em",lineHeight:1.1}}, deDash(it.t))];
      if (it.note) txt.push(h("div",{style:{fontFamily:"Fira Sans",fontWeight:500,fontSize:"24px",color:C.soft,lineHeight:1.3}}, deDash(it.note)));
      return h("div",{style:{display:"flex",alignItems:"flex-start",gap:"20px"}},
        check,
        h("div",{style:{display:"flex",flexDirection:"column",gap:"5px",flex:1}}, ...txt));
    }));
}
const ARROW = `data:image/svg+xml;base64,${Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="44" height="30"><path d="M3 15 H34 M24 5 L37 15 L24 25" stroke="#22c55e" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>').toString("base64")}`;
function compareEl(c) {
  const arrow = h("img",{src:ARROW,width:44,height:30,style:{}});
  const box = (label, value, on) => h("div",{style:{display:"flex",flexDirection:"column",gap:"12px",flex:1,justifyContent:"center",border:`1px solid ${on?C.green:C.rule}`,backgroundColor:on?"rgba(34,197,94,0.07)":C.panel,borderRadius:"12px",padding:"28px 26px"}},
    h("div",{style:{fontFamily:"Fira Code",fontSize:"18px",color:on?C.green:C.faint,letterSpacing:"0.02em"}}, deDash(label)),
    h("div",{style:{fontFamily:"Archivo",fontWeight:800,fontSize:"40px",color:on?C.ink:C.soft,letterSpacing:"-0.02em",lineHeight:1.02,...(on?{}:{textDecoration:"line-through"})}}, deDash(value)));
  return h("div",{style:{display:"flex",alignItems:"stretch",gap:"20px"}},
    box(c.before.label||"before", c.before.value, false),
    h("div",{style:{display:"flex",alignItems:"center"}}, arrow),
    box(c.after.label||"after", c.after.value, true));
}
function receiptEl(c, S) {
  return h("div",{style:{display:"flex",flexDirection:"column",gap:"0px",border:`1px solid ${C.rule}`,backgroundColor:C.panel,borderRadius:"14px",padding:"36px 38px"}},
    h("div",{style:{fontFamily:"Fira Code",fontSize:"20px",color:C.soft,letterSpacing:"0.04em",borderBottom:`1px dashed ${C.rule}`,paddingBottom:"18px",marginBottom:"22px"}}, "savings receipt"),
    ...c.lines.map(l=>h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"baseline",paddingBottom:"14px"}},
      h("div",{style:{fontFamily:"Fira Sans",fontWeight:500,fontSize:"26px",color:C.soft}}, l.k),
      h("div",{style:{fontFamily:"Fira Code",fontSize:"26px",color:C.ink}}, l.v))),
    h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"baseline",borderTop:`1px solid ${C.rule}`,paddingTop:"22px",marginTop:"6px"}},
      h("div",{style:{fontFamily:"Archivo",fontWeight:800,fontSize:"30px",color:C.ink}}, c.totalK),
      h("div",{style:{fontFamily:"Archivo",fontWeight:800,fontSize:"54px",color:C.green,letterSpacing:"-0.03em"}}, c.totalV)));
}

function body(c, S) {
  switch (c.layout) {
    case "stat":    return [c.headline?headlineEl(c.headline,c.accent,S):null, heroEl(c,S), subEl(c.sub,S)].filter(Boolean);
    case "bars":    return [headlineEl(c.headline,c.accent,S), barsEl(c.data), subEl(c.sub,S)].filter(Boolean);
    case "twocol":  return [headlineEl(c.headline,c.accent,S), twocolEl(c.cols), subEl(c.sub,S)].filter(Boolean);
    case "checklist": return [headlineEl(c.headline,c.accent,S), checklistEl(c.items), subEl(c.sub,S)].filter(Boolean);
    case "compare": return [headlineEl(c.headline,c.accent,S), compareEl(c), subEl(c.sub,S)].filter(Boolean);
    case "versus": return [headlineEl(c.headline,c.accent,S), versusEl(c), subEl(c.sub,S)].filter(Boolean);
    case "receipt": return [c.headline?headlineEl(c.headline,c.accent,S):null, receiptEl(c,S), subEl(c.sub,S)].filter(Boolean);
    default:        return [headlineEl(c.headline,c.accent,S), subEl(c.sub,S)].filter(Boolean); // quote
  }
}
function card(c, S) {
  const dataLed = c.layout==="bars"||c.layout==="twocol"||c.layout==="receipt"||c.layout==="stat"||c.layout==="checklist"||c.layout==="compare"||c.layout==="versus";
  const unbranded = c.brand === "founder"; // founder account de-branded: accent stays, name goes
  return h("div",{style:{width:`${S.w}px`,height:`${S.h}px`,display:"flex",flexDirection:"column",justifyContent:"space-between",backgroundColor:C.bg,backgroundImage:`url(${DOT})`,backgroundRepeat:"repeat",padding:`${S.pad}px`,fontFamily:"Fira Sans"}},
    h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"center",borderBottom:`1px solid ${C.rule}`,paddingBottom:"20px"}},
      unbranded ? markOnly(S.mark) : wordmark(brandFor(c.brand), S.mark),
      c.kicker?h("div",{style:{fontFamily:"Fira Code",fontSize:`${S.eb}px`,color:C.soft,letterSpacing:"0.04em"}}, deDash(c.kicker)):h("div",{})),
    h("div",{style:{display:"flex",flexDirection:"column",gap:"30px",flex:1,justifyContent:dataLed?"flex-start":"center",paddingTop:dataLed?"48px":"0"}}, ...body(c,S)),
    h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"center",borderTop:`1px solid ${C.rule}`,paddingTop:"20px"}},
      h("div",{style:{fontFamily:"Fira Code",fontSize:`${S.foot}px`,color:C.soft}}, c.source?`source: ${deDash(c.source)}`:""),
      unbranded ? h("div",{}) : h("div",{style:{fontFamily:"Fira Code",fontSize:`${S.foot}px`,color:C.green}}, domainFor(c.brand))));
}

const SB_URL = process.env.SUPABASE_URL, SB_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
async function upload(property, uuid, shape, png) {
  const path = `${property}/social/${uuid}/${shape}.png`;
  const r1 = await fetch(`${SB_URL}/storage/v1/object/media/${path}`, { method:"POST", headers:{ Authorization:`Bearer ${SB_KEY}`, apikey:SB_KEY, "Content-Type":"image/png", "x-upsert":"true" }, body:png });
  if (!r1.ok && r1.status !== 200) throw new Error(`storage ${r1.status} ${await r1.text()}`);
  return `${SB_URL}/storage/v1/object/public/media/${path}`;
}

const args = process.argv.slice(2);
const noUpload = args.includes("--no-upload");
const outIdx = args.indexOf("--out"), outDir = outIdx !== -1 ? args[outIdx+1] : null;
const files = args.filter((a,i)=> a.endsWith(".json") && (outIdx===-1 || i!==outIdx+1));
if (!files.length) { console.error("no specs .json"); process.exit(1); }
if (!noUpload && (!SB_URL || !SB_KEY)) { console.error("source supabase.env or --no-upload"); process.exit(1); }

async function render(el, S) {
  const svg = await satori(el, { width:S.w, height:S.h, fonts });
  return new Resvg(svg, { fitTo:{mode:"width",value:S.w} }).render().asPng();
}

const result = {};
for (const file of files) {
  const cards = JSON.parse(await readFile(file, "utf8"));
  for (const c of cards) {
    const shape = c.shape === "portrait" ? "portrait" : "square";
    const S = SHAPES[shape];
    const png = await render(card(c, S), S);
    if (outDir) { await mkdir(join(outDir), { recursive:true }); await writeFile(join(outDir, `${c.uuid}.png`), png); }
    let url = null;
    if (!noUpload) url = await upload(brandFor(c.brand)==="trovex"?"trovex":"tsukumo", c.uuid, shape, png);
    result[c.uuid] = url || `(local ${shape})`;
    console.log(`✓ ${c.uuid} (${c.brand}/${shape}/${c.layout})${url?" "+url:""}`);
  }
}
console.log("\n=== uuid → url ===");
console.log(JSON.stringify(result, null, 0));
console.log("DONE");
