// gen_brand_gallery.mjs — REUSABLE per-product launch gallery on the locked
// data-editorial system (memory visual-system-locked + suite-accent-palette).
// One family, one accent per product: trovex=green, wrai.th=violet, yoru=amber.
// Content-driven: PRODUCTS = accent/wordmark/domain; CONTENT = the real copy +
// client-safe screenshots per product. Add a product by adding a CONTENT entry.
//
// Run:  node growth/assets/_tools/gen_brand_gallery.mjs <product>   (wraith|trovex)
// Honest: copy verbatim, real numbers only. Screenshots must be client-safe (no
// client/project names) — memory confidentiality-no-client-names.
// Deps (satori/resvg) resolve via a node_modules symlink up-tree.
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPOFONT = join(HERE, "..", "_fonts");
const SF = join(homedir(), "Library", "Fonts");
const fonts = [
  { name: "Archivo", data: await readFile(join(REPOFONT, "Archivo-800.ttf")), weight: 800, style: "normal" },
  { name: "Fira Sans", data: await readFile(join(SF, "FiraSans-Medium.otf")), weight: 500, style: "normal" },
  { name: "Fira Code", data: await readFile(join(SF, "FiraCode-Regular.ttf")), weight: 400, style: "normal" },
];
const C = { bg: "#0c0d10", panel: "#101216", ink: "#f3f0e9", soft: "#8b8f98", subtle: "#74808f", rule: "#23262d" };
const PRODUCTS = {
  trovex: { accent: "#22c55e", word: ["trovex"], domain: "trovex.dev" },
  wraith: { accent: "#6e6bf2", word: ["wrai", ".", "th"], domain: "tsukumo.ch/wraith" },
  yoru: { accent: "#f59e0b", word: ["yoru"], domain: "yoru.sh" },
};
// per-product CONTENT (verbatim, real numbers). shot files are client-safe captures.
const CONTENT = {
  wraith: {
    eyebrow: "the agent control plane",
    shots: [{ file: "/tmp/fleet-v2-band.png", w: 2800, h: 826, title: "Mission control for your agent fleet", accent: "agent fleet", eb: "LIVE · the real board" }],
    how: { title: "point any MCP agent at it, no rewrite", accent: "no rewrite", steps: ["register your agents", "they message + share a task board", "watch the fleet from one dashboard"], foot: "Claude Code · Cursor · Windsurf · Zed — the control plane you point agents at, not a framework you rewrite into." },
    trust: { facts: ["one Go binary, one SQLite file", "58 MCP tools, zero config", "100% local by default, no telemetry", "AGPL · v1.0 stable"], install: "curl -fsSL https://raw.githubusercontent.com/TsukumoHQ/WRAI.TH/main/install.sh | bash", foot: "github.com/TsukumoHQ/WRAI.TH · tsukumo.ch/wraith" },
    og: { title: "Mission control for your agent fleet.", accent: "agent fleet.", sub: "Persistent memory, messaging, and a shared task board over MCP. One Go binary, local, open source.", footRight: "v1.0 · 58 MCP tools · 100% local · AGPL" },
    thumb: "CONTROL PLANE",
  },
  trovex: {
    eyebrow: "the canonical doc store",
    shots: [
      { file: "/tmp/trovex-savings-band.png", w: 2800, h: 826, title: "What trovex saved, on our own repo", accent: "our own repo", eb: "LIVE · /savings" },
      { file: "/tmp/trovex-search.png", w: 1920, h: 1120, title: "one query, one current doc", accent: "one current doc", eb: "LIVE · trovex search" },
    ],
    how: { title: "index your repo, then ask, get one doc", accent: "one doc", steps: ["index your repo", "agent asks trovex(q)", "one canonical doc + freshness marker"], foot: "Local: SQLite + on-device ONNX embeddings. No cloud, no API keys." },
    trust: { facts: ["local-first, runs on your machine", "SQLite + on-device ONNX embeddings", "no cloud, no API keys", "AGPL core · MIT CLI · MCP-native"], install: "uv tool install git+https://github.com/TsukumoHQ/trovex", foot: "github.com/TsukumoHQ/trovex · trovex.dev" },
    og: { title: "One canonical doc for your coding agents.", accent: "coding agents.", sub: "~60% fewer tokens per lookup. Local-first, open source.", footRight: "AGPL core / MIT CLI · MCP-native" },
    thumb: "CONTEXT",
  },
};

