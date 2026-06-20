// PR B of the GEO citation offensive (growth/geo/citation-attack-map.md): make the
// /answers + /vs pages maximally citable by AI engines. Two cheap, high-signal levers
// that were absent on every page:
//   1. Speakable — marks the exact passage (h1 + the .verdict direct answer) engines lift.
//   2. Freshness — datePublished/dateModified in schema, mirrored by a visible "Updated"
//      stamp (recency is among the strongest citation signals).
// Idempotent: re-running only bumps dateModified + the visible date. No content rewrite.
// The pages are authored with CRLF line endings — inserts match the file's EOL.
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";

const PUBLISHED = "2026-06-17"; // pages first shipped
const MODIFIED = "2026-06-21"; // this freshness pass
const MODIFIED_HUMAN = "21 June 2026";
const SPEAKABLE = `"speakable": { "@type": "SpeakableSpecification", "cssSelector": ["h1", ".verdict p"] }`;
const DATES = `"datePublished": "${PUBLISHED}", "dateModified": "${MODIFIED}"`;
const STAMP = `<p class="updated">Updated <time datetime="${MODIFIED}">${MODIFIED_HUMAN}</time></p>`;

const dirs = [];
for (const sec of ["answers", "vs", "for", "glossary"]) {
  const base = `public/${sec}`;
  for (const slug of readdirSync(base, { withFileTypes: true })) {
    if (!slug.isDirectory()) continue;
    const f = `${base}/${slug.name}/index.html`;
    if (existsSync(f)) dirs.push(f);
  }
}

let changed = 0;
for (const f of dirs) {
  let html = readFileSync(f, "utf8");
  const before = html;
  const eol = html.includes("\r\n") ? "\r\n" : "\n";

  // 1. Inject dates + speakable into the QAPage/FAQPage/HowTo node (once). Idempotent:
  //    if already present, refresh dateModified only. $2 preserves the matched EOL;
  //    the 8-space indent matches the sibling "mainEntity" line.
  if (!html.includes('"speakable"')) {
    html = html.replace(
      /("@type": "(?:QAPage|FAQPage|HowTo)",)(\r?\n)/,
      `$1$2        ${DATES},${eol}        ${SPEAKABLE},${eol}`,
    );
  } else {
    html = html.replace(/"dateModified": "\d{4}-\d{2}-\d{2}"/, `"dateModified": "${MODIFIED}"`);
  }

  // 2. Visible "Updated" stamp directly before the <h1> (schema mirrors visible content).
  //    $1 = the <h1>'s own indentation, reused so the stamp lines up above it.
  if (!html.includes('class="updated"')) {
    html = html.replace(/^( *)(<h1[ >])/m, `$1${STAMP}${eol}$1$2`);
  } else {
    html = html.replace(
      /<p class="updated">Updated <time datetime="\d{4}-\d{2}-\d{2}">[^<]*<\/time><\/p>/,
      STAMP,
    );
  }

  if (html !== before) {
    writeFileSync(f, html);
    changed++;
  }
}
console.error(`geo-freshness: updated ${changed}/${dirs.length} pages`);
