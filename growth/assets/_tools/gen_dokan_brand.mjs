// gen_dokan_brand.mjs — bespoke brand identity for dokan (suite 4th-pillar PREP).
// NOT a templated social card; one-off brand lockups. Same data-editorial DNA as
// gen_card/gen_carousel (dark #0c0d10, Archivo display, Fira mono, DOT texture, lowercase
// wordmark) but dokan's OWN accent: CYAN #22d3ee (distinct from trovex green / wraith violet
// / yoru amber — reads conduit/runtime/pipe). Positioning SSOT: trovex doc eeeddc3f.
// Renders: og (1200x630), wordmark lockup (1200x630), 4-pillar suite diagram (1600x900).
// Honest: no fabricated metrics; the dogfood line is real. Run via render.sh (deps + SB env).
//   growth/assets/_tools/render.sh gen_dokan_brand.mjs [--no-upload --out /tmp/dk]
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
const C = { bg:"#0c0d10", panel:"#101216", ink:"#f3f0e9", soft:"#8b8f98", faint:"#5f636b", rule:"#23262d", track:"#181a1f" };
// suite accents (locked): the 4 pillars
const A = { trovex:"#22c55e", wraith:"#8b5cf6", yoru:"#f59e0b", dokan:"#22d3ee" };
const DOT = `data:image/svg+xml;base64,${Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44"><circle cx="2" cy="2" r="1.3" fill="#ffffff" fill-opacity="0.028"/></svg>').toString("base64")}`;
const h = (t, p, ...k) => ({ type: t, props: { ...p, children: k.length <= 1 ? k[0] : k } });

function wordmark(word, accent, fs) {
  return h("div",{style:{display:"flex",alignItems:"center",gap:`${Math.round(fs*0.42)}px`,fontFamily:"Fira Code",fontSize:`${fs}px`,color:C.ink}},
    h("div",{style:{width:`${Math.round(fs*0.62)}px`,height:`${Math.round(fs*0.62)}px`,backgroundColor:accent}}), h("span",{},word));
}
function frame(w, hgt, pad, kids, foot) {
  return h("div",{style:{width:`${w}px`,height:`${hgt}px`,display:"flex",flexDirection:"column",justifyContent:"space-between",backgroundColor:C.bg,backgroundImage:`url(${DOT})`,backgroundRepeat:"repeat",padding:`${pad}px`,fontFamily:"Fira Sans"}},
    h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"center"}}, kids.header || h("div",{}), kids.headerRight || h("div",{})),
    h("div",{style:{display:"flex",flexDirection:"column",gap:"24px",flex:1,justifyContent:"center"}}, ...kids.body),
    h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"center",borderTop:`1px solid ${C.rule}`,paddingTop:"22px"}},
      h("div",{style:{fontFamily:"Fira Code",fontSize:"22px",color:C.soft}}, foot?.left || ""),
      h("div",{style:{fontFamily:"Fira Code",fontSize:"22px",color:foot?.accent || C.ink}}, foot?.right || "")));
}

// ---- OG 1200x630 ----
function og() {
  return frame(1200, 630, 72, {
    header: wordmark("dokan", A.dokan, 34),
    headerRight: h("div",{style:{fontFamily:"Fira Code",fontSize:"22px",color:C.soft,letterSpacing:"0.04em"}}, "the 4th pillar · prep"),
    body: [
      h("div",{style:{display:"flex",flexWrap:"wrap",fontFamily:"Archivo",fontWeight:800,fontSize:"82px",lineHeight:0.98,letterSpacing:"-0.035em",maxWidth:"1040px"}},
        ...[["your",0],["agents",0],["run",0],["the",0],["scripts.",1],["you",0],["don't",0],["click.",1]].map(([w,a])=>
          h("span",{style:{color:a?A.dokan:C.ink,marginRight:"0.24em"}}, w))),
      h("div",{style:{fontFamily:"Fira Sans",fontWeight:500,fontSize:"30px",lineHeight:1.4,color:C.soft,maxWidth:"940px"}},
        "an agent-operated deterministic script runtime. upload, run, schedule over MCP. the mechanical 80%, off your agents' token budget."),
    ],
  }, { left: "the conduit · MCP-native", right: "Apache-2.0", accent: A.dokan });
}

// ---- wordmark lockup 1200x630 ----
function lockup() {
  return frame(1200, 630, 72, {
    headerRight: h("div",{style:{fontFamily:"Fira Code",fontSize:"22px",color:C.soft,letterSpacing:"0.04em"}}, "wordmark · accent #22d3ee"),
    body: [
      h("div",{style:{display:"flex",alignItems:"center",gap:"30px"}},
        h("div",{style:{width:"104px",height:"104px",backgroundColor:A.dokan}}),
        h("div",{style:{fontFamily:"Archivo",fontWeight:800,fontSize:"150px",color:C.ink,letterSpacing:"-0.04em",lineHeight:1}}, "dokan")),
      h("div",{style:{fontFamily:"Fira Code",fontSize:"26px",color:C.soft,letterSpacing:"0.02em"}}, "lowercase always · cyan square mark · Archivo 800"),
    ],
  }, { left: "tsukumo suite · 4th pillar (prep)", right: "a tsukumo product", accent: A.dokan });
}