const DOT = `data:image/svg+xml;base64,${Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44"><circle cx="2" cy="2" r="1.3" fill="#ffffff" fill-opacity="0.028"/></svg>').toString("base64")}`;

const h = (t, p, ...k) => ({ type: t, props: { ...p, children: k.length <= 1 ? k[0] : k } });
const product = process.argv[2] || "wraith";
const P = PRODUCTS[product], D = CONTENT[product], A = P.accent;
const dataURI = async (f) => `data:image/png;base64,${(await readFile(f)).toString("base64")}`;

function wordmark(fs) {
  const dot = P.word.length === 3;
  return h("div", { style: { display: "flex", alignItems: "center", fontFamily: "Fira Code", fontSize: `${fs}px`, color: C.ink } },
    dot ? null : h("div", { style: { width: `${Math.round(fs * 0.6)}px`, height: `${Math.round(fs * 0.6)}px`, backgroundColor: A, marginRight: "11px" } }),
    ...P.word.map((seg, i) => h("span", { style: { color: i === 1 && dot ? A : C.ink } }, seg)));
}
const eyebrow = (s, fs) => h("div", { style: { fontFamily: "Fira Code", fontSize: `${fs}px`, color: C.subtle, letterSpacing: "0.08em" } }, s);
function titleEl(full, accent, fs) {
  const i = accent ? full.indexOf(accent) : -1;
  const segs = i === -1 ? [{ t: full, a: 0 }] : [{ t: full.slice(0, i), a: 0 }, { t: accent, a: 1 }, { t: full.slice(i + accent.length), a: 0 }];
  const words = [];
  for (const s of segs) for (const w of s.t.split(" ")) { if (w === "") continue; words.push({ w, a: s.a }); }
  return h("div", { style: { display: "flex", flexWrap: "wrap", fontFamily: "Archivo", fontWeight: 800, fontSize: `${fs}px`, lineHeight: 1.0, letterSpacing: "-0.035em", maxWidth: "1120px" } },
    ...words.map(({ w, a }) => h("span", { style: { color: a ? A : C.ink, marginRight: "0.24em" } }, w)));
}
function frame(w, hgt, kids, pad = 64) {
  return h("div", { style: { width: `${w}px`, height: `${hgt}px`, display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.bg, backgroundImage: `url(${DOT})`, backgroundRepeat: "repeat", color: C.ink, padding: `${pad}px`, fontFamily: "Fira Sans", position: "relative" } },
    h("div", { style: { position: "absolute", top: 0, left: 0, width: "100%", height: "5px", backgroundColor: A } }), ...kids);
}
// fit a shot into a max box, preserve aspect
function fitBox(nw, nh, maxW, maxH) { const s = Math.min(maxW / nw, maxH / nh); return [Math.round(nw * s), Math.round(nh * s)]; }

