#!/usr/bin/env node
/**
 * GEO citation-share monitor — measure AI-engine citations of the suite DIRECTLY.
 *
 * AI engines strip referrers, so our Plausible GEO attribution is a floor. This probes the
 * ICP's real questions through an AI search engine, reads back the actual citations, and
 * records whether trovex / tsukumo / the suite is cited — turning the GEO bet into a real,
 * weekly, trendable metric. Top-1% AEO practice: measure citation share at the source.
 *
 * Engine: OpenAI Responses API + web_search (a real AI-search surface, ~ChatGPT-with-search).
 * Perplexity / Google AI Overviews are designed-for but need their own keys (see TODO).
 *
 * Honesty: AI answers are NON-DETERMINISTIC (vary by run/region/personalization). This is a
 * SAMPLED SNAPSHOT, never a guaranteed rank. We log exactly what the API returns — no
 * fabrication. Run weekly; the trend matters more than any single run.
 *
 * Keys: reads OPENAI_API_KEY from the environment only (load out-of-git, e.g.
 *   set -a; . ~/.config/trovex-growth/openai.env; set +a
 * Never hardcode/commit a key; the output contains only domains + counts, no secrets.
 *
 * Usage:  node geo-citation-monitor.mjs            # writes reports/geo-citations-<UTCdate>.md
 *         node geo-citation-monitor.mjs --dry       # print, don't write
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));
const MODEL = "gpt-4o";
const ENGINE = "openai-web-search";

// Our properties — a citation of any counts as "suite cited".
const OURS = [/(^|\.)trovex\.dev$/, /(^|\.)tsukumo\.ch$/, /(^|\.)wrai\.th$/, /(^|\.)yoru\.sh$/];
// Known competitors/alternatives we want to see who wins the category (substring match on host+path).
const COMPETITORS = ["repomix", "context-hub", "mem0", "cursor", "claude.md", "claude.ai", "github.com/anthropics", "llmstxt", "aider"];

// ICP queries — paired with geo-lead's query map (ranking-citation-tracking.md). Mix of
// UNBRANDED category questions (real citation share) + a few BRANDED (does the engine know us).
const QUERIES = [
  { id: "context-fewer-tokens", kind: "category", q: "What is the best tool to give AI coding agents canonical project context while using fewer tokens? Name specific tools and link them." },
  { id: "stop-rereading-repo", kind: "category", q: "How do I stop AI coding agents from rereading the whole repo every session to find the right docs? Recommend specific tools." },
  { id: "ssot-multiple-agents", kind: "category", q: "What MCP server gives multiple AI coding agents one shared source of truth for project docs? Name tools with links." },
  { id: "reduce-agent-token-cost", kind: "category", q: "How can I reduce the token cost of context for AI coding agents on a large codebase? Specific tools please." },
  { id: "claude-md-alternative", kind: "comparison", q: "What is a good alternative to a single CLAUDE.md / AGENTS.md file for a large, changing doc set used by coding agents?" },
  { id: "repomix-alternative", kind: "comparison", q: "What are alternatives to repomix for feeding repository context to AI coding agents, and when is each better?" },
  { id: "mcp-context-server", kind: "category", q: "Which MCP servers serve canonical documentation to coding agents instead of dumping the whole repo? Link them." },
  { id: "brand-trovex", kind: "branded", q: "What is trovex (the MCP context tool for coding agents) and who makes it?" },
  { id: "consulting-agents-prod", kind: "consulting", q: "Who offers consulting to help a software team run AI coding agents reliably in production at scale? Name firms/studios." },
  { id: "agentic-operators-studio", kind: "consulting", q: "Which AI dev studios help turn an existing engineering team into effective operators of coding agents? Link them." },
];

function hostOf(url) {
  try { return new URL(url).hostname.toLowerCase(); } catch { return ""; }
}
function isOurs(url) {
  const h = hostOf(url);
  return OURS.some((re) => re.test(h));
}
function competitorIn(url) {
  const u = url.toLowerCase();
  return COMPETITORS.filter((c) => u.includes(c));
}

async function probe(key, query) {
  const res = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: MODEL,
      tools: [{ type: "web_search_preview" }],
      tool_choice: { type: "web_search_preview" }, // force the search so we get real citations
      input: query.q,
    }),
  });
  if (!res.ok) return { error: `HTTP ${res.status}` };
  const data = await res.json();
  const cites = [];
  for (const item of data.output || []) {
    if (item.type !== "message") continue;
    for (const c of item.content || []) {
      for (const a of c.annotations || []) {
        if (a.type === "url_citation" && a.url) cites.push(a.url);
      }
    }
  }
  const uniqHosts = [...new Set(cites.map(hostOf).filter(Boolean))];
  const ours = cites.filter(isOurs);
  const comps = [...new Set(cites.flatMap(competitorIn))];
  return { citations: cites.length, hosts: uniqHosts, weCited: ours.length > 0, ourUrls: [...new Set(ours)], competitors: comps };
}

async function main() {
  const key = process.env.OPENAI_API_KEY;
  if (!key) {
    console.error("No OPENAI_API_KEY in env. Load it out-of-git first:\n  set -a; . ~/.config/trovex-growth/openai.env; set +a");
    process.exit(2);
  }
  const dry = process.argv.includes("--dry");
  const rows = [];
  for (const query of QUERIES) {
    process.stderr.write(`probing ${query.id}… `);
    try {
      const r = await probe(key, query);
      rows.push({ ...query, ...r });
      process.stderr.write(r.error ? `ERR ${r.error}\n` : `${r.weCited ? "CITED" : "not cited"} (${r.citations} citations)\n`);
    } catch (e) {
      rows.push({ ...query, error: String(e).slice(0, 80) });
      process.stderr.write(`ERR\n`);
    }
  }

  const valid = rows.filter((r) => !r.error);
  const citedN = valid.filter((r) => r.weCited).length;
  const share = valid.length ? Math.round((citedN / valid.length) * 100) : 0;
  // UTC date, passed implicitly — no Date fabrication beyond the run stamp.
  const date = new Date().toISOString().slice(0, 10);

  const md = [
    `# GEO Citation-Share — ${date} (${ENGINE})`,
    ``,
    `*Owner: analytics-lead · Engine: OpenAI web_search (model \`${MODEL}\`) · Sampled snapshot — AI answers are non-deterministic; this is one run, not a guaranteed rank. No fabricated data.*`,
    ``,
    `**Suite citation share: ${citedN}/${valid.length} queries (${share}%)** — i.e. of the ICP questions probed, the share where trovex/tsukumo/wrai.th/yoru.sh was cited.`,
    ``,
    `| Query | Kind | We cited? | Our URL(s) | Competitors cited | Total citations |`,
    `|-------|------|:---------:|-----------|-------------------|----------------:|`,
    ...rows.map((r) =>
      r.error
        ? `| ${r.id} | ${r.kind} | ERR | — | — | ${r.error} |`
        : `| ${r.id} | ${r.kind} | ${r.weCited ? "✅" : "—"} | ${(r.ourUrls || []).join("<br>") || "—"} | ${(r.competitors || []).join(", ") || "—"} | ${r.citations} |`,
    ),
    ``,
    `## How to read this`,
    `- **Share is the metric** — track it weekly; one run is noisy, the trend is the signal.`,
    `- **Unbranded "category" queries** = the real prize (a buyer asking generically). **Branded** = does the engine even know us yet.`,
    `- Hand the not-cited category rows to geo-lead: those are the answer/comparison pages to strengthen.`,
    `- Engine coverage: OpenAI web_search live; **Perplexity + Google AI Overviews are TODO (need their own keys)** — add them to widen the panel.`,
    ``,
    `### Queries probed`,
    ...QUERIES.map((q) => `- \`${q.id}\` (${q.kind}): ${q.q}`),
  ].join("\n");

  if (dry) { console.log(md); return; }
  const outDir = join(__dir, "reports");
  mkdirSync(outDir, { recursive: true });
  const outPath = join(outDir, `geo-citations-${date}.md`);
  writeFileSync(outPath, md + "\n");
  console.log(`wrote ${outPath} — suite citation share ${citedN}/${valid.length} (${share}%)`);
}

main();
