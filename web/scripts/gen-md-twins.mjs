#!/usr/bin/env node
/*
 * Per-page Markdown twins — AI-ingestion lever (top-1% teardown e775b1a4, adopt #2).
 *
 * Top dev-tool sites (Vercel/Mintlify/Cursor/Supabase) serve a chrome-free .md twin of every
 * page so AI crawlers ingest clean, token-cheap, accurately-quotable content. trovex literally
 * sells "serve agents the clean canonical doc" — so we serve our own pages that way (dogfood).
 *
 * Runs at BUILD time (after `vite build`): reads the hand-authored static HTML under public/
 * for /answers, /vs, /glossary and emits a sibling `index.md` into dist/. Nothing is committed
 * as .md (avoids the md-guard); the twin is a build artifact, regenerated every deploy.
 *
 * Discovery: llms.txt notes the convention (`<page-url>index.md`).
 */
import { readdirSync, readFileSync, writeFileSync, existsSync, mkdirSync, statSync } from "node:fs";
import { join } from "node:path";

const SECTIONS = ["answers", "vs", "glossary"];
const SRC = "public";
const OUT = "dist";
const INSTALL = "uv tool install git+https://github.com/TsukumoHQ/trovex";

const decode = (s) =>
  s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
   .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&mdash;/g, "—")
   .replace(/&nbsp;/g, " ").replace(/&copy;/g, "©");

function htmlToMd(mainHtml) {
  let h = mainHtml;
  // drop non-content blocks: breadcrumb nav, the CTA, the "updated" stamp wrapper kept as text
  h = h.replace(/<nav class="crumb"[\s\S]*?<\/nav>/gi, "");
  h = h.replace(/<div class="cta"[\s\S]*?<\/div>\s*(?=<\/main>|<div|<section|$)/gi, "");
  h = h.replace(/<div class="cta"[\s\S]*?<\/div>/gi, "");
  // label divs (verdict "Definition"/"Verdict", related "Related questions") -> bold line
  h = h.replace(/<div class="l">([\s\S]*?)<\/div>/gi, (_m, t) => `\n\n**${decode(t.trim())}**\n\n`);
  // headings
  h = h.replace(/<h1[^>]*>([\s\S]*?)<\/h1>/gi, (_m, t) => `\n# ${strip(t)}\n\n`);
  h = h.replace(/<h2[^>]*>([\s\S]*?)<\/h2>/gi, (_m, t) => `\n## ${strip(t)}\n\n`);
  h = h.replace(/<h3[^>]*>([\s\S]*?)<\/h3>/gi, (_m, t) => `\n### ${strip(t)}\n\n`);
  // links -> [text](href)
  h = h.replace(/<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi, (_m, href, t) => `[${strip(t)}](${href})`);
  // inline emphasis + code
  h = h.replace(/<(strong|b)>([\s\S]*?)<\/\1>/gi, (_m, _t, t2) => `**${strip(t2)}**`);
  h = h.replace(/<(em|i)>([\s\S]*?)<\/\1>/gi, (_m, _t, t2) => `*${strip(t2)}*`);
  h = h.replace(/<code>([\s\S]*?)<\/code>/gi, (_m, t) => "`" + strip(t) + "`");
  // list items
  h = h.replace(/<li[^>]*>([\s\S]*?)<\/li>/gi, (_m, t) => `- ${strip(t)}\n`);
  // faq q/a use <p class="faq-q"> / <p class="faq-a">
  h = h.replace(/<p class="faq-q">([\s\S]*?)<\/p>/gi, (_m, t) => `\n**${strip(t)}**\n`);
  // paragraphs
  h = h.replace(/<p[^>]*>([\s\S]*?)<\/p>/gi, (_m, t) => `\n${strip(t)}\n`);
  // drop any remaining tags
  h = h.replace(/<[^>]+>/g, "");
  h = decode(h);
  // collapse whitespace: kill whitespace-only lines, trailing spaces, 3+ newlines
  h = h.replace(/[ \t]+\n/g, "\n").replace(/^[ \t]+$/gm, "").replace(/\n{3,}/g, "\n\n").trim();
  return h;
}
// strip tags from a small inline fragment + decode + trim
function strip(s) {
  return decode(s.replace(/<[^>]+>/g, "")).replace(/\s+/g, " ").trim();
}

function field(html, re) {
  const m = html.match(re);
  return m ? m[1].trim() : "";
}

let count = 0;
for (const sec of SECTIONS) {
  const base = join(SRC, sec);
  if (!existsSync(base)) continue;
  for (const slug of readdirSync(base)) {
    const srcFile = join(base, slug, "index.html");
    if (!statSync(join(base, slug)).isDirectory() || !existsSync(srcFile)) continue;
    const html = readFileSync(srcFile, "utf8");
    const canonical = field(html, /<link rel="canonical" href="([^"]+)"/i);
    const title = strip(field(html, /<title>([\s\S]*?)<\/title>/i));
    const mainMatch = html.match(/<main[^>]*>([\s\S]*?)<\/main>/i);
    if (!mainMatch) continue;
    const body = htmlToMd(mainMatch[1]);
    // header = machine comment + source/install blockquote; body already starts with its own # h1
    const md = `<!-- Clean markdown twin for AI ingestion (title: ${title}). Canonical HTML: ${canonical} -->\n` +
      `> Source: ${canonical}\n` +
      `> trovex — open source, public beta. Install: \`${INSTALL}\`\n\n` +
      body + "\n";
    const outDir = join(OUT, sec, slug);
    mkdirSync(outDir, { recursive: true });
    writeFileSync(join(outDir, "index.md"), md);
    count++;
  }
}
console.log(`gen-md-twins: wrote ${count} markdown twins into ${OUT}/{${SECTIONS.join(",")}}`);
