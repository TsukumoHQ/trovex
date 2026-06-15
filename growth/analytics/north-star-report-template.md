# Trovex — North-Star Weekly Report (template)

*Owner: analytics-lead · Cadence: weekly (Mon, covering prev Mon–Sun) · Copy this file per week into `growth/analytics/reports/YYYY-Www.md`.*

North star: **qualified reach → consulting leads.** This report rolls the live events up
into one funnel, finds the **lowest broken stage**, and assigns the next move. Rule: we
report the honest number or mark it `n/a` — never fabricate, never present a proxy as the
real thing.

> Fill every `‹…›`. Keep it to one screen. If a stage is unmeasurable this week, write
> `n/a — <why>`, not a guess.

---

## 0. Headline (one number + one sentence)

- **North-star proxy this week:** `consult_clicked` = `‹n›` (vs `‹n_prev›` last week, `‹±%›`).
- **One sentence:** ‹what moved and why — e.g. "Perplexity citations drove +X sessions but consult intent flat; bottleneck is hero→consult, not reach."›
- **Lowest broken stage:** ‹stage› → **next move:** ‹owner + action / experiment #›.

## 1. Funnel (week over week)

Source: Plausible custom events (home SPA + `/vs/`), Vercel Web Analytics (pageviews/Web Vitals), GitHub. Activation rows = opt-in CLI telemetry (mark `n/a` until it ships).

| Stage | Metric (event) | This wk | Last wk | Δ | Data quality |
|-------|----------------|--------:|--------:|---|--------------|
| Reach | sessions (`landing_view` + `/vs/` pageviews) | ‹› | ‹› | ‹› | real |
| Intent · CTA | `cta_clicked` / sessions | ‹› | ‹› | ‹› | real |
| Intent · GitHub | `github_clicked` (all locations) | ‹› | ‹› | ‹› | real |
| Intent · install proxy | `command_copied` | ‹› | ‹› | ‹› | real **proxy** |
| Consideration | `compare_clicked` → `/vs/` | ‹› | ‹› | ‹› | real |
| **Lead** | `consult_clicked` | ‹› | ‹› | ‹› | real, low-volume |
| Activation · index | `index_run` (1st) | ‹n/a› | ‹n/a› | — | opt-in telemetry: not built |
| Activation · aha | `first_query` w/ `saved>0` | ‹n/a› | ‹n/a› | — | opt-in telemetry: not built |
| Retention | repeat query-day (W1/W2) | ‹n/a› | ‹n/a› | — | opt-in telemetry: not built |
| Vanity (context only) | GitHub stars / clones | ‹› | ‹› | ‹› | vanity-adjacent |

**Conversion rates that matter:** sessions→`github_clicked` = `‹%›`; sessions→`consult_clicked` = `‹%›` (the north-star rate); `/vs/` sessions→`github_clicked` vs home (experiment #5 read) = `‹vs / home›`.

## 2. GEO / channel mix (where reach came from)

Source: `geo_source` / `channel` props (`geo-attribution.md`). AI-engine attribution is a **floor** — report the `direct`/`unknown` share openly.

| Channel | Sessions | `github_clicked` rate | `consult_clicked` | Notes |
|---------|---------:|----------------------:|------------------:|-------|
| ai_engine (chatgpt/perplexity/claude/…) | ‹› | ‹› | ‹› | which engine led: ‹› |
| search | ‹› | ‹› | ‹› | incl. Google AI Overviews (not separable) |
| social (HN/Reddit/X/…) | ‹› | ‹› | ‹› | ‹launch spike?› |
| referral / registry | ‹› | ‹› | ‹› | `utm_source=mcp-registry` = ‹› |
| direct / unknown | ‹› | ‹› | ‹› | **floor caveat** — stripped AI referrers live here |

- **UTM coverage:** ‹% of sessions carrying a known `utm_source`› — low coverage = leads aren't tagging seeded links (ping per `utm-taxonomy-contract`).
- **Best GEO ROI:** ‹engine› — sessions `‹n›` × intent `‹%›`. Tell geo-lead.

## 3. Comparison pages (`/vs/`)

| Page | Pageviews | `github_clicked` | `compare_clicked` out |
|------|----------:|-----------------:|----------------------:|
| vs/ (index) | ‹› | ‹› | ‹› |
| claude-md · repomix · context-hub · cursor-memory · mem0 · vector-db-rag | ‹›… | ‹›… | ‹›… |

- **Top converter:** ‹page› — feed to geo-lead/content-lead.

## 4. Experiments in flight

Source: `experiment-backlog.md`. One success metric each; thin traffic → directional.

| # | Test | Status | Metric | Read so far |
|---|------|--------|--------|-------------|
| ‹#› | ‹hypothesis› | running/queued/done | ‹event› | ‹directional call or "underpowered, hold"› |

## 5. Data-quality / caveats (always fill)

- Activation/retention = `n/a` until opt-in CLI telemetry ships (no install numbers claimed).
- AI-engine share is a floor; `direct`/`unknown` = `‹%›`.
- Analytics deployed `‹date›`; weeks before that are partial.
- Ad-block recovery via first-party Plausible proxy in effect; Vercel WA may differ slightly.
- Anything that looks too good → verify before reporting. No fabricated proof.

## 6. Decision log (≤3 lines)

- **This week's call:** ‹what we'll change, who owns it›.
- **Asks to cmo / leads:** ‹e.g. "geo-lead: UTM-tag the Perplexity comparison links"›.

---

### How to pull the numbers (operator note)

- **Plausible:** dashboard → filter by custom event (`consult_clicked`, `github_clicked`,
  `command_copied`, `compare_clicked`) and break down by the `geo_source` / `channel` /
  `location` props. Set the events as goals to get per-source conversion rates.
- **Vercel WA:** pageviews + Web Vitals only (cross-check reach; not the event source of record).
- **GitHub:** Insights → Traffic (clones/visitors), stargazers (context only).
- **Activation:** when opt-in telemetry exists, pull stage counts from its aggregate; until
  then leave `n/a`.
