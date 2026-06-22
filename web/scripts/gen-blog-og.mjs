// trovex.dev per-post blog OG cards (1200x630). Pure satori + resvg.
// VISUAL SYSTEM = data-editorial (memory visual-system-locked): brutalist Archivo
// display, dark #0c0d10, palette beyond green-on-black, green = trovex's accent
// (product surface). Headline carries the real post title; no mood labels, no chrome.
// Honest: real post titles verbatim from frontmatter; no fabricated metrics.
//
// Deps (satori/resvg) resolve via a node_modules symlink in this dir (see runner).
// Run:  node web/scripts/gen-blog-og.mjs
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const PUBLIC = join(HERE, "..", "public", "blog");
const REPOFONT = join(HERE, "..", "..", "growth", "assets", "_fonts");
const F = join(homedir(), "Library", "Fonts");
const fonts = [
  { name: "Archivo", data: await readFile(join(REPOFONT, "Archivo-800.ttf")), weight: 800, style: "normal" },
  { name: "Fira Sans", data: await readFile(join(F, "FiraSans-Medium.otf")), weight: 500, style: "normal" },
  { name: "Fira Code", data: await readFile(join(F, "FiraCode-Regular.ttf")), weight: 400, style: "normal" },
];
const C = { bg: "#0c0d10", ink: "#f3f0e9", soft: "#8b8f98", subtle: "#74808f", accent: "#22c55e", rule: "#23262d" };
const DOT = `data:image/svg+xml;base64,${Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44"><circle cx="2" cy="2" r="1.3" fill="#ffffff" fill-opacity="0.028"/></svg>').toString("base64")}`;

const h = (type, props, ...kids) => ({ type, props: { ...props, children: kids.length <= 1 ? kids[0] : kids } });

// [slug, preTitle, accentTitle] — accent is the green tail (trovex's accent).
const POSTS = [
  ["local-first-vs-cloud-rag-for-agent-context", "Local-first vs cloud RAG for serving your coding agents", "context"],
  ["mcp-context-patterns-for-coding-agents", "MCP context patterns for coding agents:", "dump, retrieve, or answer"],
  ["one-source-of-truth-for-a-fleet-of-agents", "One source of truth for", "a fleet of coding agents"],
  ["the-token-cost-of-agents-rereading-docs", "The token cost of coding agents", "rereading your docs"],
];

const tfs = (str) => { const n = str.length; if (n > 56) return 50; if (n > 40) return 58; return 66; };

function card(pre, accent) {
  const full = pre.replace(/\s+$/, "") + " " + accent;
  return h("div", { style: { width: "1200px", height: "630px", display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.bg, backgroundImage: `url(${DOT})`, backgroundRepeat: "repeat", color: C.ink, padding: "60px 64px", fontFamily: "Fira Sans" } },
    // header: wordmark + eyebrow, hairline under
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${C.rule}`, paddingBottom: "22px" } },
      h("div", { style: { display: "flex", alignItems: "center", gap: "12px", fontFamily: "Fira Code", fontSize: "26px", color: C.ink } },
        h("div", { style: { width: "16px", height: "16px", backgroundColor: C.accent } }), h("span", {}, "trovex")),
      h("div", { style: { fontFamily: "Fira Code", fontSize: "20px", color: C.subtle, letterSpacing: "0.04em" } }, "the blog")),
    // headline (Archivo display): pre ink + accent green, wraps
    h("div", { style: { display: "flex", flexWrap: "wrap", fontFamily: "Archivo", fontWeight: 800, fontSize: `${tfs(full)}px`, lineHeight: 1.0, letterSpacing: "-0.035em", maxWidth: "1060px" } },
      h("span", {}, pre.replace(/\s+$/, "") + " "),
      h("span", { style: { color: C.accent } }, accent)),
    // footer (mono), hairline above
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: "Fira Code", fontSize: "21px", borderTop: `1px solid ${C.rule}`, paddingTop: "22px" } },
      h("span", { style: { color: C.accent } }, "trovex.dev"),
      h("span", { style: { color: C.subtle } }, "the canonical doc store for your coding agents")),
  );
}

for (const [slug, pre, accent] of POSTS) {
  const svg = await satori(/** @type {any} */ (card(pre, accent)), { width: 1200, height: 630, fonts: /** @type {any} */ (fonts) });
  const png = new Resvg(svg, { fitTo: { mode: "width", value: 1200 } }).render().asPng();
  const dir = join(PUBLIC, slug);
  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, "og.png"), png);
  console.log("rendered", `${slug}/og.png`);
}
console.log("DONE");
