#!/usr/bin/env node
/**
 * Google Search Console pull — per-page organic rank/impressions for the blog (the one FREE
 * organic-search signal blog-performance is missing). Ready to run the moment the owner
 * verifies the tsukumo.ch property + drops a service-account key out-of-git.
 *
 * Setup (one-time, see benchmarks-and-gsc-prep.md §2):
 *   1. Verify https://tsukumo.ch in Search Console (DNS TXT or the existing Vercel/Google token).
 *   2. GCP: create a service account, enable the "Search Console API", download its JSON key.
 *   3. In Search Console → Settings → Users, add the service account's client_email as a user.
 *   4. Store the key out-of-git: ~/.config/trovex-growth/gsc.json  (chmod 600). NEVER commit.
 *
 * Run:  GSC_SA_JSON=~/.config/trovex-growth/gsc.json node growth/analytics/gsc-pull.mjs
 *       (optional: GSC_SITE=https://tsukumo.ch  GSC_SINCE=2026-07-01)
 * Output: per-/blog/ page impressions / clicks / avg position (last 28d default). No secrets
 * in output; the key is read from disk only. Feeds the GSC column in blog-performance.
 */
import { readFileSync } from "node:fs";
import { createSign } from "node:crypto";

const SCOPE = "https://www.googleapis.com/auth/webmasters.readonly";
const ymd = (d) => d.toISOString().slice(0, 10);
const b64url = (b) => Buffer.from(b).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

function loadKey() {
  const path = (process.env.GSC_SA_JSON || "").replace(/^~/, process.env.HOME || "");
  if (!path) { console.error("Set GSC_SA_JSON=<path to service-account json>"); process.exit(2); }
  return JSON.parse(readFileSync(path, "utf8"));
}

async function accessToken(sa) {
  const now = Math.floor(Date.now() / 1000);
  const header = b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claim = b64url(JSON.stringify({
    iss: sa.client_email, scope: SCOPE, aud: sa.token_uri, iat: now, exp: now + 3600,
  }));
  const signer = createSign("RSA-SHA256");
  signer.update(`${header}.${claim}`);
  const jwt = `${header}.${claim}.${b64url(signer.sign(sa.private_key))}`;
  const res = await fetch(sa.token_uri, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion: jwt }),
  });
  if (!res.ok) throw new Error(`token ${res.status}: ${await res.text()}`);
  return (await res.json()).access_token;
}

async function main() {
  const sa = loadKey();
  const site = process.env.GSC_SITE || "https://tsukumo.ch";
  const end = new Date();
  const start = process.env.GSC_SINCE ? new Date(`${process.env.GSC_SINCE}T00:00:00Z`) : new Date(end.getTime() - 28 * 86400_000);
  const token = await accessToken(sa);

  const res = await fetch(
    `https://searchconsole.googleapis.com/webmasters/v3/sites/${encodeURIComponent(site)}/searchAnalytics/query`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ startDate: ymd(start), endDate: ymd(end), dimensions: ["page"], rowLimit: 500 }),
    },
  );
  if (!res.ok) throw new Error(`gsc ${res.status}: ${await res.text()}`);
  const rows = ((await res.json()).rows || []).filter((r) => (r.keys?.[0] || "").includes("/blog/"));

  rows.sort((a, b) => b.impressions - a.impressions);
  console.log(`# GSC blog pages ${ymd(start)}→${ymd(end)} (${rows.length} with impressions)`);
  console.log(`| page | impressions | clicks | ctr | avg position |`);
  console.log(`|------|------------:|-------:|----:|-------------:|`);
  for (const r of rows) {
    const slug = (r.keys[0].split("/blog/")[1] || "").replace(/\/$/, "");
    console.log(`| ${slug} | ${r.impressions} | ${r.clicks} | ${(r.ctr * 100).toFixed(1)}% | ${r.position.toFixed(1)} |`);
  }
  if (!rows.length) console.log("_no blog impressions in window (expected pre-launch)_");
}

main().catch((e) => { console.error(String(e).slice(0, 200)); process.exit(1); });
