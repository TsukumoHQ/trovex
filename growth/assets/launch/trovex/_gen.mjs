// trovex OSS launch gallery (Show HN / Product Hunt). Built to launch-lead spec
// trovex:677a3af9 — slides 1,3,4,5 + OG + thumb are typographic/diagram (honest,
// no fake screenshots). Slide 2 (savings proof) shows the real ~60% number; a real
// /savings capture can replace it at the flip. Brand: trovex terminal-restraint —
// flat stage #06080d, green #22c55e, Fira. lowercase wordmark. No Synergix (repo
// URL is TsukumoHQ now). Honesty: only ~60%, real install cmd (not-on-PyPI yet).
//
// Run (deps symlinked):  node growth/assets/launch/trovex/_gen.mjs
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { readFile, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const F = join(homedir(), "Library", "Fonts");
const fonts = [
  { name: "Fira Sans", data: await readFile(join(F, "FiraSans-Bold.otf")), weight: 700, style: "normal" },
  { name: "Fira Code", data: await readFile(join(F, "FiraCode-Regular.ttf")), weight: 400, style: "normal" },
];
const C = { stage: "#06080d", card: "#11151f", elev: "#161b26", border: "#222a39", fg: "#e6edf3", muted: "#9aa6b8", subtle: "#74808f", faint: "#5a6577", accent: "#22c55e", red: "#ef4444" };
const h = (t, p, ...k) => ({ type: t, props: { ...p, children: k.length <= 1 ? k[0] : k } });
const REPO = "github.com/TsukumoHQ/trovex";

const wordmark = (fs = 28) => h("div", { style: { display: "flex", alignItems: "center", gap: "12px", fontFamily: "Fira Code", fontSize: `${fs}px`, color: C.fg } },
  h("div", { style: { width: `${fs * 0.6}px`, height: `${fs * 0.6}px`, backgroundColor: C.accent } }), h("span", {}, "trovex"));
const label = (s) => h("div", { style: { fontFamily: "Fira Code", fontSize: "19px", color: C.subtle, letterSpacing: "0.16em", textTransform: "uppercase" } }, s);
function frame(w, hgt, kids, pad = 72) {
  return h("div", { style: { width: `${w}px`, height: `${hgt}px`, display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.stage, color: C.fg, padding: `${pad}px`, fontFamily: "Fira Sans", position: "relative" } },
    h("div", { style: { position: "absolute", top: 0, left: 0, width: "100%", height: "5px", backgroundColor: C.accent } }), ...kids);
}
const head = (right) => h("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between" } }, wordmark(28), label(right));
const title = (parts, fs = 56) => h("div", { style: { display: "flex", flexWrap: "wrap", fontFamily: "Fira Sans", fontWeight: 700, fontSize: `${fs}px`, lineHeight: 1.08, letterSpacing: "-0.02em", maxWidth: "1120px" } }, ...parts);
const fg = (s) => h("span", { style: { marginRight: "0.28em" } }, s);
const grn = (s) => h("span", { style: { marginRight: "0.28em", color: C.accent } }, s);
const mono = (s, c, fs = 22) => h("div", { style: { fontFamily: "Fira Code", fontSize: `${fs}px`, color: c } }, s);

