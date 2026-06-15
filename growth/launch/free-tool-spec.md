# Free tool spec — agent token-savings calculator (DRAFT)

**Status:** DRAFT spec + funnel-fit doc. No build, no deploy. For cmo/eng to scope.
**Owner:** launch-lead · **Reviewed against:** product-marketing-context.md, voice, no-synergix-mention, copy-gate, north-star
**Repo:** github.com/Synergix-lab/trovex · **Landing:** trovex.dev

---

## 1. The idea in one line

A tiny standalone web tool that estimates what a coding agent spends rereading a repo's `.md` docs,
and what routing to one canonical doc would save. Useful on its own. The honest version of the ~60%
number, run on the visitor's own inputs.

## 2. Why this tool, and the trap to avoid

A free tool only feeds the funnel if it's genuinely useful detached from the product. The trap: a
calculator that always says "you'd save 60%, now install trovex" is an ad, devs see through it, and it
converts nobody. So the rule for this build: **the math has to be real and the tool has to stand alone.**
If a visitor's repo wouldn't save much, the tool says so. That honesty is what makes the install pitch
credible when the number *is* big.

## 3. What it computes (the model)

Two input modes. Same output.

**Mode A — quick estimate (sliders/fields, no upload):**
Inputs the user sets:
- number of `.md` files an agent typically considers per lookup (default 6)
- average file size in tokens (default ~1,200; show the assumption)
- lookups per session (default 10)
- sessions per day (default 8)
- number of agents/teammates sharing the repo (default 1)
- model input price per 1M tokens (a small preset list + a custom field)

Computation (transparent, shown on screen):
```
baseline_tokens_per_lookup   = files_considered * avg_file_tokens
trovex_tokens_per_lookup     = one_section_tokens + pointer_overhead   // default section ~400 + ~60
saved_per_lookup             = baseline - trovex
lookups_per_day              = lookups_per_session * sessions_per_day * agents
tokens_saved_per_day         = saved_per_lookup * lookups_per_day
$_saved_per_day              = tokens_saved_per_day / 1e6 * model_input_price
…rolled up to per-week / per-month
```
Show the % saved alongside the absolute number, and surface the assumptions so a skeptic can adjust them.

**Mode B — paste a repo / file list (better estimate, optional, later):**
- User pastes a list of `.md` paths + sizes (or the tool reads a public GitHub repo's `.md` tree via the
  GitHub API, no auth, public only). Compute real corpus size and a per-lookup estimate from it.
- Mode B is a v2 — Mode A ships first.

**Honesty rules baked into the UI:**
- Every default is labeled an assumption and is editable.
- If inputs imply a small saving (tiny doc set), the result says plainly "not much to save here — trovex
  helps most on doc-heavy repos." No dark-pattern flattering numbers.
- One line under the result: "this is an estimate from your inputs, not a measurement. trovex ships a
  savings view that measures the real number on your repo."

## 4. The page (copy — passes anti-ai-slop)

**H1:** `What do your coding agents spend rereading docs?`
**Sub:** `Estimate the tokens your agents burn rereading .md files each session, and what serving one
canonical doc would save. Adjust every assumption. If the number's small, the tool will tell you.`

**Result block:** big number (tokens/$ saved per month) + the % + a small "show the math" toggle that
reveals the formula above.

**Below the result (the low-key path to the product, not a wall):**
```
trovex does this for real: it indexes your repo's markdown and serves your agent the one current doc
(path:line + freshness) instead of a reread, and shows you the measured savings. Open source, runs on
your machine. github.com/Synergix-lab/trovex
```
**Footer, even lower-key (the consulting door):** `Running agents across a team? happy to talk.`
(no company name — brand rule.)

> Copy check: lowercase trovex, no banned words, no hype, real framing, no company name. Re-run
> anti-ai-slop on the final page copy before it ships.

## 5. Build spec (keep it tiny)

- **Single static page.** No backend for Mode A — all math is client-side JS. No database, no accounts,
  no tracking beyond privacy-respecting analytics (defer to analytics-lead's plan for the event names).
- **Stack:** plain HTML + a little JS, or drop it into the existing landing (the `web/` Vite+React app)
  as a route like `trovex.dev/savings`. Reuse the site's styles so it's coherent.
- **Mode B** (v2) needs one unauthenticated call to the GitHub API for public repos; rate-limit-aware,
  graceful fallback to Mode A.
- **No PII, no email gate.** Gating the result behind an email kills the share value and the trust. The
  result is free and instant; the only ask is the link to the repo.
- **Shareable:** encode the inputs in the URL querystring so a result is linkable (e.g. someone posts
  "my repo would save $X/mo" with a link). This is the organic-distribution hook.

## 6. Funnel fit (why this earns its keep)

- **Top-of-funnel discovery (awareness):** a calculator is independently searchable and linkable —
  "agent token cost calculator" is a query devs run; it's shareable in the exact communities in the
  community plan; it's a soft, non-spammy thing to drop in a thread because it's a tool, not a pitch.
- **Activation bridge:** the calculator produces the *estimated* savings; trovex produces the *measured*
  one. The page hands the visitor a reason to install: "you guessed $X — go see the real number." That's
  a cleaner activation path than a feature list.
- **North-star alignment:** it qualifies reach. Someone who runs the calculator on a doc-heavy team repo
  and sees a big monthly number is exactly the consulting-adjacent lead — the footer gives them a quiet door.
- **Measurement:** instrument calculator-run, show-the-math, repo-link-click, and (later) install-from-calc
  so we can see if it actually feeds activation. Hand event names to analytics-lead.

**Where it does NOT help (be honest):** it won't move people with tiny doc sets, and a flattering-but-fake
number would poison trust. Its whole value is being the honest version of the savings story.

## 7. Scope / sequencing recommendation

- **v1 (small):** Mode A static page on `trovex.dev/savings`, client-side math, shareable URL, low-key
  repo link + consulting footer. A day or two of work.
- **v2 (later):** Mode B (paste/GitHub-tree estimate), deeper presets, the install-from-calc event.
- **Decision for cmo:** is `/savings` worth a slot now, or after the registry + HN/PH launches land? It
  pairs naturally with the community plan (a useful thing to share) and the landing CRO work — coordinate
  with cro-lead so it doesn't fight the main landing's conversion path.

*This is a spec. Nothing is built or deployed.*
