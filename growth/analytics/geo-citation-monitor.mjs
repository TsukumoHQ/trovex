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
// STANDING cohort — the original suite-category panel. Keep stable so the weekly trend stays comparable.
const STANDING = [
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
].map((q) => ({ ...q, cohort: "standing" }));

// OFFENSIVE cohort — the citation write-list the team is actively building answers for
// (source: memory `citation-uncited-queries` / content/geo/query-gap-backlog.md, 2026-06-19).
// This is the VERIFICATION OVERLAY: probe the exact buyer questions tech-copy/geo are
// targeting so "did the page move the citation?" becomes a measured number post-deploy.
// Started 0/12 by definition (pages not live yet) — that's the honest pre-deploy baseline.
const OFFENSIVE = [
  { id: "agents-reliable-in-prod", tier: 1, q: "How do I make AI coding agents reliable in production — guardrails, review gates, observability? Name specific tools, articles, or studios and link them." },
  { id: "agent-observability", tier: 1, q: "How do I know what my AI coding agent actually did — what tools give agent observability and audit trails? Link specific tools or guides." },
  { id: "managing-agent-context", tier: 1, q: "My AI coding agents keep losing context on a large codebase — how do I manage context for them? Recommend specific tools with links." },
  { id: "agent-token-cost", tier: 1, q: "The token cost of my AI coding agents is too high — how do I cut it with better context and orchestration? Name specific tools and link them." },
  { id: "agent-guardrails", tier: 1, q: "Is it safe to let AI coding agents touch our codebase, and what guardrails (review gates, scoped permissions) make it safe? Link specific tools or guides." },
  { id: "multi-agent-orchestration", tier: 1, q: "How do software teams orchestrate multiple AI coding agents working together? Name specific tools or frameworks with links." },
  { id: "ai-code-safe-to-ship", tier: 2, q: "Is AI-written code safe to ship, and how do teams do AI code review in production? Link specific tools or articles." },
  { id: "ai-native-eng-team", tier: 2, q: "What does an AI-native engineering team actually look like in practice? Link specific writeups or studios." },
  { id: "roi-of-ai-agents", tier: 2, q: "How do I measure the ROI of AI coding agents for an engineering team? Link specific frameworks or articles." },
  { id: "convince-skeptical-devs", tier: 2, q: "How do I convince skeptical senior developers to adopt AI coding tools without losing their trust? Link specific writeups or studios." },
  { id: "agentic-sdlc", tier: 2, q: "What is an agentic SDLC and how does it change the software development lifecycle? Define it and link sources." },
  { id: "ai-adoption-scaleups", tier: 2, q: "How should a scale-up or mid-market engineering team adopt AI coding agents at scale? Name specific studios or consultancies and link them." },
].map((q) => ({ ...q, kind: "offensive", cohort: "offensive" }));

const QUERIES = [...STANDING, ...OFFENSIVE];

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
  // Per-cohort share — the offensive cohort is the one we expect to move once pages deploy.
  const cohortShare = (name) => {
    const v = valid.filter((r) => r.cohort === name);
    const c = v.filter((r) => r.weCited).length;
    return { cited: c, total: v.length, pct: v.length ? Math.round((c / v.length) * 100) : 0 };
  };
  const standing = cohortShare("standing");
  const offensive = cohortShare("offensive");
  // UTC date, passed implicitly — no Date fabrication beyond the run stamp.
  const date = new Date().toISOString().slice(0, 10);

  const md = [
    `# GEO Citation-Share — ${date} (${ENGINE})`,
    ``,
    `*Owner: analytics-lead · Engine: OpenAI web_search (model \`${MODEL}\`) · Sampled snapshot — AI answers are non-deterministic; this is one run, not a guaranteed rank. No fabricated data.*`,
    ``,
    `**Suite citation share: ${citedN}/${valid.length} queries (${share}%)** — i.e. of the ICP questions probed, the share where trovex/tsukumo/wrai.th/yoru.sh was cited.`,
    ``,
    `**By cohort:**`,
    `- **Standing** (suite-category panel, stable weekly trend): **${standing.cited}/${standing.total} (${standing.pct}%)**`,
    `- **Offensive** (the citation write-list being built — \`citation-uncited-queries\`): **${offensive.cited}/${offensive.total} (${offensive.pct}%)** — verification overlay; expected 0 until pages deploy + get indexed.`,
    ``,
    `| Query | Cohort | Kind | We cited? | Our URL(s) | Competitors cited | Total citations |`,
    `|-------|--------|------|:---------:|-----------|-------------------|----------------:|`,
    ...rows.map((r) =>
      r.error
        ? `| ${r.id} | ${r.cohort} | ${r.kind} | ERR | — | — | ${r.error} |`
        : `| ${r.id} | ${r.cohort} | ${r.kind} | ${r.weCited ? "✅" : "—"} | ${(r.ourUrls || []).join("<br>") || "—"} | ${(r.competitors || []).join(", ") || "—"} | ${r.citations} |`,
    ),
    ``,
    `## How to read this`,
    `- **Share is the metric** — track it weekly; one run is noisy, the trend is the signal.`,
    `- **Two cohorts:** *standing* keeps the weekly trend comparable; *offensive* is the post-deploy verification overlay for the queries tech-copy/geo are actively building answers for. A row in *offensive* flipping ✅ is the proof a new page earned a citation.`,
    `- **Unbranded "category" queries** = the real prize (a buyer asking generically). **Branded** = does the engine even know us yet.`,
    `- Hand the not-cited rows back to geo-lead/tech-copy: those are the answer/comparison pages to ship or strengthen.`,
    `- Engine coverage: OpenAI web_search live; **Perplexity + Google AI Overviews are TODO (need their own keys)** — add them to widen the panel.`,
    ``,
    `### Queries probed`,
    `**Standing:**`,
    ...STANDING.map((q) => `- \`${q.id}\` (${q.kind}): ${q.q}`),
    `**Offensive (write-list):**`,
    ...OFFENSIVE.map((q) => `- \`${q.id}\` (tier ${q.tier}): ${q.q}`),
  ].join("\n");

  if (dry) { console.log(md); return; }
  const outDir = join(__dir, "reports");
  mkdirSync(outDir, { recursive: true });
  const outPath = join(outDir, `geo-citations-${date}.md`);
  writeFileSync(outPath, md + "\n");
  console.log(`wrote ${outPath} — suite citation share ${citedN}/${valid.length} (${share}%)`);
}

main();
