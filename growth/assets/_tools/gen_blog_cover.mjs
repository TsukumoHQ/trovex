// gen_blog_cover.mjs — tsukumo.ch blog per-post cover / ogImage cards (1200x630).
// VISUAL SYSTEM = data-editorial (memory visual-system-locked): brutalist Archivo
// display, dark #0c0d10 + faint dot-grid texture, GREEN accent (tsukumo blog default).
// Reads growth/social/blog-covers.json (the canonical cover manifest). Honest: titles
// verbatim from the live posts; de-em-dash card copy. These feed each post's ogImage
// (NOT cover: — cover: is the title-less hero, per the double-title rule).
//
// Deps (satori/resvg) resolve via a node_modules symlink up-tree.
// Creds (upload): ~/.config/trovex-growth/supabase.env (SUPABASE_URL + SERVICE_ROLE_KEY).
// Run:  node growth/assets/_tools/gen_blog_cover.mjs            (all, upload)
//       node growth/assets/_tools/gen_blog_cover.mjs --no-upload --out /tmp/covers
//       node growth/assets/_tools/gen_blog_cover.mjs <slug>     (one slug)
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const MANIFEST = join(HERE, "..", "..", "social", "blog-covers.json");
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
const deDash = (s) => (s || "").replace(/\s+[—–]\s+/g, ": ");

const tfs = (s) => { const n = s.length; if (n > 62) return 52; if (n > 46) return 60; return 68; };
function titleEl(full, accent) {
  const i = accent ? full.indexOf(accent) : -1;
  const segs = i === -1 ? [{ t: full, a: 0 }] : [{ t: full.slice(0, i), a: 0 }, { t: accent, a: 1 }, { t: full.slice(i + accent.length), a: 0 }];
  const words = [];
  for (const s of segs) for (const w of s.t.split(" ")) { if (w === "") continue; words.push({ w, a: s.a }); }
  return h("div", { style: { display: "flex", flexWrap: "wrap", fontFamily: "Archivo", fontWeight: 800, fontSize: `${tfs(full)}px`, lineHeight: 1.0, letterSpacing: "-0.035em", maxWidth: "1080px" } },
    ...words.map(({ w, a }) => h("span", { style: { color: a ? C.green : C.ink, marginRight: "0.24em" } }, w)));
}
function cover(p) {
  return h("div", { style: { width: "1200px", height: "630px", display: "flex", flexDirection: "column", justifyContent: "space-between", backgroundColor: C.bg, backgroundImage: `url(${DOT})`, backgroundRepeat: "repeat", color: C.ink, padding: "58px 64px", fontFamily: "Fira Sans" } },
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${C.rule}`, paddingBottom: "20px" } },
      h("div", { style: { display: "flex", alignItems: "center", gap: "11px", fontFamily: "Fira Code", fontSize: "26px", color: C.ink } },
        h("div", { style: { width: "16px", height: "16px", backgroundColor: C.green } }), h("span", {}, "tsukumo")),
      h("div", { style: { fontFamily: "Fira Code", fontSize: "19px", color: C.subtle, letterSpacing: "0.05em" } }, deDash(p.kicker || "the blog"))),
    h("div", { style: { display: "flex", flexDirection: "column", gap: "20px" } },
      titleEl(p.title, p.accent),
      h("div", { style: { fontFamily: "Fira Sans", fontWeight: 500, fontSize: "25px", lineHeight: 1.36, color: C.soft, maxWidth: "960px" } }, deDash(p.sub))),
    h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: "Fira Code", fontSize: "19px", borderTop: `1px solid ${C.rule}`, paddingTop: "20px" } },
      h("span", { style: { color: C.subtle } }, p.source ? `source: ${deDash(p.source)}` : ""),
      h("span", { style: { color: C.green } }, "tsukumo.ch")));
}

const SB_URL = process.env.SUPABASE_URL, SB_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
async function upload(slug, png) {
  const path = `tsukumo/cover/${slug}/og-1200x630.png`;
  const r1 = await fetch(`${SB_URL}/storage/v1/object/media/${path}`, { method: "POST", headers: { Authorization: `Bearer ${SB_KEY}`, apikey: SB_KEY, "Content-Type": "image/png", "x-upsert": "true" }, body: png });
  if (!r1.ok && r1.status !== 200) throw new Error(`storage ${r1.status}`);
  const url = `${SB_URL}/storage/v1/object/public/media/${path}`;
  const r2 = await fetch(`${SB_URL}/rest/v1/media_assets?on_conflict=property,kind,slug,variant`, { method: "POST",
    headers: { Authorization: `Bearer ${SB_KEY}`, apikey: SB_KEY, "Content-Type": "application/json", Prefer: "resolution=merge-duplicates,return=minimal" },
    body: JSON.stringify({ property: "tsukumo", kind: "cover", slug, variant: "og-1200x630", path, url, width: 1200, height: 630, tags: ["cover", "blog"], generator: "gen_blog_cover.mjs" }) });
  if (!r2.ok) throw new Error(`index ${r2.status}`);
  return url;
}

const args = process.argv.slice(2);
const noUpload = args.includes("--no-upload");
const outIdx = args.indexOf("--out"), outDir = outIdx !== -1 ? args[outIdx + 1] : null;
const onlySlug = args.find((a, i) => !a.startsWith("--") && (outIdx === -1 || i !== outIdx + 1));
if (!noUpload && (!SB_URL || !SB_KEY)) { console.error("source supabase.env or pass --no-upload"); process.exit(1); }

let posts = JSON.parse(await readFile(MANIFEST, "utf8"));
if (onlySlug) posts = posts.filter((p) => p.slug === onlySlug);
if (outDir) await mkdir(outDir, { recursive: true });
let n = 0;
for (const p of posts) {
  const svg = await satori(cover(p), { width: 1200, height: 630, fonts });
  const png = new Resvg(svg, { fitTo: { mode: "width", value: 1200 } }).render().asPng();
  if (outDir) await writeFile(join(outDir, `${p.slug}.png`), png);
  if (!noUpload) await upload(p.slug, png);
  n++;
}
console.log(`${n} covers ${noUpload ? "rendered" : "uploaded"}`);
