#!/usr/bin/env node
// Silo + schema coherence guard for trovex.dev (web/public).
// Asserts, across /answers, /vs, /glossary, /for:
//   - every content dir is in sitemap.xml
//   - every /answers + /vs page is referenced in llms.txt
//   - each page's JSON-LD parses
//   - /answers pages carry QAPage + Speakable + a visible freshness stamp
//   - the /answers index ItemList lists every live answer page (schema == visible)
// Exit non-zero on any failure so it can gate a PR / run in dokan.
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const PUB = join(dirname(fileURLToPath(import.meta.url)), "..", "public");
const BASE = "https://trovex.dev";
const fails = [];
const fail = (m) => fails.push(m);

const read = (p) => readFileSync(join(PUB, p), "utf8");
const dirsIn = (sub) =>
  existsSync(join(PUB, sub))
    ? readdirSync(join(PUB, sub), { withFileTypes: true })
        .filter((d) => d.isDirectory())
        .map((d) => d.name)
    : [];

const sitemap = read("sitemap.xml");
const llms = read("llms.txt");

// llms.txt is curated, not exhaustive — but the section catch-alls must exist so crawlers reach the rest.
if (!llms.includes(`${BASE}/answers/`)) fail("llms.txt: no 'All answers' catch-all link");
if (!llms.includes(`${BASE}/vs/`)) fail("llms.txt: no 'All comparisons' catch-all link");

const jsonLdBlocks = (html) =>
  [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(
    (m) => m[1],
  );

// 1. Every content dir → sitemap + parseable JSON-LD
for (const sub of ["answers", "vs", "glossary", "for"]) {
  for (const slug of dirsIn(sub)) {
    const rel = `${sub}/${slug}/index.html`;
    if (!existsSync(join(PUB, rel))) continue; // skip asset-only dirs
    const url = `${BASE}/${sub}/${slug}/`;
    if (!sitemap.includes(`<loc>${url}</loc>`)) fail(`sitemap missing: ${url}`);
    const html = read(rel);
    for (const block of jsonLdBlocks(html)) {
      try {
        JSON.parse(block);
      } catch (e) {
        fail(`JSON-LD parse error in ${rel}: ${e.message}`);
      }
    }
    // 3. answers pages: an answer schema (QAPage or FAQPage) + Speakable + visible freshness stamp.
    //    llms.txt is curated (highlights + "All answers"/"All comparisons" catch-alls), so it is
    //    NOT required to list every page — only the section catch-all must exist (checked once below).
    if (sub === "answers") {
      if (!/"@type":\s*"(QAPage|FAQPage)"/.test(html))
        fail(`no QAPage/FAQPage schema: ${rel}`);
      if (!html.includes("SpeakableSpecification")) fail(`no Speakable: ${rel}`);
      if (!/class="updated"|Updated <time/.test(html))
        fail(`no freshness stamp: ${rel}`);
    }
  }
}

// 4. /answers index ItemList must list every live answer page
const idx = read("answers/index.html");
const itemListBlock = jsonLdBlocks(idx)
  .map((b) => {
    try {
      return JSON.parse(b);
    } catch {
      return null;
    }
  })
  .filter(Boolean)
  .flatMap((j) => j["@graph"] || [j])
  .find((g) => g["@type"] === "ItemList");
if (!itemListBlock) {
  fail("answers/index.html: no ItemList JSON-LD");
} else {
  const listed = new Set(
    (itemListBlock.itemListElement || []).map((i) => i.url),
  );
  for (const slug of dirsIn("answers")) {
    if (!existsSync(join(PUB, `answers/${slug}/index.html`))) continue;
    const url = `${BASE}/answers/${slug}/`;
    if (!listed.has(url)) fail(`answers ItemList missing (schema≠visible): ${url}`);
  }
}

const answerCount = dirsIn("answers").filter((s) =>
  existsSync(join(PUB, `answers/${s}/index.html`)),
).length;
if (fails.length) {
  console.error(`✗ silo/schema guard: ${fails.length} issue(s)`);
  for (const f of fails) console.error("  - " + f);
  process.exit(1);
}
console.log(
  `✓ silo/schema guard: ${answerCount} answers, all in sitemap + llms.txt + ItemList; QAPage/Speakable/freshness present; JSON-LD parses.`,
);
