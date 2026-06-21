// gen_brand_gallery.mjs — REUSABLE per-product launch gallery on the locked
// data-editorial system (memory visual-system-locked + suite-accent-palette).
// One family, one accent per product: trovex=green, wrai.th=violet, yoru=amber.
// Run:  node growth/assets/_tools/gen_brand_gallery.mjs <product>   (default wraith)
//
// Honest: copy verbatim from the store (no fabrication). Screenshots must be
// client-safe (no client/project names) per memory confidentiality-no-client-names.
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
// shared family
const C = { bg: "#0c0d10", panel: "#101216", ink: "#f3f0e9", soft: "#8b8f98", subtle: "#74808f", rule: "#23262d" };
// per-product accent (suite-accent-palette, owner-locked)
const PRODUCTS = {
  trovex: { accent: "#22c55e", word: ["trovex"], domain: "trovex.dev" },
  wraith: { accent: "#6e6bf2", word: ["wrai", ".", "th"], domain: "tsukumo.ch/wraith" },
  yoru: { accent: "#f5a524", word: ["yoru"], domain: "tsukumo.ch/yoru" },
};
const h = (t, p, ...k) => ({ type: t, props: { ...p, children: k.length <= 1 ? k[0] : k } });

const product = process.argv[2] || "wraith";
const P = PRODUCTS[product];
const A = P.accent;
const OUT = join(HERE, "..", "launch", product === "wraith" ? "wraith" : product);
const dataURI = async (f) => `data:image/png;base64,${(await readFile(f)).toString("base64")}`;

function wordmark(fs) {
  const dot = P.word.length === 3; // wrai.th style
  return h("div", { style: { display: "flex", alignItems: "center", gap: dot ? "0" : "11px", fontFamily: "Fira Code", fontSize: `${fs}px`, color: C.ink } },
    dot ? null : h("div", { style: { width: `${Math.round(fs * 0.6)}px`, height: `${Math.round(fs * 0.6)}px`, backgroundColor: A, marginRight: "11px" } }),
    ...P.word.map((seg, i) => h("span", { style: { color: i === 1 && dot ? A : C.ink } }, seg)));
}
const eyebrow = (s, fs) => h("div", { style: { fontFamily: "Fira Code", fontSize: `${fs}px`, color: C.subtle, letterSpacing: "0.08em" } }, s);
// headline w/ accent substring
function titleEl(full, accent, fs) {
  const i = accent ? full.indexOf(accent) : -1;
  const segs = i === -1 ? [{ t: full, a: 0 }] : [{ t: full.slice(0, i), a: 0 }, { t: accent, a: 1 }, { t: full.slice(i + accent.length), a: 0 }];
  const words = [];
  for (const s of segs) for (const w of s.t.split(" ")) { if (w === "") continue; words.push({ w, a: s.a }); }
  return h("div", { style: { display: "flex", flexWrap: "wrap", fontFamily: "Archivo", fontWeight: 800, fontSize: `${fs}px`, lineHeight: 1.0, letterSpacing: "-0.035em", maxWidth: "1120px" } },
    ...words.map(({ w, a }) => h("span", { style: { color: a ? A : C.ink, marginRight: "0.24em" } }, w)));
}

function frame(w, hgt, kids, pad = 64) {
  return h("div", { style: { width: `${w}px`, height: `${hgt}px`, display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.bg, color: C.ink, padding: `${pad}px`, fontFamily: "Fira Sans", position: "relative" } },
    h("div", { style: { position: "absolute", top: 0, left: 0, width: "100%", height: "5px", backgroundColor: A } }), ...kids);
}

