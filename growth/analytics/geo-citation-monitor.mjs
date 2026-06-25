#!/usr/bin/env node
/**
 * GEO citation-share PANEL — measure AI-engine citations of the suite DIRECTLY, across engines.
 *
 * AI engines strip referrers, so Plausible GEO attribution is a floor. This probes the ICP's
 * real questions through MULTIPLE AI-search engines, reads back the actual citations, and records
 * whether trovex / tsukumo / the suite is cited — turning the GEO bet into a real, weekly,
 * trendable metric. Top-1% AEO practice: measure citation share at the source, per engine.
 *
 * WHY A PANEL (4 engines): citation sets overlap only ~11% across engines — winning ChatGPT does
 * NOT mean you win Perplexity/Gemini/Google-AIO. Each engine is its own surface to win, so we score
 * each SEPARATELY (not just a union). Only ~14% of marketers track this at all → cheap, durable edge.
 *
 * Engines (each runs ONLY if its key is in env; missing key → marked `n/a`, NEVER fabricated):
 *   - openai      ChatGPT-with-search    OPENAI_API_KEY      (/v1/responses + web_search)
 *   - perplexity  Perplexity             PERPLEXITY_API_KEY  (/chat/completions, sonar)
 *   - gemini      Google Gemini grounded GEMINI_API_KEY      (generateContent + google_search)
 *   - google_aio  Google AI Overviews    SERPAPI_KEY         (SerpAPI — no official AIO API exists)
 *
 * Honesty: AI answers are NON-DETERMINISTIC (vary by run/region/personalization). This is a SAMPLED
 * SNAPSHOT, never a guaranteed rank. We log exactly what each API returns — no fabrication. A missing
 * engine reads `n/a`, a failed call reads `ERR`, a real zero reads `0`. Run weekly; the TREND is the
 * signal, not any single run.
 *
 * Keys: read from the environment ONLY (load out-of-git, e.g.
 *   set -a; . ~/.config/trovex-growth/ai-engines.env; set +a
 * Never hardcode/commit a key; output contains only domains + counts, no secrets.
 *
 * Output:  the report prints to STDOUT (owner rule: "rien en md, tout dans trovex") → pipe it into
 *          trovex_write to centralize. Progress + summary go to stderr. `--save` also drops a disk
 *          .md (opt-in escape hatch). NEVER commit a disk report by default.
 *
 * Usage:  node geo-citation-monitor.mjs                 # all engines w/ a key → report to stdout
 *         node geo-citation-monitor.mjs --engines=openai,perplexity   # subset
 *         node geo-citation-monitor.mjs --save          # also write reports/geo-citations-<date>.md
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));

// Our properties — a citation of any counts as "suite cited".
const OURS = [/(^|\.)trovex\.dev$/, /(^|\.)tsukumo\.ch$/, /(^|\.)wrai\.th$/, /(^|\.)yoru\.sh$/];
// Token match for engines that return redirect URLs (real source only in the title). FULL-DOMAIN /
// org tokens ONLY — bare "trovex" collides with an unrelated company (trovex.ai), which produced a
// false-positive citation. Require our actual domains or github org so a namesake can't read as us.
const OURS_TOKENS = ["trovex.dev", "tsukumo.ch", "wrai.th", "yoru.sh", "tsukumohq/trovex", "github.com/tsukumohq"];
// Known competitors/alternatives — who wins the category (substring match on host+path+title).
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
// VERIFICATION OVERLAY: probe the exact buyer questions tech-copy/geo target so "did the page move
// the citation?" becomes a measured number post-deploy. Started 0/12 (pages not live) — honest baseline.
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

// PRODUCTS cohort — the suite is 3 OSS products feeding one consulting funnel, and citation
// sets barely overlap by category. trovex (context) is already covered by STANDING; this adds
// dedicated category + branded queries for the OTHER two so each product's citation share is
// measurable on its OWN terms, not just "some suite property got cited". Tagged by `product`.
const PRODUCTS = [
  // WRAI.TH — multi-agent orchestration / running agent fleets in production.
  { id: "wraith-orchestrate-fleet", product: "wraith", kind: "category", q: "What tool gives one control plane to run a fleet of AI coding agents in production? Name specific tools and link them." },
  { id: "wraith-agents-collaborate", product: "wraith", kind: "category", q: "How do I coordinate multiple AI agents that hand work to each other on a shared codebase? Recommend specific orchestration tools with links." },
  { id: "wraith-branded", product: "wraith", kind: "branded", q: "What is WRAI.TH (the AI-agent orchestration tool) and who makes it?" },
  // yoru.sh — observability / audit trails for AI agents.
  { id: "yoru-agent-observability", product: "yoru", kind: "category", q: "What tools give observability, traces and audit trails for what AI coding agents actually did? Name specific tools and link them." },
  { id: "yoru-monitor-agents-prod", product: "yoru", kind: "category", q: "How do I monitor AI agents running in production — logs, traces, replay of their actions? Recommend specific tools with links." },
  { id: "yoru-branded", product: "yoru", kind: "branded", q: "What is yoru.sh (observability for AI agents) and who makes it?" },
].map((q) => ({ ...q, cohort: "products" }));

const QUERIES = [...STANDING, ...OFFENSIVE, ...PRODUCTS];

function hostOf(url) {
  try { return new URL(url).hostname.toLowerCase(); } catch { return ""; }
}
// Match against the URL host AND any title text (engines like Gemini/AIO return redirect URLs whose
// real source domain only survives in the citation title).
function isOurs(cite) {
  const h = hostOf(cite.url);
  if (OURS.some((re) => re.test(h))) return true;
  const blob = `${cite.url} ${cite.title || ""}`.toLowerCase();
  return OURS_TOKENS.some((t) => blob.includes(t));
}
function competitorIn(cite) {
  const blob = `${cite.url} ${cite.title || ""}`.toLowerCase();
  return COMPETITORS.filter((c) => blob.includes(c));
}
// Roll a raw citation list ({url,title}[]) into the per-(engine,query) result shape.
function summarize(cites) {
  const clean = cites.filter((c) => c && c.url);
  const uniqHosts = [...new Set(clean.map((c) => hostOf(c.url)).filter(Boolean))];
  const ours = clean.filter(isOurs);
  const comps = [...new Set(clean.flatMap(competitorIn))];
  const ourUrls = [...new Set(ours.map((c) => c.url))];
  return { citations: clean.length, hosts: uniqHosts, weCited: ours.length > 0, ourUrls, competitors: comps };
}

// ---- Engine adapters. Each returns a citation list [{url, title}] or throws. ----
const ENGINES = {
  openai: {
    label: "ChatGPT (OpenAI web_search)",
    envKey: "OPENAI_API_KEY",
    model: "gpt-4o",
    async probe(key, q) {
      const res = await fetch("https://api.openai.com/v1/responses", {
        method: "POST",
        headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          model: this.model,
          tools: [{ type: "web_search_preview" }],
          tool_choice: { type: "web_search_preview" }, // force the search → real citations
          input: q.q,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const cites = [];
      for (const item of data.output || []) {
        if (item.type !== "message") continue;
        for (const c of item.content || []) {
          for (const a of c.annotations || []) {
            if (a.type === "url_citation" && a.url) cites.push({ url: a.url, title: a.title || "" });
          }
        }
      }
      return cites;
    },
  },
  perplexity: {
    label: "Perplexity (sonar)",
    envKey: "PERPLEXITY_API_KEY",
    model: "sonar",
    async probe(key, q) {
      const res = await fetch("https://api.perplexity.ai/chat/completions", {
        method: "POST",
        headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify({ model: this.model, messages: [{ role: "user", content: q.q }] }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      // Prefer structured search_results (objects); fall back to the legacy citations url[] array.
      if (Array.isArray(data.search_results) && data.search_results.length) {
        return data.search_results.map((s) => ({ url: s.url, title: s.title || "" }));
      }
      return (data.citations || []).map((u) => ({ url: typeof u === "string" ? u : u.url, title: "" }));
    },
  },
  gemini: {
    label: "Gemini (grounded w/ google_search)",
    envKey: "GEMINI_API_KEY",
    model: "gemini-2.5-flash", // 2.0/flash-latest 404 on this account; 2.5-flash verified 200 (owner enabled billing 2026-06-20)
    async probe(key, q) {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${this.model}:generateContent`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-goog-api-key": key },
        body: JSON.stringify({ contents: [{ parts: [{ text: q.q }] }], tools: [{ google_search: {} }] }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`); // 429 = RESOURCE_EXHAUSTED → key valid but no quota/billing
      const data = await res.json();
      const chunks = data.candidates?.[0]?.groundingMetadata?.groundingChunks || [];
      // web.uri is a vertexaisearch redirect; the real source domain survives in web.title — keep both.
      return chunks.filter((c) => c.web?.uri).map((c) => ({ url: c.web.uri, title: c.web.title || "" }));
    },
  },
  google_aio: {
    label: "Google AI Overviews (via SerpAPI)",
    envKey: "SERPAPI_KEY",
    // SerpAPI returns the AI Overview in TWO steps: the google search returns a `page_token`,
    // then a second `engine=google_ai_overview` call fetches the actual overview + references.
    // (~2 SerpAPI credits per query → 22 queries ≈ 44 credits/run; mind the monthly quota.)
    async probe(key, q) {
      const url = `https://serpapi.com/search.json?engine=google&q=${encodeURIComponent(q.q)}&api_key=${key}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      let aio = data.ai_overview;
      if (!aio) return []; // no AI Overview shown for this query = honest 0, not an error
      // Paginated: first response is just a token → fetch the real overview.
      if (aio.page_token && !aio.references && !aio.text_blocks) {
        const r2 = await fetch(`https://serpapi.com/search.json?engine=google_ai_overview&page_token=${encodeURIComponent(aio.page_token)}&api_key=${key}`);
        if (!r2.ok) throw new Error(`HTTP ${r2.status} (aio page)`);
        aio = (await r2.json()).ai_overview || {};
      }
      const refs = aio.references || [];
      return refs.filter((r) => r.link).map((r) => ({ url: r.link, title: r.title || r.source || "" }));
    },
  },
};

function chosenEngines() {
  const flag = process.argv.find((a) => a.startsWith("--engines="));
  const want = flag ? flag.split("=")[1].split(",").map((s) => s.trim()) : Object.keys(ENGINES);
  return want.filter((name) => ENGINES[name]);
}

function cohortShare(rows, cohort) {
  const v = rows.filter((r) => r.cohort === cohort && !r.error && !r.skipped);
  const c = v.filter((r) => r.weCited).length;
  return { cited: c, total: v.length, pct: v.length ? Math.round((c / v.length) * 100) : 0 };
}

async function main() {
  const engines = chosenEngines();

  // Resolve which engines actually have a key — the rest are reported n/a, never silently dropped.
  const live = [];
  const skipped = [];
  for (const name of engines) {
    const key = process.env[ENGINES[name].envKey];
    (key ? live : skipped).push(name);
  }
  if (!live.length) {
    console.error(
      `No engine keys in env. Load at least one out-of-git, e.g.\n` +
      `  set -a; . ~/.config/trovex-growth/ai-engines.env; set +a\n` +
      `Expected vars: ${engines.map((n) => ENGINES[n].envKey).join(", ")}`,
    );
    process.exit(2);
  }

  // results[engine][queryId] = summarized result
  const results = {};
  for (const name of live) {
    results[name] = {};
    const key = process.env[ENGINES[name].envKey];
    for (const query of QUERIES) {
      process.stderr.write(`[${name}] ${query.id}… `);
      try {
        const cites = await ENGINES[name].probe(key, query);
        const r = summarize(cites);
        results[name][query.id] = { ...query, ...r };
        process.stderr.write(`${r.weCited ? "CITED" : "not cited"} (${r.citations})\n`);
      } catch (e) {
        results[name][query.id] = { ...query, error: String(e.message || e).slice(0, 60) };
        process.stderr.write(`ERR ${String(e.message || e).slice(0, 40)}\n`);
      }
    }
  }

  // Per-engine share + union ("cited by ANY engine" — the suite's total surface coverage).
  const perEngine = {};
  for (const name of live) {
    const rows = Object.values(results[name]);
    perEngine[name] = {
      overall: cohortShare(rows, "standing"),
      standing: cohortShare(rows, "standing"),
      offensive: cohortShare(rows, "offensive"),
      products: cohortShare(rows, "products"),
      all: (() => {
        const v = rows.filter((r) => !r.error);
        const c = v.filter((r) => r.weCited).length;
        return { cited: c, total: v.length, pct: v.length ? Math.round((c / v.length) * 100) : 0 };
      })(),
    };
  }
  const unionCited = (q) => live.some((name) => results[name][q.id]?.weCited);
  const unionAll = { cited: QUERIES.filter(unionCited).length, total: QUERIES.length };
  unionAll.pct = unionAll.total ? Math.round((unionAll.cited / unionAll.total) * 100) : 0;

  const date = new Date().toISOString().slice(0, 10);

  // ---- readout ----
  const md = [];
  md.push(`# GEO Citation-Share Panel — ${date}`);
  md.push(``);
  md.push(`*Owner: analytics-lead · Engines this run: **${live.join(", ")}**${skipped.length ? ` · n/a (no key): **${skipped.join(", ")}**` : ""}*`);
  md.push(`*Sampled snapshot — AI answers are non-deterministic; this is one run, not a guaranteed rank. No fabricated data: a missing engine reads n/a, a failed call ERR, a real zero 0.*`);
  md.push(``);
  md.push(`## Citation share by engine (each engine is its own surface to win — ~11% overlap)`);
  md.push(``);
  md.push(`| Engine | Status | All | Standing | Offensive | Products |`);
  md.push(`|--------|--------|:---:|:--------:|:---------:|:--------:|`);
  for (const name of engines) {
    if (!live.includes(name)) { md.push(`| ${ENGINES[name].label} | n/a (no ${ENGINES[name].envKey}) | — | — | — | — |`); continue; }
    const e = perEngine[name];
    md.push(`| ${ENGINES[name].label} | live | **${e.all.cited}/${e.all.total} (${e.all.pct}%)** | ${e.standing.cited}/${e.standing.total} (${e.standing.pct}%) | ${e.offensive.cited}/${e.offensive.total} (${e.offensive.pct}%) | ${e.products.cited}/${e.products.total} (${e.products.pct}%) |`);
  }
  md.push(`| **UNION (any engine)** | — | **${unionAll.cited}/${unionAll.total} (${unionAll.pct}%)** | — | — | — |`);
  md.push(``);
  md.push(`**Standing** = stable suite-category panel (weekly trend). **Offensive** = the citation write-list (\`citation-uncited-queries\`); a row flipping ✅ = proof a new page earned a citation. **Products** = per-product category/branded queries (WRAI.TH + yoru.sh). **Union** = share where ANY engine cited us = total reachable surface.`);
  md.push(``);

  // Per-PRODUCT union share — each suite product is its own funnel; measure each on its own queries.
  // trovex's category share lives in Standing (the whole standing set is trovex/context). wraith + yoru
  // get dedicated queries here. A product cited by ANY engine on ANY of its queries counts.
  md.push(`## Citation share by product (union, any engine)`);
  md.push(``);
  md.push(`| Product | Surface | Cited (any engine) |`);
  md.push(`|---------|---------|:------------------:|`);
  md.push(`| trovex | context for coding agents | ${unionAll.total ? `see Standing (${live.length ? perEngine[live[0]].standing.total : 0} queries)` : "—"} |`);
  for (const product of ["wraith", "yoru"]) {
    const pq = PRODUCTS.filter((q) => q.product === product);
    const cited = pq.filter(unionCited).length;
    const surface = product === "wraith" ? "agent-fleet orchestration" : "agent observability";
    md.push(`| ${product === "wraith" ? "WRAI.TH" : "yoru.sh"} | ${surface} | ${cited}/${pq.length} |`);
  }
  md.push(``);
  md.push(`The suite is 3 OSS products feeding one consulting funnel — a citation of any (trovex / WRAI.TH / yoru.sh / tsukumo) counts as "suite cited", but each product wins its category on its OWN queries, so they're scored apart.`);
  md.push(``);

  // Per-query matrix: one column per live engine, ✅/—/ERR per cell.
  md.push(`## Per-query × engine matrix`);
  md.push(``);
  md.push(`| Query | Cohort | Kind | ${live.join(" | ")} |`);
  md.push(`|-------|--------|------|${live.map(() => ":--:").join("|")}|`);
  for (const query of QUERIES) {
    const cells = live.map((name) => {
      const r = results[name][query.id];
      if (!r) return "·";
      if (r.error) return `ERR`;
      return r.weCited ? "✅" : "—";
    });
    md.push(`| ${query.id} | ${query.cohort} | ${query.kind} | ${cells.join(" | ")} |`);
  }
  md.push(``);

  // Detail: where exactly we were cited + who the category winners are, per engine.
  md.push(`## Detail — our citations + competitors seen`);
  for (const name of live) {
    md.push(``);
    md.push(`### ${ENGINES[name].label}`);
    md.push(`| Query | We cited? | Our URL(s) | Competitors cited | Total citations |`);
    md.push(`|-------|:---------:|-----------|-------------------|----------------:|`);
    for (const query of QUERIES) {
      const r = results[name][query.id];
      if (r.error) { md.push(`| ${query.id} | ERR | — | — | ${r.error} |`); continue; }
      md.push(`| ${query.id} | ${r.weCited ? "✅" : "—"} | ${(r.ourUrls || []).join("<br>") || "—"} | ${(r.competitors || []).join(", ") || "—"} | ${r.citations} |`);
    }
  }
  md.push(``);
  md.push(`## How to read / run this SYSTEM`);
  md.push(`- **Share per engine is the metric** — track weekly; one run is noisy, the trend is the signal. Win each engine separately.`);
  md.push(`- **Not-cited rows → geo-lead / tech-copy**: those are the answer/comparison pages to ship or strengthen. An *offensive* row flipping ✅ after a deploy = the page earned the citation.`);
  md.push(`- **Honesty:** a missing engine is \`n/a (no key)\`, never a fabricated 0. Add an engine by exporting its key (\`${Object.values(ENGINES).map((e) => e.envKey).join("\`, \`")}\`).`);
  md.push(`- **Cadence:** weekly + after each offensive batch deploys (allow index lag before re-reading — re-running pre-reindex manufactures a false 0).`);
  md.push(`- **Run:** \`set -a; . ~/.config/trovex-growth/ai-engines.env; set +a && node geo-citation-monitor.mjs\` → report prints to stdout; centralize via trovex_write (no disk .md by default).`);
  md.push(``);
  md.push(`### Queries probed`);
  md.push(`**Standing:**`);
  STANDING.forEach((q) => md.push(`- \`${q.id}\` (${q.kind}): ${q.q}`));
  md.push(`**Offensive (write-list):**`);
  OFFENSIVE.forEach((q) => md.push(`- \`${q.id}\` (tier ${q.tier}): ${q.q}`));
  md.push(`**Products (per-product):**`);
  PRODUCTS.forEach((q) => md.push(`- \`${q.id}\` (${q.product}/${q.kind}): ${q.q}`));

  const out = md.join("\n");
  // The report goes to trovex, not disk (owner: "rien en md, tout dans trovex"). Default = print to
  // STDOUT so the run pipes straight into trovex_write; stderr carries progress + the summary, so a
  // capture of stdout is a clean report. `--save` is an opt-in disk escape hatch (off by default).
  console.log(out);
  const summary = live.map((n) => `${n} ${perEngine[n].all.cited}/${perEngine[n].all.total}`).join(", ");
  process.stderr.write(`per-engine: ${summary}; union ${unionAll.cited}/${unionAll.total} (${unionAll.pct}%)\n`);

  // dokan RESULT channel: emit a compact structured summary that dokan captures (last
  // ::dokan:result:: line) and POSTs to the relay — event-driven citation alert without
  // log-polling. Guarded to dokan runs (DOKAN_RUN_ID) so local stdout (piped to trovex_write)
  // stays a clean markdown report.
  if (process.env.DOKAN_RUN_ID) {
    const result = {
      date,
      engines: live,
      skipped,
      union: unionAll,
      perEngine: Object.fromEntries(
        live.map((n) => [n, { all: perEngine[n].all, standing: perEngine[n].standing, offensive: perEngine[n].offensive, products: perEngine[n].products }]),
      ),
      summary: `GEO citations ${date}: union ${unionAll.cited}/${unionAll.total} (${unionAll.pct}%) across ${live.join(", ") || "no"} engine(s)`,
    };
    console.log(`::dokan:result:: ${JSON.stringify(result)}`);
  }
  if (process.argv.includes("--save")) {
    const outDir = join(__dir, "reports");
    mkdirSync(outDir, { recursive: true });
    const outPath = join(outDir, `geo-citations-${date}.md`);
    writeFileSync(outPath, out + "\n");
    process.stderr.write(`also saved ${outPath} (--save)\n`);
  }
}

main();
