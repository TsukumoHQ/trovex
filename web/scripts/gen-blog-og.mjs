// trovex.dev per-post blog OG cards (1200x630). Pure satori + resvg.
// Brand: trovex terminal-restraint — flat stage #06080d (NO glow/grid — brutalist-min
// per the 4-site audit), green #22c55e accent used once, Fira. Honest: real post
// titles verbatim from growth/blog frontmatter; no fabricated metrics.
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
const F = join(homedir(), "Library", "Fonts");
const fonts = [
  { name: "Fira Sans", data: await readFile(join(F, "FiraSans-Bold.otf")), weight: 700, style: "normal" },
  { name: "Fira Code", data: await readFile(join(F, "FiraCode-Regular.ttf")), weight: 400, style: "normal" },
];

// trovex tokens (web/src/index.css)
const C = { stage: "#06080d", fg: "#e6edf3", muted: "#9aa6b8", subtle: "#74808f", accent: "#22c55e", border: "rgba(148,163,184,0.14)" };
const h = (type, props, ...kids) => ({ type, props: { ...props, children: kids.length <= 1 ? kids[0] : kids } });

// 3 newest trovex blog posts. [slug, preTitle, accentTitle] — accent is the green tail.
// nbsp join ( ) on the pre span: satori collapses whitespace at flex-item boundaries.
const POSTS = [
  ["local-first-vs-cloud-rag-for-agent-context", "Local-first vs cloud RAG for serving your coding agents", "context"],
  ["mcp-context-patterns-for-coding-agents", "MCP context patterns for coding agents:", "dump, retrieve, or answer"],
  ["one-source-of-truth-for-a-fleet-of-agents", "One source of truth for", "a fleet of coding agents"],
  ["the-token-cost-of-agents-rereading-docs", "The token cost of coding agents", "rereading your docs"],
];

function card(pre, accent) {
  return h("div", { style: { width: "1200px", height: "630px", display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.stage, color: C.fg, padding: "64px", fontFamily: "Fira Sans" } },
    // wordmark row (mono)
    h("div", { style: { display: "flex", alignItems: "center", gap: "12px", fontFamily: "Fira Code", fontSize: "26px", color: C.fg } },
      h("div", { style: { width: "16px", height: "16px", backgroundColor: C.accent } }),
      h("span", {}, "trovex")),
    // headline: pre (fg) + accent (green), nbsp-joined, wraps
    h("div", { style: { display: "flex", flexWrap: "wrap", fontSize: "62px", fontWeight: 700, lineHeight: 1.08, letterSpacing: "-0.02em", maxWidth: "1040px" } },
      h("span", {}, pre.replace(/\s+$/, "") + " "),
      h("span", { style: { color: C.accent } }, accent)),
    // footer (mono)
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: "Fira Code", fontSize: "21px" } },
      h("span", { style: { color: C.accent } }, "trovex.dev"),
      h("span", { style: { color: C.subtle } }, "the canonical doc store for your coding agents")),
  );
}

for (const [slug, pre, accent] of POSTS) {
  const svg = await satori(card(pre, accent), { width: 1200, height: 630, fonts });
  const png = new Resvg(svg, { fitTo: { mode: "width", value: 1200 } }).render().asPng();
  const dir = join(PUBLIC, slug);
  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, "og.png"), png);
  console.log("rendered", `${slug}/og.png`);
}
console.log("DONE");