// 1 — HOOK (split before/after)
function slide1() {
  const fileRow = (n) => h("div", { style: { display: "flex", alignItems: "center", gap: "12px", fontFamily: "Fira Code", fontSize: "20px", color: C.faint } },
    h("div", { style: { width: "12px", height: "14px", border: `1px solid ${C.faint}` } }), h("span", {}, n));
  const panel = (kids) => h("div", { style: { display: "flex", flexDirection: "column", gap: "16px", flex: 1, border: `1px solid ${C.border}`, backgroundColor: C.card, borderRadius: "10px", padding: "30px 28px" } }, ...kids);
  return frame(1270, 760, [
    head("the hook"),
    title([fg("one current doc,"), grn("not a repo reread")], 58),
    h("div", { style: { display: "flex", gap: "28px", alignItems: "stretch" } },
      panel([
        mono("agent rereads the repo", C.muted, 21),
        ...["README.md", "docs/wiki.md", "ops/runbook.md", "postmortem.md", "CONTRIBUTING.md", "old-notes.md"].map(fileRow),
        h("div", { style: { fontFamily: "Fira Code", fontSize: "26px", color: C.red, marginTop: "6px" } }, "~720 tokens ↑"),
      ]),
      h("div", { style: { display: "flex", alignItems: "center", color: C.accent, fontSize: "40px", fontFamily: "Fira Sans" } }, "→"),
      panel([
        mono("trovex serves one", C.muted, 21),
        h("div", { style: { display: "flex", alignItems: "center", gap: "12px", fontFamily: "Fira Code", fontSize: "26px", color: C.accent, marginTop: "8px" } }, "ops/runbook.md:42"),
        h("div", { style: { display: "flex", alignSelf: "flex-start", fontFamily: "Fira Code", fontSize: "18px", color: C.accent, border: `1px solid ${C.accent}`, borderRadius: "6px", padding: "5px 12px", letterSpacing: "0.08em" } }, "CANONICAL"),
        h("div", { style: { fontFamily: "Fira Code", fontSize: "26px", color: C.accent, marginTop: "auto" } }, "~280 tokens"),
      ])),
    mono("the contrast is the pitch — six files vs one current pointer", C.subtle, 19),
  ]);
}
// 2 — PROOF (savings receipt)
function slide2() {
  return frame(1270, 760, [
    head("the proof"),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "6px" } },
      h("div", { style: { fontFamily: "Fira Sans", fontWeight: 700, fontSize: "230px", lineHeight: 0.9, letterSpacing: "-8px", color: C.accent } }, "~60%"),
      h("div", { style: { fontFamily: "Fira Sans", fontWeight: 700, fontSize: "52px", color: C.fg } }, "fewer tokens per doc lookup")),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "10px" } },
      mono("measured on your repo — trovex ships a savings view to check your own", C.muted, 24),
      mono("trovex.dev/savings", C.accent, 24)),
  ]);
}
// 3 — HOW IT WORKS
function slide3() {
  const node = (n, t) => h("div", { style: { display: "flex", flexDirection: "column", gap: "12px", flex: 1, border: `1px solid ${C.border}`, backgroundColor: C.card, borderRadius: "10px", padding: "28px 24px" } },
    mono(n, C.accent, 20), h("div", { style: { fontFamily: "Fira Sans", fontWeight: 700, fontSize: "27px", color: C.fg, lineHeight: 1.15 } }, t));
  const arrow = () => h("div", { style: { display: "flex", alignItems: "center", color: C.accent, fontSize: "40px", padding: "0 6px" } }, "→");
  return frame(1270, 760, [
    head("how it works"),
    title([fg("index your repo "), grn("→"), fg(" agent asks "), grn("trovex(q)"), fg(" "), grn("→"), fg(" one doc + freshness")], 50),
    h("div", { style: { display: "flex", alignItems: "stretch" } }, node("01", "index your repo"), arrow(), node("02", "agent asks trovex(q)"), arrow(), node("03", "one doc + freshness marker")),
    mono("local: SQLite + on-device embeddings (ONNX/fastembed) · no cloud, no API keys", C.muted, 21),
  ]);
}
// 4 — SOURCE OF TRUTH
function slide4() {
  const agent = (n) => h("div", { style: { display: "flex", alignItems: "center", justifyContent: "center", width: "200px", height: "84px", border: `1px solid ${C.border}`, backgroundColor: C.card, borderRadius: "10px", fontFamily: "Fira Code", fontSize: "22px", color: C.fg } }, n);
  return frame(1270, 760, [
    head("source of truth"),
    title([fg("one shared store, so agents + teammates"), grn("stop re-deriving")], 52),
    h("div", { style: { display: "flex", alignItems: "center", gap: "32px" } },
      h("div", { style: { display: "flex", flexDirection: "column", gap: "18px" } }, agent("agent A"), agent("agent B"), agent("teammate")),
      h("div", { style: { display: "flex", flexDirection: "column", alignItems: "center", color: C.accent, fontFamily: "Fira Code", fontSize: "18px" } },
        mono("trovex_write →", C.accent, 18), h("div", { style: { fontSize: "40px" } }, "⇄"), mono("← trovex_read", C.accent, 18)),
      h("div", { style: { display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "8px", width: "330px", height: "300px", border: `1.5px solid ${C.accent}`, backgroundColor: "rgba(34,197,94,0.06)", borderRadius: "12px" } },
        wordmark(30), mono("one store", C.muted, 22), mono("SQLite · local", C.subtle, 18))),
    mono("incidents, decisions, the rollback that worked — written once, read by all", C.muted, 21),
  ]);
}
// 5 — TRUST CLOSE
function slide5() {
  const facts = ["local-first — runs on your machine", "SQLite + on-device ONNX embeddings", "no cloud, no API keys", "AGPL core / MIT CLI · MCP-native"];
  return frame(1270, 760, [
    head("what it is"),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "16px" } },
      ...facts.map((f) => h("div", { style: { display: "flex", alignItems: "center", gap: "20px", fontFamily: "Fira Sans", fontWeight: 700, fontSize: "40px", color: C.fg } },
        h("div", { style: { width: "13px", height: "13px", backgroundColor: C.accent } }), h("span", {}, f)))),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "14px" } },
      h("div", { style: { fontFamily: "Fira Code", fontSize: "21px", color: C.accent, border: `1px solid ${C.border}`, backgroundColor: C.card, borderRadius: "10px", padding: "18px 22px" } }, "uvx trovex"),
      mono(REPO + " · public beta", C.muted, 20)),
  ]);
}
// OG card (1200x630)
function og() {
  return frame(1200, 630, [
    wordmark(32),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "24px" } },
      title([fg("one canonical doc for your"), grn("coding agents")], 62),
      mono("~60% fewer tokens per lookup. local-first, open source.", C.muted, 27)),
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } },
      mono(REPO, C.accent, 21), mono("AGPL core / MIT CLI · MCP-native", C.subtle, 20)),
  ], 72);
}
// thumbnail (240x240)
function thumb() {
  return h("div", { style: { width: "240px", height: "240px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "14px", backgroundColor: C.stage, fontFamily: "Fira Code", border: `4px solid ${C.accent}` } },
    h("div", { style: { width: "44px", height: "44px", backgroundColor: C.accent } }),
    h("div", { style: { fontSize: "40px", color: C.fg } }, "trovex"),
    h("div", { style: { fontSize: "13px", color: C.muted, letterSpacing: "0.2em" } }, "CONTEXT"));
}

const jobs = [
  ["slide-1-hook.png", slide1(), 1270, 760],
  ["slide-2-proof.png", slide2(), 1270, 760],
  ["slide-3-how-it-works.png", slide3(), 1270, 760],
  ["slide-4-source-of-truth.png", slide4(), 1270, 760],
  ["slide-5-trust.png", slide5(), 1270, 760],
  ["og-card.png", og(), 1200, 630],
  ["thumbnail-240.png", thumb(), 240, 240],
];
for (const [name, el, w, hgt] of jobs) {
  const svg = await satori(el, { width: w, height: hgt, fonts });
  const png = new Resvg(svg, { fitTo: { mode: "width", value: w } }).render().asPng();
  await writeFile(join(HERE, name), png);
  console.log("rendered", name, `${w}x${hgt}`);
}
console.log("DONE");
