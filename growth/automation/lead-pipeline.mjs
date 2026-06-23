/**
 * dokan script: lead-pipeline (PHASE 1 — go-get → enrich → classify → score → tier)
 *
 * Owner/cmo directive (d19858f9): the dokan script runs the WHOLE mechanical pipeline so
 * donna (an expensive agent) never burns tokens on it. The fuzzy ICP judgment is ONE cheap
 * LLM call per lead (gpt-4o-mini), not an agent session — the 20/80 pushed to the limit.
 *
 * PHASE 1 (this file, not owner-gated — build it):
 *   1. pull stargazers of our OSS repos (GitHub API)
 *   2. enrich deterministically (company from profile/email-domain, location, repos, bio)
 *   3. classify the FUZZY bit with 1 cheap LLM call: "does this person/co run agents at
 *      scale? ICP fit yes/no + why" — 1 prompt/lead
 *   4. score deterministically (fit + signal-strength + teamIntent)
 *   5. tier A/B/C
 *   6. emit ::dokan:result:: (structured brief = donna's queue)
 * PHASE 2 (next, TODO below): 7. fill warm template + upsert Twenty (scored Person + draft
 *   note). Reuse src/lib/twenty.ts dedup contract (paginated client-side match, never the
 *   REST email filter — see calendly-twenty-dedup-state).
 *
 * RUNTIME: node (dokan). NO external deps — global fetch (Node 18+).
 * INPUT  : env DOKAN_INPUT (JSON). Fields (all optional, with defaults):
 *   { repos: ["TsukumoHQ/trovex","TsukumoHQ/WRAI.TH","yoru-sh/yoru"],
 *     maxPerRepo: 60, maxClassify: 40, model: "gpt-4o-mini", dryRunLLM: false }
 * SECRETS (dokan store → env): GITHUB_TOKEN (raises GH rate limit + needed for volume),
 *   OPENAI_API_KEY (the cheap classify call). Script degrades, never throws, if absent.
 * OUTPUT : a single line `::dokan:result::<json>` with { generated, counts, leads:[...] }.
 *
 * HONESTY: zero fabrication. A field we can't derive is null. The LLM verdict is stored with
 * its own reason; we never invent company/teamIntent. First-party signals only (public GH).
 */

const GH = "https://api.github.com";

function input() {
  try { return JSON.parse(process.env.DOKAN_INPUT || "{}"); } catch { return {}; }
}

function ghHeaders() {
  const h = { Accept: "application/vnd.github+json", "User-Agent": "tsukumo-lead-pipeline" };
  const t = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  if (t) h.Authorization = `Bearer ${t}`;
  return h;
}

async function ghGet(path) {
  try {
    const res = await fetch(`${GH}${path}`, { headers: ghHeaders() });
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

// 1. Stargazers of a repo (paginated, capped).
async function stargazers(repo, cap) {
  const out = [];
  for (let page = 1; out.length < cap && page <= 10; page++) {
    const batch = await ghGet(`/repos/${repo}/stargazers?per_page=100&page=${page}`);
    if (!Array.isArray(batch) || batch.length === 0) break;
    out.push(...batch.map((u) => u.login).filter(Boolean));
    if (batch.length < 100) break;
  }
  return out.slice(0, cap);
}

// 2. Deterministic enrichment from the public GH profile.
async function enrich(login) {
  const u = await ghGet(`/users/${login}`);
  if (!u) return { login, error: "profile_unavailable" };
  const emailDomain = u.email && u.email.includes("@") ? u.email.split("@")[1].toLowerCase() : null;
  return {
    login,
    name: u.name || null,
    company: u.company ? String(u.company).replace(/^@/, "").trim() : null,
    emailDomain, // null unless the user made their email public
    location: u.location || null,
    bio: u.bio || null,
    blog: u.blog || null,
    publicRepos: typeof u.public_repos === "number" ? u.public_repos : null,
    followers: typeof u.followers === "number" ? u.followers : null,
    hireable: u.hireable === true,
    profile: u.html_url || `https://github.com/${login}`,
  };
}

// 3. Fuzzy ICP classification — ONE cheap LLM call per lead. Returns {fit, teamIntent, why}.
//    Degrades to a null verdict (no fabrication) if no key or the call fails.
async function classify(lead, model) {
  const key = process.env.OPENAI_API_KEY;
  if (!key) return { fit: null, teamIntent: null, why: "no_openai_key", model: null };
  const facts = [
    `login: ${lead.login}`,
    lead.name && `name: ${lead.name}`,
    lead.company && `company: ${lead.company}`,
    lead.emailDomain && `email_domain: ${lead.emailDomain}`,
    lead.location && `location: ${lead.location}`,
    lead.bio && `bio: ${lead.bio}`,
    lead.blog && `blog: ${lead.blog}`,
    `public_repos: ${lead.publicRepos ?? "?"}, followers: ${lead.followers ?? "?"}`,
  ].filter(Boolean).join("\n");
  const sys =
    "You qualify GitHub users who starred an open-source tool for AI coding agents (context/orchestration/observability). " +
    "ICP = engineers or teams who RUN AI CODING AGENTS AT SCALE (multiple agents, a team, production). " +
    "Judge ONLY from the given public facts. Do not invent. If facts are thin, say fit:false with low confidence. " +
    'Reply ONLY compact JSON: {"fit":boolean,"teamIntent":boolean,"confidence":"low|med|high","why":"<=140 chars"}';
  try {
    const res = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: model || "gpt-4o-mini",
        temperature: 0,
        max_tokens: 120,
        messages: [{ role: "system", content: sys }, { role: "user", content: facts }],
        response_format: { type: "json_object" },
      }),
    });
    if (!res.ok) return { fit: null, teamIntent: null, why: `llm_${res.status}`, model };
    const j = await res.json();
    const txt = j?.choices?.[0]?.message?.content || "{}";
    const v = JSON.parse(txt);
    return {
      fit: typeof v.fit === "boolean" ? v.fit : null,
      teamIntent: typeof v.teamIntent === "boolean" ? v.teamIntent : null,
      confidence: ["low", "med", "high"].includes(v.confidence) ? v.confidence : "low",
      why: String(v.why || "").slice(0, 140),
      model,
    };
  } catch (e) {
    return { fit: null, teamIntent: null, why: `llm_err`, model };
  }
}

