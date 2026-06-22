// gen_answer_cards.mjs — trovex.dev /answers AEO OG cards (1200x630).
// VISUAL SYSTEM = data-editorial (memory visual-system-locked): brutalist Archivo
// display, dark #0c0d10, green = trovex's accent. The question carries the card (the
// real claim); trovex's one-line answer is the sub. No mood pills, no green-on-black slop.
// Honest: question + answer verbatim from the live /answers pages. No fabricated metrics.
//
// Writes web/public/answers/<slug>/og.png (each answer page's og:image meta).
// Deps (satori/resvg) resolve via a node_modules symlink up-tree.
// Run:  node growth/assets/_tools/gen_answer_cards.mjs
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "..", "..", "..", "web", "public", "answers");
const REPOFONT = join(HERE, "..", "_fonts");
const F = join(homedir(), "Library", "Fonts");
const fonts = [
  { name: "Archivo", data: await readFile(join(REPOFONT, "Archivo-800.ttf")), weight: 800, style: "normal" },
  { name: "Fira Sans", data: await readFile(join(F, "FiraSans-Medium.otf")), weight: 500, style: "normal" },
  { name: "Fira Code", data: await readFile(join(F, "FiraCode-Regular.ttf")), weight: 400, style: "normal" },
];
const C = { bg: "#0c0d10", ink: "#f3f0e9", soft: "#8b8f98", subtle: "#74808f", rule: "#23262d", green: "#22c55e" };
const DOT = `data:image/svg+xml;base64,${Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44"><circle cx="2" cy="2" r="1.3" fill="#ffffff" fill-opacity="0.028"/></svg>').toString("base64")}`;

const h = (t, p, ...k) => ({ type: t, props: { ...p, children: k.length <= 1 ? k[0] : k } });

// slug, question, accent (substring of question, green), answer
const CARDS = [
  ["bigger-context-window-rereading", "Does a bigger context window make rereading docs cheaper?", "context window", "No. The reread is paid every session, every agent. trovex serves one current doc per query instead."],
  ["canonical-context-for-agents", "What is canonical context for coding agents?", "canonical context", "The single current doc that answers a query: a path:line pointer with a freshness marker."],
  ["reduce-agent-token-costs", "How do I reduce the token cost of a coding agent's context?", "token cost", "Serve one canonical doc per query instead of rereading the repo to guess which file is current."],
  ["shared-source-of-truth-multiple-agents", "How do I keep multiple agents working from the same docs?", "same docs", "One shared trovex store: write once, and every agent and teammate reads the same canonical answer."],
  ["stop-agent-rereading-docs", "How do I stop my agent rereading the same files every session?", "every session", "Index once; trovex returns the one current section per query, not the whole repo."],
  ["agent-cost-rereading-files", "How much do AI agents spend rereading the same files?", "rereading", "A big slice of every session, paid per agent, per teammate. trovex serves one current doc per query instead."],
  ["mcp-server-for-repo-docs", "Is there an MCP server that serves a repo's docs to coding agents?", "MCP server", "Yes: trovex. It indexes your markdown and returns the one canonical doc per query, path:line + freshness, over MCP."],
  ["source-of-truth-multi-agent-repos", "What's the single source of truth for a multi-agent repo?", "source of truth", "One shared trovex store: every agent reads the same canonical doc, and writes back so nobody re-derives it."],
  ["why-agents-pick-stale-docs", "Why do AI coding agents pick stale or outdated docs?", "stale or outdated", "They guess from copies with no freshness signal. trovex marks each canonical, stale, or duplicate and serves the current one."],
  ["token-cost-of-agent-context", "What does context cost your coding agents?", "context cost", "Mostly rereading: 40–65% of lookup tokens go to re-finding the canonical file. trovex serves one current doc per query instead."],
  ["local-first-context-for-agents", "Can you give coding agents canonical context without a cloud?", "without a cloud", "Yes. trovex runs on your machine: SQLite vectors, ONNX embeddings, no API keys, no network. Your code never leaves."],
  ["why-context-files-dont-scale", "Why do AGENTS.md / CLAUDE.md context files stop scaling?", "stop scaling", "A file that helps at 5 docs hurts at 50. A 2026 ETH Zurich study found big context files cut agent task success and raised cost 20%+."],
];

const tfs = (s) => { const n = s.length; if (n > 58) return 52; if (n > 42) return 60; return 68; };
function titleEl(full, accent) {
  const i = accent ? full.indexOf(accent) : -1;
  const segs = i === -1 ? [{ t: full, a: 0 }] : [{ t: full.slice(0, i), a: 0 }, { t: accent, a: 1 }, { t: full.slice(i + accent.length), a: 0 }];
  const words = [];
  for (const s of segs) for (const w of s.t.split(" ")) { if (w === "") continue; words.push({ w, a: s.a }); }
  return h("div", { style: { display: "flex", flexWrap: "wrap", fontFamily: "Archivo", fontWeight: 800, fontSize: `${tfs(full)}px`, lineHeight: 1.0, letterSpacing: "-0.035em", maxWidth: "1080px" } },
    ...words.map(({ w, a }) => h("span", { style: { color: a ? C.green : C.ink, marginRight: "0.24em" } }, w)));
}
function card(q, accent, a) {
  return h("div", { style: { width: "1200px", height: "630px", display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.bg, backgroundImage: `url(${DOT})`, backgroundRepeat: "repeat", color: C.ink, padding: "58px 64px", fontFamily: "Fira Sans" } },
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${C.rule}`, paddingBottom: "20px" } },
      h("div", { style: { display: "flex", alignItems: "center", gap: "11px", fontFamily: "Fira Code", fontSize: "26px", color: C.ink } },
        h("div", { style: { width: "16px", height: "16px", backgroundColor: C.green } }), h("span", {}, "trovex")),
      h("div", { style: { fontFamily: "Fira Code", fontSize: "19px", color: C.subtle, letterSpacing: "0.05em" } }, "the answer")),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "20px" } },
      titleEl(q, accent),
      h("div", { style: { fontFamily: "Fira Sans", fontWeight: 500, fontSize: "26px", lineHeight: 1.38, color: C.soft, maxWidth: "980px" } }, a)),
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: "Fira Code", fontSize: "20px", borderTop: `1px solid ${C.rule}`, paddingTop: "20px" } },
      h("span", { style: { color: C.green } }, "trovex.dev/answers"),
      h("span", { style: { color: C.subtle } }, "the canonical doc store for coding agents")),
  );
}

for (const [slug, q, accent, a] of CARDS) {
  const svg = await satori(card(q, accent, a), { width: 1200, height: 630, fonts });
  const png = new Resvg(svg, { fitTo: { mode: "width", value: 1200 } }).render().asPng();
  const dir = join(OUT, slug);
  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, "og.png"), png);
  console.log("rendered", `answers/${slug}/og.png`);
}
console.log("DONE");
