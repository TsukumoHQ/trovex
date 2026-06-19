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
        h("span", {}, "mission control for your "), h("span", { style: { color: W.accent } }, "AI agent fleet")),
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
