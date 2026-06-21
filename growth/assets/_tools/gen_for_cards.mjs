// gen_for_cards.mjs — trovex.dev /for/<agent> OG cards (1200x630).
// VISUAL SYSTEM = data-editorial (memory visual-system-locked): brutalist Archivo
// display, dark #0c0d10, green = trovex's accent. POSITIONING = PUBLIC-BETA (the old
// 'private beta' framing is banned). Honest: real ~60% only; real MCP wiring per agent.
//
// Writes web/public/for/<slug>/og.png (each /for page's og:image meta).
// Deps (satori/resvg) resolve via a node_modules symlink up-tree.
// Run:  node growth/assets/_tools/gen_for_cards.mjs
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "..", "..", "..", "web", "public", "for");
const REPOFONT = join(HERE, "..", "_fonts");
const F = join(homedir(), "Library", "Fonts");
const fonts = [
  { name: "Archivo", data: await readFile(join(REPOFONT, "Archivo-800.ttf")), weight: 800, style: "normal" },
  { name: "Fira Sans", data: await readFile(join(F, "FiraSans-Medium.otf")), weight: 500, style: "normal" },
  { name: "Fira Code", data: await readFile(join(F, "FiraCode-Regular.ttf")), weight: 400, style: "normal" },
];
const C = { bg: "#0c0d10", panel: "#101216", ink: "#f3f0e9", soft: "#8b8f98", subtle: "#74808f", rule: "#23262d", green: "#22c55e" };
const h = (t, p, ...k) => ({ type: t, props: { ...p, children: k.length <= 1 ? k[0] : k } });

// slug, agent, mechanism sub, MCP wiring line
const CARDS = [
  ["claude-code", "Claude Code", "One canonical doc per query, not a CLAUDE.md reread of the whole repo.", "point Claude Code at trovex over MCP"],
  ["cursor", "Cursor", "One canonical doc per query, not a whole-repo reread.", "add to .cursor/mcp.json"],
  ["windsurf", "Windsurf", "One canonical doc per query, not a whole-repo reread.", "add to mcp_config.json"],
  ["cline", "Cline", "One canonical doc per query, not a whole-repo reread.", "add a remote MCP server in the MCP Servers panel"],
];

function card(agent, sub, connect) {
  return h("div", { style: { width: "1200px", height: "630px", display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.bg, color: C.ink, padding: "58px 64px", fontFamily: "Fira Sans" } },
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${C.rule}`, paddingBottom: "20px" } },
      h("div", { style: { display: "flex", alignItems: "center", gap: "11px", fontFamily: "Fira Code", fontSize: "26px", color: C.ink } },
        h("div", { style: { width: "16px", height: "16px", backgroundColor: C.green } }), h("span", {}, "trovex")),
      h("div", { style: { fontFamily: "Fira Code", fontSize: "19px", color: C.subtle, letterSpacing: "0.05em" } }, "via MCP")),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "22px" } },
      h("div", { style: { display: "flex", flexWrap: "wrap", fontFamily: "Archivo", fontWeight: 800, fontSize: "72px", lineHeight: 1.0, letterSpacing: "-0.035em" } },
        h("span", { style: { marginRight: "0.24em" } }, "trovex for"), h("span", { style: { color: C.green } }, agent)),
      h("div", { style: { fontFamily: "Fira Sans", fontWeight: 500, fontSize: "27px", lineHeight: 1.36, color: C.soft, maxWidth: "980px" } }, sub),
      h("div", { style: { display: "flex", alignSelf: "flex-start", fontFamily: "Fira Code", fontSize: "21px", color: C.ink, backgroundColor: C.panel, border: `1px solid ${C.rule}`, borderRadius: "8px", padding: "12px 18px" } }, connect)),
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: "Fira Code", fontSize: "20px", borderTop: `1px solid ${C.rule}`, paddingTop: "20px" } },
      h("span", { style: { color: C.subtle } }, "~60% fewer tokens per lookup · public beta"),
      h("span", { style: { color: C.green } }, "trovex.dev")),
  );
}

for (const [slug, agent, sub, connect] of CARDS) {
  const svg = await satori(card(agent, sub, connect), { width: 1200, height: 630, fonts });
  const png = new Resvg(svg, { fitTo: { mode: "width", value: 1200 } }).render().asPng();
  const dir = join(OUT, slug);
  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, "og.png"), png);
  console.log("rendered", `for/${slug}/og.png`);
}
console.log("DONE");