// 4+5. Deterministic score (0-100) + tier. Rubric: ICP fit + signal strength + teamIntent.
function scoreAndTier(lead, verdict) {
  let s = 0;
  if (verdict.fit === true) s += 45;
  if (verdict.teamIntent === true) s += 20;
  if (verdict.confidence === "high") s += 10;
  else if (verdict.confidence === "med") s += 5;
  if (lead.company) s += 8;            // works somewhere identifiable
  if (lead.emailDomain && !/gmail|outlook|hotmail|proton|yahoo|icloud/.test(lead.emailDomain)) s += 7; // company domain
  if ((lead.followers ?? 0) >= 50) s += 5;
  if (lead.hireable) s -= 5;           // job-seeking ≠ buyer
  s = Math.max(0, Math.min(100, s));
  const tier = s >= 60 ? "A" : s >= 35 ? "B" : "C";
  return { score: s, tier };
}

async function main() {
  const cfg = input();
  const repos = Array.isArray(cfg.repos) && cfg.repos.length
    ? cfg.repos : ["TsukumoHQ/trovex", "TsukumoHQ/WRAI.TH", "yoru-sh/yoru"];
  const maxPerRepo = Number(cfg.maxPerRepo) || 60;
  const maxClassify = Number(cfg.maxClassify) || 40;
  const model = cfg.model || "gpt-4o-mini";

  // 1. collect unique stargazer logins across repos (dedup; remember which repo)
  const seen = new Map(); // login → repo first seen on
  for (const repo of repos) {
    for (const login of await stargazers(repo, maxPerRepo)) {
      if (!seen.has(login)) seen.set(login, repo);
    }
  }
  const logins = [...seen.keys()];

  // 2. enrich (deterministic)
  const enriched = [];
  for (const login of logins) {
    const e = await enrich(login);
    e.starredRepo = seen.get(login);
    enriched.push(e);
  }

  // 3-5. classify the most promising-by-cheap-signal first (cap LLM spend), score, tier
  const preRank = enriched
    .map((e) => ({ e, pre: (e.company ? 2 : 0) + (e.emailDomain ? 2 : 0) + (e.bio ? 1 : 0) + ((e.followers ?? 0) >= 50 ? 1 : 0) }))
    .sort((a, b) => b.pre - a.pre);
  const leads = [];
  let classified = 0;
  for (const { e } of preRank) {
    let verdict = { fit: null, teamIntent: null, confidence: "low", why: "not_classified", model: null };
    if (classified < maxClassify && !e.error) { verdict = await classify(e, model); classified++; }
    const { score, tier } = scoreAndTier(e, verdict);
    leads.push({ ...e, verdict, score, tier });
  }
  leads.sort((a, b) => b.score - a.score);

  const counts = {
    stargazers: logins.length,
    enriched: enriched.length,
    classified,
    A: leads.filter((l) => l.tier === "A").length,
    B: leads.filter((l) => l.tier === "B").length,
    C: leads.filter((l) => l.tier === "C").length,
  };

  // PHASE 2 TODO (owner-gated send only; pipeline-to-draft is NOT gated):
  //   - fill warm 1:1 template (content doc slots) per A/B lead → draft
  //   - upsert each scored lead into Twenty as a Person (dedup via twenty.ts paginated match)
  //     + attach the draft as a note → donna's queue. Source enum + stage = analytics-lead contract.

  const result = { generated: new Date().toISOString(), repos, model, counts, leads };
  // dokan result sentinel (single line)
  console.log(`::dokan:result::${JSON.stringify(result)}`);
}

main().catch((e) => {
  console.log(`::dokan:result::${JSON.stringify({ error: String(e && e.message || e) })}`);
});