// ---- 4-pillar suite diagram 1600x900 ----
function pillar(name, accent, verb, line) {
  return h("div",{style:{display:"flex",flexDirection:"column",gap:"16px",flex:1,border:`1px solid ${C.rule}`,backgroundColor:C.panel,borderRadius:"16px",padding:"40px 34px"}},
    h("div",{style:{display:"flex",alignItems:"center",gap:"16px"}},
      h("div",{style:{width:"30px",height:"30px",backgroundColor:accent}}),
      h("div",{style:{fontFamily:"Archivo",fontWeight:800,fontSize:"44px",color:C.ink,letterSpacing:"-0.03em"}}, name)),
    h("div",{style:{fontFamily:"Fira Code",fontSize:"22px",color:accent,letterSpacing:"0.06em"}}, verb),
    h("div",{style:{fontFamily:"Fira Sans",fontWeight:500,fontSize:"27px",color:C.soft,lineHeight:1.32}}, line));
}
function suite() {
  return h("div",{style:{width:"1600px",height:"900px",display:"flex",flexDirection:"column",justifyContent:"space-between",backgroundColor:C.bg,backgroundImage:`url(${DOT})`,backgroundRepeat:"repeat",padding:"84px",fontFamily:"Fira Sans"}},
    h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"center"}},
      h("div",{style:{fontFamily:"Fira Code",fontSize:"26px",color:C.soft,letterSpacing:"0.04em"}}, "the tsukumo suite · the operating layer for agent fleets"),
      h("div",{style:{fontFamily:"Fira Code",fontSize:"24px",color:A.dokan}}, "4 pillars")),
    h("div",{style:{display:"flex",gap:"26px"}},
      pillar("trovex", A.trovex, "KNOW", "the context agents read. one canonical source of truth."),
      pillar("wrai.th", A.wraith, "COORDINATE", "how a fleet hands off, shares memory, owns tasks."),
      pillar("yoru", A.yoru, "HEALTHY", "whether agents are observable, per-action, in prod."),
      pillar("dokan", A.dokan, "DO", "the deterministic 20/80. mechanical work as scripts.")),
    h("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"center",borderTop:`1px solid ${C.rule}`,paddingTop:"24px"}},
      h("div",{style:{fontFamily:"Fira Code",fontSize:"22px",color:C.soft}}, "know · coordinate · health · do"),
      h("div",{style:{fontFamily:"Fira Code",fontSize:"22px",color:C.ink}}, "tsukumo.ch")));
}

const ASSETS = [
  { name: "og", w:1200, h:630, el: og },
  { name: "wordmark", w:1200, h:630, el: lockup },
  { name: "suite-4pillar", w:1600, h:900, el: suite },
];

const SB_URL = process.env.SUPABASE_URL, SB_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
async function upload(path, png) {
  const r = await fetch(`${SB_URL}/storage/v1/object/media/${path}`, { method:"POST", headers:{ Authorization:`Bearer ${SB_KEY}`, apikey:SB_KEY, "Content-Type":"image/png", "x-upsert":"true" }, body:png });
  if (!r.ok && r.status !== 200) throw new Error(`storage ${r.status} ${await r.text()}`);
  return `${SB_URL}/storage/v1/object/public/media/${path}`;
}

const args = process.argv.slice(2);
const noUpload = args.includes("--no-upload");
const outIdx = args.indexOf("--out"), outDir = outIdx !== -1 ? args[outIdx+1] : null;
if (!noUpload && (!SB_URL || !SB_KEY)) { console.error("source supabase.env or --no-upload"); process.exit(1); }

const result = {};
for (const a of ASSETS) {
  const svg = await satori(a.el(), { width:a.w, height:a.h, fonts });
  const png = new Resvg(svg, { fitTo:{mode:"width",value:a.w} }).render().asPng();
  if (outDir) { await mkdir(outDir, { recursive:true }); await writeFile(join(outDir, `${a.name}.png`), png); }
  let url = null;
  if (!noUpload) url = await upload(`dokan/brand/${a.name}.png`, png);
  result[a.name] = url || `(local ${a.w}x${a.h})`;
  console.log(`✓ ${a.name} (${a.w}x${a.h})${url?" "+url:""}`);
}
console.log("\n=== dokan brand ===");
console.log(JSON.stringify(result, null, 0));
console.log("DONE");
