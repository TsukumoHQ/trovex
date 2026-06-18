# Suite → Agency — Weekly Digest (auto), 2026-06-18

*Auto-assembled by `weekly-digest-runner.mjs` · window 2026-06-11→2026-06-18 · Plausible + Supabase (live). No fabricated data; `n/a` = source unavailable. North star = `assessment_request` where `source=suite`.*

## Headline
- **North star — suite-sourced assessment requests: 0.** All assessment requests: 0.
- **Qualified leads (hot+warm): 0** (suite-attributed: 0). Bands — hot 0 · warm 0 · cold 0.
- **Waitlist signups (all projects): 6.**

## Suite reach — GitHub (top of funnel, all-time stars + 14d clones)
| Repo | Stars | Clones 14d (total/uniq) |
|------|------:|-------------------------|
| Synergix-lab/WRAI.TH | 21 | 1367/404 |
| Synergix-lab/trovex | 0 | 1004/5 |
| Synergix-lab/yoru | n/a | n/a |
> CLI repos (WRAI.TH/yoru) have no landing — GitHub traffic is their reach. The full chain:
> suite reach (here) → suite_to_agency_click → assessment_request → qualified (below).

## Funnel (Plausible, 2026-06-11→2026-06-18)
| Stage | Event | Count |
|-------|-------|------:|
| Agency visits | tsukumo_visit | 57 |
| Suite→agency clicks | suite_to_agency_click | 3 |
| Intent | intent_page_view | 28 |
| CTA / contact | cta_clicked + contact_clicked | 7 + 0 |
| **★ Conversion** | assessment_request | 0 |
| — suite-sourced (north star) | source=suite | 0 |

**Rates:** visit→assessment 0% · visit→qualified 0%.

## GEO / channel (tsukumo_visit by geo_source)
| geo_source | visits |
|------------|------:|
| direct | 54 |
| referral | 2 |
| trovex | 1 |

## Community / top-of-funnel capture (new surfaces)
| Surface | Metric | Count |
|---------|--------|------:|
| Newsletter | newsletter_signup (event) | 0 |
| Newsletter | new rows (Supabase) | 0 |
| Tool /context-cost | tool_view → completed → cta | 0 → 0 → 0 |

**Tool funnel:** view→completed n/a · completed→cta n/a. (Tool CTA → /assessment; see which readiness band converts via `event:props:result`.)

## Other reads (run separately)
- GEO citation share — `geo-citation-monitor.mjs` → `reports/geo-citations-*.md`.
- Per-post performance + read-depth — `blog-performance.mjs` → `reports/blog-performance-*.md`.

## Hygiene
- Window honors `--since <launch-date>`; pre-launch traffic is crawler+verification noise (see `traffic-hygiene.md`) — start the window at launch day for a clean read.
- Supabase reads are **counts on non-PII columns** (lead_band/channel/how_heard) — no email leaves the DB.