function shotSlide(shot, src) {
  const [iw, ih] = fitBox(shot.w, shot.h, 1142, 396);
  return frame(1270, 760, [
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, wordmark(28), eyebrow(shot.eb, 19)),
    titleEl(shot.title, shot.accent, 54),
    h("div", { style: { display: "flex", justifyContent: "center" } },
      h("div", { style: { display: "flex", border: `1px solid ${C.rule}`, borderRadius: "12px", overflow: "hidden", backgroundColor: C.panel } },
        h("img", { src, width: iw, height: ih, style: { display: "block" } }))),
  ]);
}
function howSlide() {
  const node = (n, t) => h("div", { style: { display: "flex", flexDirection: "column", gap: "14px", flex: 1, border: `1px solid ${C.rule}`, backgroundColor: C.panel, borderRadius: "10px", padding: "32px 28px" } },
    h("div", { style: { fontFamily: "Fira Code", fontSize: "20px", color: A } }, n),
    h("div", { style: { fontFamily: "Archivo", fontWeight: 800, fontSize: "28px", color: C.ink, lineHeight: 1.1, letterSpacing: "-0.02em" } }, t));
  const arrow = () => h("div", { style: { display: "flex", alignItems: "center", color: A, fontSize: "40px", padding: "0 6px" } }, "→");
  return frame(1270, 760, [
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, wordmark(28), eyebrow("how it works", 19)),
    titleEl(D.how.title, D.how.accent, 54),
    h("div", { style: { display: "flex", alignItems: "stretch" } }, node("01", D.how.steps[0]), arrow(), node("02", D.how.steps[1]), arrow(), node("03", D.how.steps[2])),
    h("div", { style: { fontFamily: "Fira Code", fontSize: "21px", color: C.soft } }, D.how.foot),
  ]);
}
function trustSlide() {
  return frame(1270, 760, [
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, wordmark(28), eyebrow("what it is", 19)),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "18px" } },
      ...D.trust.facts.map((f) => h("div", { style: { display: "flex", alignItems: "center", gap: "20px", fontFamily: "Archivo", fontWeight: 800, fontSize: "40px", color: C.ink, letterSpacing: "-0.02em" } },
        h("div", { style: { width: "13px", height: "13px", backgroundColor: A } }), h("span", {}, f)))),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "12px" } },
      h("div", { style: { fontFamily: "Fira Code", fontSize: "20px", color: C.ink, backgroundColor: C.panel, border: `1px solid ${C.rule}`, borderRadius: "10px", padding: "16px 20px" } }, D.trust.install),
      h("div", { style: { fontFamily: "Fira Code", fontSize: "20px", color: C.soft } }, D.trust.foot)),
  ]);
}
function ogCard() {
  return h("div", { style: { width: "1200px", height: "630px", display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.bg, backgroundImage: `url(${DOT})`, backgroundRepeat: "repeat", color: C.ink, padding: "60px 64px", fontFamily: "Fira Sans" } },
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${C.rule}`, paddingBottom: "22px" } }, wordmark(28), eyebrow(D.eyebrow, 20)),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "20px" } },
      titleEl(D.og.title, D.og.accent, 66),
      h("div", { style: { fontFamily: "Fira Sans", fontWeight: 500, fontSize: "26px", lineHeight: 1.36, color: C.soft, maxWidth: "940px" } }, D.og.sub)),
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: "Fira Code", fontSize: "21px", borderTop: `1px solid ${C.rule}`, paddingTop: "22px" } },
      h("span", { style: { color: A } }, P.domain), h("span", { style: { color: C.subtle } }, D.og.footRight)));
}
function thumb() {
  return h("div", { style: { width: "240px", height: "240px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "16px", backgroundColor: C.bg, fontFamily: "Fira Code", border: `4px solid ${A}` } },
    wordmark(34), h("div", { style: { fontSize: "13px", color: C.subtle, letterSpacing: "0.2em" } }, D.thumb));
}

const jobs = [];
for (let i = 0; i < D.shots.length; i++) jobs.push([`slide-${i + 1}-shot.png`, shotSlide(D.shots[i], await dataURI(D.shots[i].file)), 1270, 760]);
jobs.push([`slide-how.png`, howSlide(), 1270, 760]);
jobs.push([`slide-trust.png`, trustSlide(), 1270, 760]);
jobs.push([`og-card.png`, ogCard(), 1200, 630]);
jobs.push([`thumbnail-240.png`, thumb(), 240, 240]);

const OUTDIR = `/tmp/${product}-gallery`;
await mkdir(OUTDIR, { recursive: true });
for (const [name, el, w, hgt] of jobs) {
  const svg = await satori(el, { width: w, height: hgt, fonts });
  const png = new Resvg(svg, { fitTo: { mode: "width", value: w } }).render().asPng();
  await writeFile(join(OUTDIR, name), png);
  console.log("rendered", name, `${w}x${hgt}`);
}
console.log("DONE →", OUTDIR);
