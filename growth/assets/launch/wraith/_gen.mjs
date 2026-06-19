// wrai.th launch gallery — typographic/diagram slides (NO screenshot needed).
// Brand: wrai.th's OWN identity (NOT tsukumo acid). Palette pulled from the live
// v2 dashboard (internal/web/static/v2/v2.css): dark ink, emerald accent, mono.
// Honesty gate: facts verbatim from the asset-spec copy bank; no fabricated
// metrics/logos. Screenshot slides (1-3) are captured by a human from the live
// dashboard — see CAPTURE-BRIEF.md.
//
// Run:  NODE_PATH=/tmp/og-preview/node_modules node growth/assets/launch/wraith/_gen.mjs
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
// Space Mono ttf lives in the tsukumo clone's og dir; reuse it as the mono face.
const monoPath = "/tmp/tsukumo-design/src/og/SpaceMono-Regular.ttf";
const mono = await readFile(monoPath);
const fonts = [{ name: "Space Mono", data: mono, weight: 400, style: "normal" }];

const W = { bg: "#0a0c10", card: "#10131a", elev: "#161a23", border: "#1d2230", text: "#e6e9ef", muted: "#6b7385", dim: "#424a5c", accent: "#4ade80", violet: "#a78bfa", blue: "#60a5fa" };
const h = (type, props, ...kids) => ({ type, props: { ...props, children: kids.length <= 1 ? kids[0] : kids } });

// wrai.th wordmark — dot in accent.
const wordmark = (fs = 30) => h("div", { style: { display: "flex", alignItems: "baseline", fontFamily: "Space Mono", fontSize: `${fs}px`, color: W.text, letterSpacing: "-0.02em" } },
  h("span", {}, "wrai"), h("span", { style: { color: W.accent } }, "."), h("span", {}, "th"));

const frame = (w, hgt, kids, pad = 72) => h("div", { style: { width: `${w}px`, height: `${hgt}px`, display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: W.bg, color: W.text, padding: `${pad}px`, fontFamily: "Space Mono", position: "relative" } },
  h("div", { style: { position: "absolute", top: 0, left: 0, width: "100%", height: "5px", backgroundColor: W.accent } }),
  ...kids);

// ---- Slides 1-3 — REAL /v2/ dashboard captures, composited into branded frames.
// Raws are human-captured from a clean throwaway "wraith-demo" colony (PR #226),
// leak-verified zero client/Synergix names. Honesty gate: real run, real data.
const dataURI = async (file) => `data:image/png;base64,${(await readFile(join(HERE, file))).toString("base64")}`;

// Fixed screenshot box (all raws are 2540x1520 → 1.671 aspect). Height-locked so
// the three slides sit uniformly; width derived from the real aspect.
const SHOT_H = 470;
const SHOT_W = Math.round((SHOT_H * 2540) / 1520); // 785

function screenSlide(parts, src) {
  // parts = [pre, accent, post] of the verbatim caption (accent = emerald span).
  const [pre, accent, post] = parts;
  return h("div", { style: { width: "1270px", height: "760px", display: "flex", flexDirection: "column", backgroundColor: W.bg, color: W.text, padding: "56px", fontFamily: "Space Mono", position: "relative" } },
    h("div", { style: { position: "absolute", top: 0, left: 0, width: "100%", height: "5px", backgroundColor: W.accent } }),
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } },
      wordmark(26),
      h("div", { style: { fontSize: "19px", color: W.muted, letterSpacing: "0.16em" } }, "LIVE · /v2/")),
    h("div", { style: { display: "flex", flexWrap: "wrap", marginTop: "22px", fontSize: "38px", lineHeight: 1.14, color: W.text, maxWidth: "1110px" } },
      h("span", {}, pre.replace(/\s+$/, "\u00a0")), h("span", { style: { color: W.accent } }, accent), post ? h("span", {}, "\u00a0" + post) : null),
    h("div", { style: { display: "flex", flex: 1, alignItems: "center", justifyContent: "center", marginTop: "26px" } },
      h("div", { style: { display: "flex", border: `1px solid ${W.border}`, borderRadius: "12px", overflow: "hidden", backgroundColor: W.card } },
        h("img", { src, width: SHOT_W, height: SHOT_H, style: { display: "block" } }))));
}

