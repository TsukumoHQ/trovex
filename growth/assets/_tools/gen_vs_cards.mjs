// gen_vs_cards.mjs — trovex.dev /vs/<slug> comparison OG cards (1200x630).
// VISUAL SYSTEM = data-editorial (memory visual-system-locked): brutalist Archivo
// display, dark #0c0d10. The COMPARISON is the design — a 2-column table (the other
// tool muted, trovex green). Fair + honest: each card credits where the other tool is
// the right choice (matches the page's "when to use X"). Real ~60% only. green=trovex.
//
// Writes web/public/vs/<slug>/og.png (each /vs page's og:image meta).
// Deps (satori/resvg) resolve via a node_modules symlink up-tree.
// Run:  node growth/assets/_tools/gen_vs_cards.mjs
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "..", "..", "..", "web", "public", "vs");
const REPOFONT = join(HERE, "..", "_fonts");
const F = join(homedir(), "Library", "Fonts");
const fonts = [
  { name: "Archivo", data: await readFile(join(REPOFONT, "Archivo-800.ttf")), weight: 800, style: "normal" },
  { name: "Fira Sans", data: await readFile(join(F, "FiraSans-Medium.otf")), weight: 500, style: "normal" },
  { name: "Fira Code", data: await readFile(join(F, "FiraCode-Regular.ttf")), weight: 400, style: "normal" },
];
const C = { bg: "#0c0d10", ink: "#f3f0e9", soft: "#8b8f98", subtle: "#74808f", rule: "#23262d", green: "#22c55e" };
const h = (t, p, ...k) => ({ type: t, props: { ...p, children: k.length <= 1 ? k[0] : k } });

// slug, titleRight (after "trovex vs "), leftHead, rows [[left,right,greenSub?]...], footer (fair credit)
const CARDS = [
  ["context-hub", "context-hub", "chunk-retrieval server", [["a ranked list of chunks", "one canonical doc"], ["you pick from candidates", "one current answer, path:line"], ["no freshness signal", "canonical / stale markers", "~60% fewer tokens per lookup"]], "A general retrieval server fits broad search. trovex answers which repo doc is current."],
  ["cursor-memory", "Cursor memory", "Cursor memory / rules", [["editor-locked rules", "portable across MCP clients"], ["Cursor only", "Claude Code, Cursor, Windsurf, Zed"], ["hand-written rules", "indexed docs + freshness", "~60% fewer tokens per lookup"]], "Cursor memory is great inside Cursor. trovex travels with your repo."],
  ["mem0", "mem0", "mem0", [["remembers conversations", "serves your repo's docs"], ["user / agent memory", "one canonical doc per query"], ["general memory layer", "repo SSOT + freshness", "~60% fewer tokens per lookup"]], "mem0 is great for conversational memory. trovex for your repo's canonical docs."],
  ["vector-db-rag", "a vector-DB RAG setup", "vector-DB RAG (DIY)", [["a pipeline you build", "turnkey, runs on your machine"], ["embed + chunk + rank yourself", "index once, ask, get one doc"], ["returns a set of chunks", "one canonical answer + freshness", "~60% fewer tokens per lookup"]], "A custom RAG stack fits bespoke needs. trovex for repo docs out of the box."],
  ["continue", "Continue.dev", "Continue.dev", [["a full in-IDE assistant", "a context source you plug in"], ["brings its own retrieval", "one canonical doc per query"], ["broad chat + edit workflow", "path:line + freshness", "~60% fewer tokens per lookup"]], "Continue is the assistant; trovex is the canonical-doc source you plug into it."],
  ["aider", "Aider", "Aider", [["a coding agent with a repo map", "a canonical-doc server"], ["maps the repo to make edits", "returns the one current doc"], ["repo map in context", "just the section that answers", "~60% fewer tokens per lookup"]], "Aider is great for editing; trovex for which doc is canonical and current."],
  ["cody", "Sourcegraph Cody", "Sourcegraph Cody", [["enterprise code search", "local canonical docs"], ["searches code across many repos", "one current doc per query"], ["cloud / org-scale", "local-first, on your machine", "~60% fewer tokens per lookup"]], "Cody is great for org-wide code search; trovex for a repo's canonical docs."],
  ["pieces", "Pieces", "Pieces", [["personal workflow memory", "a repo's canonical docs"], ["snippets across your tools", "one current doc, path:line"], ["per-developer memory", "shared repo source of truth", "~60% fewer tokens per lookup"]], "Pieces is great for personal workflow memory; trovex for the repo's docs."],
  ["claude-projects", "Claude Projects", "Claude Projects", [["uploaded static knowledge", "a live repo over MCP"], ["manual re-upload to update", "always current + freshness"], ["Claude.ai only", "any MCP client, runs locally", "~60% fewer tokens per lookup"]], "Claude Projects is great for uploaded refs; trovex for live repo docs."],
];

