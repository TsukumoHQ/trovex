# UTM'd launch-link sheet — attribution wired before firing (DRAFT)

**Status:** DRAFT / ready-to-paste links. The owner pastes these when firing each surface. Nothing live.
**Owner:** launch-lead · **Reviewed against:** utm-convention.md, geo-attribution.md, funnel-event-taxonomy, oss-agency-bridge.md, launch-day-runbook.md, suite-positioning.md, voice
**Pairs with:** analytics-lead (owns the `utm_source` map in `web/src/analytics.ts`).

> Goal: every launch click is attributable from minute 1, so the north-star report ("waitlist/leads **by source**") is real instead of a pile of "Direct." This sheet maps **every launch surface → the exact link to paste**, matching the UTM contract.

---

## 0. How attribution actually works here (read before pasting — this is the whole point)

Three cases. Getting them right is the difference between real data and "Direct."

1. **Link to a property we control (`trovex.dev`, wrai.th site, `tsukumo.ch`) → UTM is captured.** These are the rows that carry `utm_*`. The web layer reads them into closed-enum session props and persists them on waitlist signup (utm-convention §4).
2. **Link to the GitHub repo (the HN/PH submission URL, most registry/dir links) → UTM is NOT captured.** GitHub strips it. Attribution falls back to **referrer host** (geo-attribution.md). So we don't fake UTMs on repo links — we rely on the referrer floor and, where possible, *also* drop a UTM'd `trovex.dev` link in the post body.
3. **AI engines + dark social strip the referrer → lands in `direct`.** Only a UTM we put on the link survives (case 1). That's why the controllable links below matter most.

**Practical rule:** the submission URL is often the repo (no UTM); the **in-post secondary link to trovex.dev is where we capture** — always UTM that one.

---

## 1. Closed values (quick ref — must match `analytics.ts`)

- **`utm_source`** (closed): `hackernews` · `producthunt` (alias `ph`) · `reddit` · `lobsters` · `x` · `linkedin` · `discord` · `newsletter` · `mcp-registry` (or specific slug) · AI engines (`chatgpt`/`perplexity`/`claude`/`gemini`/`bing`/`copilot`) · `google`.
- **`utm_medium`** (closed): `ai_answer` · `organic` · `social` · `community` · `registry` · `referral` · `email` · `paid`.
- **`utm_campaign`**: `private-beta` (NOW) · `launch-hn` · `launch-ph` · `launch` (registries/dirs umbrella) · `newsletter` · `agency-launch` · `lead-nurture`.
- **`utm_content`**: the variant/placement (`hn-firstcomment`, `ph-gallery`, `rmcp-post`, `thread-1`, `listing`, `vs-leanctx`…). Powers per-placement attribution.

> ⚠️ **Pre-fire blocker for analytics-lead:** confirm EVERY `utm_source` below is in the `analytics.ts` map (esp. `hackernews`, `producthunt`, `reddit`, `lobsters`, `discord`, `mcp-registry`) and that `launch`, `launch-hn`, `launch-ph` are accepted campaigns. Unmapped source → silently `referral`/`unknown` and that channel's ROI vanishes. **Do this before launch day.**

---

## 2. Phase note — what campaign is live

- **NOW (private beta):** primary conversion = waitlist. Links point to `trovex.dev` (waitlist), `utm_campaign=private-beta`. (community/social drive per beta-* docs.)
- **Coordinated public launch (cmo go):** swap campaign to `launch-hn` / `launch-ph` / `launch`; trovex links may point to repo once public (then UTM only on the trovex.dev secondary link). wrai.th leads the one-shots.

Base for controllable links: `https://trovex.dev/?…` (swap to the repo as the *submission* URL where noted).

---

## 3. The sheet — per surface

### One-shots (HN / PH) — wrai.th leads

| Surface | Submission URL (posted) | UTM? | Controllable link to paste (in first comment / body) |
|---|---|---|---|
| **Show HN (wrai.th)** | `github.com/Synergix-lab/WRAI.TH` (repo) | repo = no UTM (referrer fallback) | suite cross-link → `https://trovex.dev/?utm_source=hackernews&utm_medium=social&utm_campaign=launch-hn&utm_content=hn-firstcomment` |
| **Show HN (trovex, when public)** | `github.com/Synergix-lab/trovex` (repo) | repo = no UTM | secondary → `https://trovex.dev/?utm_source=hackernews&utm_medium=social&utm_campaign=launch-hn&utm_content=hn-firstcomment` |
| **Product Hunt** | PH listing (links repo + homepage) | homepage field = UTM'd | homepage → `https://trovex.dev/?utm_source=producthunt&utm_medium=social&utm_campaign=launch-ph&utm_content=ph-listing` ; maker-comment link `…&utm_content=ph-firstcomment` |