// slide-1 — mission control (real V2 board, client-safe band)
function shotSlide(titleFull, accent, eb, shotSrc) {
  return frame(1270, 760, [
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, wordmark(28), eyebrow(eb, 19)),
    titleEl(titleFull, accent, 54),
    h("div", { style: { display: "flex", border: `1px solid ${C.rule}`, borderRadius: "12px", overflow: "hidden", backgroundColor: C.panel } },
      h("img", { src: shotSrc, width: 1142, height: 386, style: { display: "block", objectFit: "cover" } })),
  ]);
}
// slide-4 — how it works (3 steps)
function howSlide() {
  const node = (n, t) => h("div", { style: { display: "flex", flexDirection: "column", gap: "14px", flex: 1, border: `1px solid ${C.rule}`, backgroundColor: C.panel, borderRadius: "10px", padding: "32px 28px" } },
    h("div", { style: { fontFamily: "Fira Code", fontSize: "20px", color: A } }, n),
    h("div", { style: { fontFamily: "Archivo", fontWeight: 800, fontSize: "30px", color: C.ink, lineHeight: 1.1, letterSpacing: "-0.02em" } }, t));
  const arrow = () => h("div", { style: { display: "flex", alignItems: "center", color: A, fontSize: "40px", padding: "0 6px" } }, "→");
  return frame(1270, 760, [
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, wordmark(28), eyebrow("how it works", 19)),
    titleEl("point any MCP agent at it, no rewrite", "no rewrite", 54),
    h("div", { style: { display: "flex", alignItems: "stretch" } }, node("01", "register your agents"), arrow(), node("02", "they message + share a task board"), arrow(), node("03", "watch the fleet from one dashboard")),
    h("div", { style: { fontFamily: "Fira Code", fontSize: "21px", color: C.soft } }, "Claude Code · Cursor · Windsurf · Zed — the control plane you point agents at, not a framework you rewrite into."),
  ]);
}
// slide-5 — trust (facts)
function trustSlide() {
  const facts = ["one Go binary, one SQLite file", "58 MCP tools, zero config", "100% local by default, no telemetry", "AGPL · v1.0 stable"];
  return frame(1270, 760, [
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, wordmark(28), eyebrow("what it is", 19)),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "18px" } },
      ...facts.map((f) => h("div", { style: { display: "flex", alignItems: "center", gap: "20px", fontFamily: "Archivo", fontWeight: 800, fontSize: "40px", color: C.ink, letterSpacing: "-0.02em" } },
        h("div", { style: { width: "13px", height: "13px", backgroundColor: A } }), h("span", {}, f)))),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "12px" } },
      h("div", { style: { fontFamily: "Fira Code", fontSize: "20px", color: C.ink, backgroundColor: C.panel, border: `1px solid ${C.rule}`, borderRadius: "10px", padding: "16px 20px" } }, "curl -fsSL https://raw.githubusercontent.com/TsukumoHQ/WRAI.TH/main/install.sh | bash"),
      h("div", { style: { fontFamily: "Fira Code", fontSize: "20px", color: C.soft } }, "github.com/TsukumoHQ/WRAI.TH · " + P.domain)),
  ]);
}
// og 1200x630
function ogCard() {
  return h("div", { style: { width: "1200px", height: "630px", display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.bg, color: C.ink, padding: "60px 64px", fontFamily: "Fira Sans" } },
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${C.rule}`, paddingBottom: "22px" } }, wordmark(28), eyebrow("the agent control plane", 20)),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "20px" } },
      titleEl("Mission control for your agent fleet.", "agent fleet.", 66),
      h("div", { style: { fontFamily: "Fira Sans", fontWeight: 500, fontSize: "26px", lineHeight: 1.36, color: C.soft, maxWidth: "940px" } }, "Persistent memory, messaging, and a shared task board over MCP. One Go binary, local, open source.")),
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: "Fira Code", fontSize: "21px", borderTop: `1px solid ${C.rule}`, paddingTop: "22px" } },
      h("span", { style: { color: A } }, P.domain), h("span", { style: { color: C.subtle } }, "v1.0 · 58 MCP tools · 100% local · AGPL")));
}
function thumb() {
  return h("div", { style: { width: "240px", height: "240px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "16px", backgroundColor: C.bg, fontFamily: "Fira Code", border: `4px solid ${A}` } },
    wordmark(34), h("div", { style: { fontSize: "13px", color: C.subtle, letterSpacing: "0.2em" } }, "CONTROL PLANE"));
}

const band = await dataURI("/tmp/fleet-v2-band.png");
const jobs = [
  ["slide-1-mission-control.png", shotSlide("Mission control for your agent fleet", "agent fleet", "LIVE · the real board", band), 1270, 760],
  ["slide-4-how-it-works.png", howSlide(), 1270, 760],
  ["slide-5-trust.png", trustSlide(), 1270, 760],
  ["og-card.png", ogCard(), 1200, 630],
  ["thumbnail-240.png", thumb(), 240, 240],
];
const only = process.argv[3]; // optional: render only filenames containing this
await mkdir(OUT, { recursive: true });
for (const [name, el, w, hgt] of jobs) {
  if (only && !name.includes(only)) continue;
  const svg = await satori(el, { width: w, height: hgt, fonts });
  const png = new Resvg(svg, { fitTo: { mode: "width", value: w } }).render().asPng();
  await writeFile(join("/tmp/wraith-gallery", name), png).catch(async () => { await mkdir("/tmp/wraith-gallery", { recursive: true }); await writeFile(join("/tmp/wraith-gallery", name), png); });
  console.log("rendered", name, `${w}x${hgt}`);
}
console.log("DONE");
