# widen-retry-reseed

## Team : trovex-backend (tsukumo)
## Branch : test/widen-retry-reseed (from main)
## Status : 🔵 SUBMITTED

## 1. Product Brief

### Acceptance Criteria
_(untyped ticket — no acceptance criteria)_

## 2. Root cause & decisions

## review-trovex verdict: SHIP

ROOT_CAUSE: The widen-retry regression test was vacuous. It seeded 70 archived
near-duplicates that shared the SAME four-query-term profile as the single active
doc; the active doc's only difference was lighter filler tokens ("live doc" vs
"notes {i}"). Under BagEmbedder's L2-normalized bag-of-words + cosine distance,
identical query-term counts mean cosine sim scales as 1/‖doc‖ — the active doc's
smaller noise magnitude gave it a HIGHER cosine (lower distance) than every
archived dup, so it always ranked #1 in the first-pass KNN pool (k = limit*5 = 25).
It therefore survived the lifecycle filter in the first pass and was returned
WITHOUT the widen-retry ever firing. The test passed even under the old buggy
guard (`filtered and total > pool`, which never retried an unfiltered query), so
it protected nothing — exactly the reviewer's round-2/round-3 finding.

DECISION: Invert the similarity ordering so the active doc is provably squeezed
OUT of the first-pass pool, making the widen-retry the sole recovery path:
- Every archived dup carries ALL four query terms (reverse/proxy/tls/nginx);
  the one active doc carries only TWO (reverse/proxy, no tls/nginx). Fewer
  matched terms → strictly lower cosine → active is farther than all N archived
  dups → first-pass top-25 is 100% archived → lifecycle filter empties it →
  only the whole-index widen-retry (total > pool) surfaces the active doc.
- Call search(..., hybrid=False) so BM25 is not an alternate recovery route:
  the dense widen-retry is the ONLY thing that can make the assertion pass.
- N=30 archived (> pool 25) keeps the pool saturated with a safe margin while
  staying cheap.
VERIFICATION: passes on current source; simulating the old
unfiltered-never-retry guard (no retry) makes the first pass empty and the
assertion fails (`assert <active> in set()`), proving the test is now
non-vacuous. Full gate green: ruff check src tests, pytest -q → 344 passed,
brand guard clean.

REJECTED ALTERNATIVE: keeping the real hybrid search surface (hybrid=True). BM25
would be a second recovery route for the active doc and could mask a dense
widen-retry regression, re-introducing vacuousness. Isolating the dense path is
the point of this regression test.

review-trovex: ✅ ship — 2 files (test + provenance md), test-only, gate green
(ruff + pytest 344 passed), brand guard clean, no src/schema/wire/route change,
Active-Memory invariants untouched, no secret/brand/host/number leak.

## 3. Files changed

```
features/widen-retry-reseed.md        | 54 +++++++++++++++++++++++++++++++++++
 tests/test_store_write_correctness.py | 37 ++++++++++++++++++++----
 2 files changed, 85 insertions(+), 6 deletions(-)
```

## 4. QA Log

### Round 2 — ❌ REJECTED by review-widen-retry-reseed
blocker: reseed still vacuous — widen-retry disabled and test still passes; active doc already in first-pass top-25, so retry path unverified

### Round 3 — ❌ REJECTED by review-widen-retry-reseed
reseed still vacuous: active doc in first-pass top-25, widen-retry never fires (repro of round-2)

## 5. Timeline

- round 2 → **reject** (review-widen-retry-reseed)
- round 3 → **reject** (review-widen-retry-reseed)

---
_Auto-assembled by the niwa scribe from the Q&A gate. Task `widen-retry-reseed`._