### Registries / directories (the shelf)

| Surface | Link posted | UTM? | Link to paste |
|---|---|---|---|
| **MCP Official / Glama / mcp.so** | repo (+ homepage field where allowed) | homepage field = UTM'd | `https://trovex.dev/?utm_source=mcp-registry&utm_medium=registry&utm_campaign=launch&utm_content=listing` |
| **awesome-mcp / awesome-go** | repo line | repo = no UTM (referrer) | n/a — referrer fallback; keep repo link clean per list format |
| **AlternativeTo** | homepage + repo | homepage = UTM'd | `https://trovex.dev/?utm_source=mcp-registry&utm_medium=referral&utm_campaign=launch&utm_content=alternativeto` *(or a dedicated slug if analytics-lead adds it)* |
| **DevHunt / Product-Hunt-dirs** | repo + homepage | homepage = UTM'd | `https://trovex.dev/?utm_source=mcp-registry&utm_medium=referral&utm_campaign=launch&utm_content=devhunt` |

> Registry/dir sources collapse to `mcp-registry` unless analytics-lead adds per-directory slugs; `utm_content` keeps them distinguishable. Repo-only lists (awesome-*) rely on referrer.

### Community venues (value-first; per community-plan + community-participation-playbook)

| Venue | Link posted | UTM? | Link to paste |
|---|---|---|---|
| **r/mcp** | trovex.dev or repo (per post) | trovex.dev = UTM'd | `https://trovex.dev/?utm_source=reddit&utm_medium=community&utm_campaign=launch-hn&utm_content=rmcp-post` |
| **r/ChatGPTCoding** | trovex.dev or repo | UTM'd | `…?utm_source=reddit&utm_medium=community&utm_campaign=launch-hn&utm_content=rchatgptcoding-post` |
| **r/LocalLLaMA** | trovex.dev or repo | UTM'd | `…?utm_source=reddit&utm_medium=community&utm_campaign=launch-hn&utm_content=rlocalllama-post` |
| **MCP Discord #showcase** | trovex.dev or repo | UTM'd | `…?utm_source=discord&utm_medium=community&utm_campaign=launch-hn&utm_content=mcp-showcase` |
| **Lobsters** | repo (story link) | repo = no UTM (referrer) | secondary in comment → `…?utm_source=lobsters&utm_medium=community&utm_campaign=launch-hn&utm_content=lobsters` |

> reddit posts share `utm_source=reddit`; the subreddit is in `utm_content`. Don't paste the same link across venues (spam) — each has its own `utm_content`.

### Social (per social-lead)

| Surface | Link to paste |
|---|---|
| **X thread** | `https://trovex.dev/?utm_source=x&utm_medium=social&utm_campaign=launch-hn&utm_content=thread-1` |
| **LinkedIn post** | `https://trovex.dev/?utm_source=linkedin&utm_medium=social&utm_campaign=launch-hn&utm_content=post-1` |

### Newsletters / earned media (per outreach.md + earned-media-targets.md)

| Surface | Link to paste |
|---|---|
| **Newsletter feature/note** | `https://trovex.dev/?utm_source=newsletter&utm_medium=email&utm_campaign=newsletter&utm_content=<outlet>` |
| **Guest article / podcast show-notes** | `…?utm_source=newsletter&utm_medium=referral&utm_campaign=newsletter&utm_content=<outlet>-article` |

### Suite → tsukumo (cross-property — different taxonomy)

These point to `tsukumo.ch`, governed by tsukumo's own analytics, NOT the trovex.dev list. Use the scheme from `oss-agency-bridge.md`:
```
https://tsukumo.ch/?utm_source=<tool>&utm_medium=oss-suite&utm_campaign=consulting&utm_content=<readme|site-footer>
```
(`<tool>` = `wraith` | `trovex` | `yoru`.) Fires `suite_to_agency_click` from web footers (not static READMEs).

---

## 4. QA + handoff (do before firing)

- [ ] **analytics-lead:** confirm every `utm_source` + the `launch*` campaigns are in `analytics.ts` (§1 blocker). This is the gate — unmapped = lost ROI.
- [ ] Verify a tagged `trovex.dev` link round-trips: click → `getAttribution()` captures source/medium/campaign/content → persists on waitlist signup.
- [ ] Owner pastes the **right row per surface**; never the same `utm_content` twice; never a UTM on a repo-only link (it's stripped — use the referrer fallback instead).
- [ ] Keep tsukumo links on the cross-property scheme (§3 last block), not the trovex.dev list.
- [ ] No PII anywhere (UTMs are host/enum only); no "Synergix" in any visible link text; lowercase wordmarks.
- [ ] Log which links went where (surface, utm_content, date) so the north-star report reconciles.

*All links above are drafts to paste at fire time. Nothing has been posted.*