// ---- Slide 4 — HOW IT WORKS (3-step flow) ----
function slide4() {
  const node = (n, label) => h("div", { style: { display: "flex", flexDirection: "column", gap: "14px", flex: 1, border: `1px solid ${W.border}`, backgroundColor: W.card, borderRadius: "10px", padding: "30px 26px" } },
    h("div", { style: { fontSize: "20px", color: W.accent } }, n),
    h("div", { style: { fontSize: "30px", lineHeight: 1.15, color: W.text } }, label));
  const arrow = () => h("div", { style: { display: "flex", alignItems: "center", color: W.accent, fontSize: "44px", padding: "0 8px" } }, "→");
  return frame(1270, 760, [
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, wordmark(28), h("div", { style: { fontSize: "20px", color: W.muted } }, "how it works")),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "44px" } },
      h("div", { style: { display: "flex", flexWrap: "wrap", fontSize: "54px", lineHeight: 1.1, color: W.text, maxWidth: "1000px" } },
        h("span", {}, "register agents "), h("span", { style: { color: W.accent } }, "→"), h("span", {}, " they coordinate over MCP "), h("span", { style: { color: W.accent } }, "→"), h("span", {}, " one dashboard")),
      h("div", { style: { display: "flex", alignItems: "stretch" } }, node("01", "register agents"), arrow(), node("02", "coordinate over MCP"), arrow(), node("03", "one dashboard"))),
    h("div", { style: { fontSize: "22px", color: W.muted } }, "works with Claude Code · Cursor · Windsurf"),
  ]);
}

// ---- Slide 5 — TRUST CLOSE (typographic) ----
function slide5() {
  const facts = ["one Go binary", "one SQLite file", "58 MCP tools", "100% local · no telemetry", "AGPL"];
  return frame(1270, 760, [
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, wordmark(28), h("div", { style: { fontSize: "20px", color: W.muted } }, "what it is")),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "18px" } },
      ...facts.map((f) => h("div", { style: { display: "flex", alignItems: "center", gap: "20px", fontSize: "46px", color: W.text } },
        h("div", { style: { width: "14px", height: "14px", backgroundColor: W.accent } }), h("span", {}, f)))),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "18px" } },
      h("div", { style: { fontSize: "21px", color: W.accent, border: `1px solid ${W.border}`, backgroundColor: W.card, borderRadius: "10px", padding: "18px 22px" } },
        "curl -fsSL https://raw.githubusercontent.com/Synergix-lab/WRAI.TH/main/install.sh | bash"),
      h("div", { style: { fontSize: "20px", color: W.muted } }, "github.com/Synergix-lab/WRAI.TH")),
  ]);
}

// ---- OG / social card (1200x630) ----
function og() {
  return frame(1200, 630, [
    wordmark(34),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "26px" } },
      h("div", { style: { display: "flex", flexWrap: "wrap", fontSize: "62px", lineHeight: 1.08, color: W.text, maxWidth: "1020px" } },
        h("span", {}, "mission control for your\u00a0"), h("span", { style: { color: W.accent } }, "AI agent fleet")),
      h("div", { style: { fontSize: "27px", color: W.muted } }, "memory · messaging · tasks · one dashboard. local, open source.")),
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } },
      h("div", { style: { fontSize: "21px", color: W.accent } }, "github.com/Synergix-lab/WRAI.TH"),
      h("div", { style: { fontSize: "20px", color: W.muted } }, "AGPL · MCP-native")),
  ], 72);
}

// ---- Product thumbnail (240x240) ----
function thumb() {
  return h("div", { style: { width: "240px", height: "240px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "12px", backgroundColor: W.bg, fontFamily: "Space Mono", border: `4px solid ${W.accent}` } },
    h("div", { style: { display: "flex", alignItems: "baseline", fontSize: "44px", color: W.text, letterSpacing: "-0.02em" } },
      h("span", {}, "wrai"), h("span", { style: { color: W.accent } }, "."), h("span", {}, "th")),
    h("div", { style: { fontSize: "13px", color: W.muted, letterSpacing: "0.18em" } }, "AGENT FLEET"));
}

const jobs = [
  ["slide-1-mission-control.png", screenSlide(["mission control for your ", "AI agent fleet"], await dataURI("raw-slide-1-overview.png")), 1270, 760],
  ["slide-2-coordination.png", screenSlide(["agents that message each other + ", "share one task board"], await dataURI("raw-slide-2-messages.png")), 1270, 760],
  ["slide-3-memory.png", screenSlide(["persistent memory that ", "survives /clear"], await dataURI("raw-slide-3-memory.png")), 1270, 760],
  ["slide-4-how-it-works.png", slide4(), 1270, 760],
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
