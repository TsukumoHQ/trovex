// gen_suite_map.mjs — one-screen suite map (1200x630) on the locked data-editorial
// system. Four pillars, each its OWN suite accent (suite-accent-palette):
// trovex=green, wrai.th=violet, yoru=amber, dokan=cyan. Honest one-liners only,
// real numbers only. dokan is 4th-pillar PREP -> carries an "in prep" tag (never
// implied live). Reusable on repo READMEs + /open-source.
//
// Run:  growth/assets/_tools/render.sh gen_suite_map.mjs --no-upload --out /tmp/suite
//   (or node directly with a node_modules symlink up-tree; writes suite-map.png)
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
const DOT = `data:image/svg+xml;base64,${Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44"><circle cx="2" cy="2" r="1.3" fill="#ffffff" fill-opacity="0.028"/></svg>').toString("base64")}`;
const h = (t, p, ...k) => ({ type: t, props: { ...p, children: k.length <= 1 ? k[0] : k } });

// word: array of [text, accent?] segments so wrai.th can color the dot only.
const PILLARS = [
  { word: [["trovex", 1]], accent: "#22c55e", role: "canonical context for coding agents", sub: "~60% fewer tokens per lookup" },
  { word: [["wrai", 1], [".", 1], ["th", 1]], accent: "#6e6bf2", role: "the agent control plane", sub: "messaging, memory, task board over MCP" },
  { word: [["yoru", 1]], accent: "#f59e0b", role: "the observability layer", sub: "see what your agents actually did" },
  { word: [["dokan", 1]], accent: "#22d3ee", role: "the script runtime", sub: "deterministic automation, zero LLM inside", tag: "in prep" },
];

function wordmark(segs, accent, fs) {
  return h("div", { style: { display: "flex", alignItems: "center", gap: "10px", fontFamily: "Fira Code", fontSize: `${fs}px`, color: C.ink } },
    h("div", { style: { width: `${Math.round(fs * 0.6)}px`, height: `${Math.round(fs * 0.6)}px`, backgroundColor: accent } }),
    h("div", { style: { display: "flex" } }, ...segs.map(([t, a]) => h("span", { style: { color: a ? accent : C.ink } }, t))));
}

function pillarCard(p) {
  const head = h("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between" } },
    wordmark(p.word, p.accent, 30),
    p.tag ? h("div", { style: { fontFamily: "Fira Code", fontSize: "15px", color: p.accent, border: `1px solid ${p.accent}`, borderRadius: "999px", padding: "3px 12px", opacity: 0.9 } }, p.tag) : h("div", {}));
  return h("div", { style: { display: "flex", flexDirection: "column", gap: "10px", flex: 1, backgroundColor: C.panel, border: `1px solid ${C.rule}`, borderLeft: `3px solid ${p.accent}`, borderRadius: "12px", padding: "26px 28px" } },
    head,
    h("div", { style: { fontFamily: "Archivo", fontWeight: 800, fontSize: "27px", color: C.ink, letterSpacing: "-0.02em", lineHeight: 1.08 } }, p.role),
    h("div", { style: { fontFamily: "Fira Sans", fontWeight: 500, fontSize: "19px", color: C.soft, lineHeight: 1.3 } }, p.sub));
}

function card() {
  const row = (a, b) => h("div", { style: { display: "flex", gap: "22px" } }, pillarCard(a), pillarCard(b));
  return h("div", { style: { width: "1200px", height: "630px", display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.bg, backgroundImage: `url(${DOT})`, backgroundRepeat: "repeat", padding: "52px 56px", fontFamily: "Fira Sans" } },
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${C.rule}`, paddingBottom: "18px" } },
      wordmark([["tsukumo", 0]], "#22c55e", 26),
      h("div", { style: { fontFamily: "Fira Code", fontSize: "18px", color: C.soft, letterSpacing: "0.04em" } }, "the stack we run our own agents on")),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "22px" } }, row(PILLARS[0], PILLARS[1]), row(PILLARS[2], PILLARS[3])),
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: `1px solid ${C.rule}`, paddingTop: "18px", fontFamily: "Fira Code", fontSize: "18px" } },
      h("div", { style: { color: C.subtle } }, "open source · dogfooded"),
      h("div", { style: { color: "#22c55e" } }, "tsukumo.ch")));
}

const args = process.argv.slice(2);
const outIdx = args.indexOf("--out");
const outDir = outIdx !== -1 ? args[outIdx + 1] : "/tmp/suite";
const svg = await satori(card(), { width: 1200, height: 630, fonts });
const png = new Resvg(svg, { fitTo: { mode: "width", value: 1200 } }).render().asPng();
await mkdir(outDir, { recursive: true });
await writeFile(join(outDir, "suite-map.png"), png);
console.log("rendered suite-map.png 1200x630 ->", outDir);