function row(left, right, sub, head) {
  const lc = head ? C.soft : C.soft, rc = head ? C.green : C.ink;
  const lf = head ? "Fira Code" : "Fira Sans", rf = head ? "Fira Code" : "Fira Sans";
  return h("div", { style: { display: "flex", alignItems: "flex-start", paddingTop: head ? "0" : "20px" } },
    h("div", { style: { display: "flex", flex: 1, paddingRight: "28px", fontFamily: lf, fontSize: head ? "21px" : "27px", color: lc } }, left),
    h("div", { style: { display: "flex", flexDirection: "column", flex: 1, paddingLeft: "32px", borderLeft: `1px solid ${C.rule}` } },
      h("div", { style: { fontFamily: rf, fontSize: head ? "21px" : "27px", color: rc, fontWeight: head ? 400 : 500 } }, right),
      sub ? h("div", { style: { fontFamily: "Fira Code", fontSize: "20px", color: C.green, marginTop: "8px" } }, sub) : null));
}

function card(titleRight, leftHead, rows, footer) {
  return h("div", { style: { width: "1200px", height: "630px", display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.bg, color: C.ink, padding: "52px 64px", fontFamily: "Fira Sans" } },
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } },
      h("div", { style: { display: "flex", alignItems: "center", gap: "11px", fontFamily: "Fira Code", fontSize: "24px", color: C.ink } },
        h("div", { style: { width: "15px", height: "15px", backgroundColor: C.green } }), h("span", {}, "trovex")),
      h("div", { style: { fontFamily: "Fira Code", fontSize: "19px", color: C.subtle, letterSpacing: "0.05em" } }, "the comparison")),
    h("div", { style: { display: "flex", fontFamily: "Archivo", fontWeight: 800, fontSize: "46px", letterSpacing: "-0.03em", color: C.ink } },
      h("span", { style: { marginRight: "0.28em" } }, "trovex"), h("span", { style: { marginRight: "0.28em", color: C.subtle } }, "vs"), h("span", {}, titleRight)),
    h("div", { style: { display: "flex", flexDirection: "column", borderTop: `1px solid ${C.rule}`, paddingTop: "22px" } },
      row(leftHead, "trovex", null, true),
      h("div", { style: { display: "flex", flexDirection: "column", marginTop: "10px" } }, ...rows.map((r) => row(r[0], r[1], r[2], false)))),
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: "Fira Code", fontSize: "19px", borderTop: `1px solid ${C.rule}`, paddingTop: "20px" } },
      h("div", { style: { color: C.soft, fontFamily: "Fira Sans", maxWidth: "1000px" } }, footer),
      h("div", { style: { color: C.green } }, "trovex.dev")),
  );
}

for (const [slug, titleRight, leftHead, rows, footer] of CARDS) {
  const svg = await satori(card(titleRight, leftHead, rows, footer), { width: 1200, height: 630, fonts });
  const png = new Resvg(svg, { fitTo: { mode: "width", value: 1200 } }).render().asPng();
  const dir = join(OUT, slug);
  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, "og.png"), png);
  console.log("rendered", `vs/${slug}/og.png`);
}
console.log("DONE");
